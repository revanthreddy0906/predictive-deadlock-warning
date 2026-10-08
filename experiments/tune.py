"""Phase 10: choose each method's parameters on the tuning split only.

    python -m experiments.tune --run results/tuning [--fa-max 5 --min-lead 3]

Grid: threshold 5..95 step 5, k in {1,2,3}, refractory R in {10,20}; for `combined`
also 11 weight vectors (equal, each indicator doubled, each removed). Objective
(fix B1): maximise F1 (unsafe target, H_max = 20) subject to false alarms per 1000
steps <= fa_max and median lead >= min_lead. If nothing is feasible, take max F1 and
record feasible = false.

The random baseline's rate p is matched on the tuning split so it fires as many alarm
onsets in total as the tuned `combined` method (fix B2).

Outputs (into the run dir): tuning_grid.csv (every config), best_params.json.
"""

from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from experiments.common import load_config, TUNING_SEEDS
from experiments.evalcore import (COUNTS, H_MAX, KS, REFRACTORIES, THRESHOLDS, eval_counts, prepare,
                                  random_rng, score_for, score_sources, tuning_configs)
from pdw import io, warning
from pdw.metrics import summarize_counts


def _grid_chunk(args):
    path, gap = args
    sources = score_sources()
    n_cfg = len(sources) * len(KS) * len(REFRACTORIES) * len(THRESHOLDS)
    counts = np.zeros((n_cfg, len(COUNTS)), np.int64)
    hist = np.zeros((n_cfg, H_MAX + 1), np.int64)
    eligible = 0
    for row in io.read_chunk(path):
        assert row["seed"] in TUNING_SEEDS, "tuning must only see tuning seeds"
        seq = prepare(row, gap)
        ev, mask = seq["ev"].unsafe_events, seq["ev"].mask
        eligible += int((~mask).sum())
        c = 0
        for m, wn, w in sources:
            score = score_for(seq, m, w)
            for k in KS:
                for R in REFRACTORIES:
                    for th in THRESHOLDS:
                        if score is not None:
                            r = eval_counts(warning.alarm_onsets(score, th, k, R, mask), ev, seq)
                            counts[c] += [r[x] for x in COUNTS]
                            for lead in r["leads"].values():
                                hist[c, lead] += 1
                        c += 1
    return counts, hist, eligible


def _random_chunk(args):
    path, gap, ps, R = args
    totals = np.zeros(len(ps), np.int64)
    for row in io.read_chunk(path, columns=["scenario", "n", "m", "seed", "T", "end_reason", "unsafe", "deadlocked"]):
        seq = prepare(row, gap)
        rng_state = random_rng(seq, 0)
        u = rng_state.random(seq["T"])  # one uniform draw per step, shared across p
        for i, p in enumerate(ps):
            cand = (u < p) & ~seq["ev"].mask
            totals[i] += warning._refractory_filter(np.flatnonzero(cand), R).size
    return totals


def _median_from_hist(h: np.ndarray) -> float:
    """Exact median of integer leads given their histogram (leads are <= H_max)."""
    return float(np.median(np.repeat(np.arange(h.size), h))) if h.sum() else np.nan


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="results/tuning")
    ap.add_argument("--fa-max", type=float, default=5.0)
    ap.add_argument("--min-lead", type=float, default=3.0)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    args = ap.parse_args(argv)

    meta = json.load(open(os.path.join(args.run, "meta.json")))
    cfg = meta["config"]
    assert cfg["split"] == "tuning", "tune only on the tuning split"
    gap = cfg.get("min_safe_gap", 5)
    files = io.chunk_files(args.run)

    with ProcessPoolExecutor(args.workers) as ex:
        parts = list(ex.map(_grid_chunk, [(f, gap) for f in files]))
    counts = sum(p[0] for p in parts)
    hist = sum(p[1] for p in parts)
    eligible = sum(p[2] for p in parts)

    grid = pd.DataFrame(tuning_configs())
    for j, name in enumerate(COUNTS):
        grid[name] = counts[:, j]
    m = summarize_counts(grid["true"], grid["false"], grid["events"], grid["captured"], grid["T"])
    for k, v in m.items():
        grid[k] = v
    grid["lead_median"] = [_median_from_hist(h) for h in hist]
    grid["feasible"] = (grid["fa_per_1000"] <= args.fa_max) & (grid["lead_median"] >= args.min_lead)
    grid.drop(columns=["weights"]).to_csv(os.path.join(args.run, "tuning_grid.csv"), index=False)

    def pick(df):
        feas = df[df["feasible"]]
        best = (feas if len(feas) else df).sort_values(["f1", "precision"], ascending=False).iloc[0]
        out = {k: best[k] for k in ("method", "weights_name", "threshold", "k", "R")}
        out["weights"] = list(best["weights"]) if best["method"] == "combined" else None
        out.update({k: float(best[k]) for k in ("f1", "precision", "recall", "fa_per_1000", "lead_median")})
        out["alarms"] = int(best["alarms"])
        out["feasible"] = bool(len(feas) > 0)
        return out

    best = {}
    for method, df in grid.groupby("method", sort=False):
        best[method] = pick(df)
    best_by_weights = {wn: pick(df) for wn, df in grid[grid["method"] == "combined"].groupby("weights_name", sort=False)}

    # Random baseline: match total alarm onsets of tuned `combined`.
    target = best["combined"]["alarms"]
    p0 = target / max(eligible, 1)
    ps = np.unique(np.concatenate([p0 * np.geomspace(0.5, 4.0, 40), [p0]]))
    R = int(best["combined"]["R"])
    with ProcessPoolExecutor(args.workers) as ex:
        totals = sum(ex.map(_random_chunk, [(f, gap, ps, R) for f in files]))
    i = int(np.argmin(np.abs(totals - target)))
    best["random"] = {"method": "random", "p": float(ps[i]), "R": R, "alarms": int(totals[i]),
                      "matched_to_alarms": int(target)}

    out = {"best": best, "best_by_weights": best_by_weights,
           "objective": {"maximise": "f1", "fa_per_1000_max": args.fa_max, "lead_median_min": args.min_lead,
                         "H_max": H_MAX, "target": "unsafe (primary events)"},
           "tuning_run": args.run, "tuning_config_hash": meta["config_hash"]}
    with open(os.path.join(args.run, "best_params.json"), "w") as f:
        json.dump(out, f, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o))

    show = pd.DataFrame(best).T[["threshold", "k", "R", "weights_name", "f1", "precision", "recall",
                                 "fa_per_1000", "lead_median", "feasible", "p"]]
    print(show.to_string())


if __name__ == "__main__":
    main()
