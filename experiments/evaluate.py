"""Phase 11: apply frozen tuned parameters to the test split, all methods.

    python -m experiments.evaluate --run results/main_test --params results/tuning/best_params.json

Targets
    unsafe        primary unsafe events (flicker-merged), alarms masked during episodes;
                  H_max in {5, 10, 20, 50} with the same alarms (fix A8)
    first_onset   first raw unsafe onset per sequence (robustness check, fix A4)
    deadlock      deadlock onset; alarms NOT masked during unsafe episodes, so a warning
                  issued while the system is unsafe can still anticipate the deadlock
Outputs go to <run>/eval/: per-sequence rows (rows.parquet) and one CSV per table.
No parameter is chosen here; the PR sweep is for plotting only.
"""

from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from experiments.common import TEST_SEEDS
from experiments.evalcore import (COUNTS, H_MAX, THRESHOLDS, eval_counts, load_models, prepare, random_rng,
                                  score_for)
from pdw import io, learned, metrics, warning

H_LIST = (5, 10, 20, 50)
ALL_SCORED = ("combined", *warning.SINGLE, "availability", "lookahead", *warning.EXTRA_METHODS, *learned.LEARNED)
# Robustness: the tuned rule applied to indicators computed from misdeclared claims (+-20%).
NOISY = ("combined", "combined_max", "need_pressure", "contention", *learned.LEARNED)


def _row(base, method, target, H, r, keep_leads):
    out = {**base, "method": method, "target": target, "H_max": H, **{c: r[c] for c in COUNTS}}
    out["quiet"] = r["quiet"]
    out["leads"] = json.dumps(r["leads"]) if keep_leads else "{}"
    return out


def _eval_chunk(args):
    path, best, by_w, gap, reps, scored, models_path = args
    models = load_models(models_path)
    rows, seqs = [], []
    pr = {m: np.zeros((len(THRESHOLDS), 5), np.int64) for m in scored}  # true,false,events,captured,T
    pr_leads = {m: np.zeros((len(THRESHOLDS), H_MAX + 1), np.int64) for m in scored}
    for raw in io.read_chunk(path):
        assert raw["seed"] in TEST_SEEDS, "evaluation must only see test seeds"
        seq = prepare(raw, gap)
        ev = seq["ev"]
        has_look = seq.get("lookahead") is not None
        base = {"scenario": seq["scenario"], "n": seq["n"], "m": seq["m"], "seed": seq["seed"],
                "has_lookahead": has_look, "has_extras": seq.get("extras") is not None}

        spike_idx = np.flatnonzero(seq["in_spike"])
        outcomes = [e[2] for e in ev.episodes]
        seqs.append({**base, "T": seq["T"], "end_reason": seq["end_reason"],
                     "n_events": int(ev.unsafe_events.size), "n_raw_onsets": ev.n_raw_onsets,
                     "first_event": int(ev.unsafe_events[0]) if ev.unsafe_events.size else -1,
                     "spike_start": int(spike_idx[0]) if spike_idx.size else -1,
                     "ep_recovered": outcomes.count("recovered"), "ep_deadlocked": outcomes.count("deadlocked"),
                     "ep_censored": outcomes.count("censored"), "tightness": seq["tightness"]})

        for method in scored:
            p = best[method]
            score = score_for(seq, method, p.get("weights"), models)
            if score is None:
                continue
            alarms = warning.alarm_onsets(score, p["threshold"], p["k"], p["R"], ev.mask)
            for H in H_LIST:
                rows.append(_row(base, method, "unsafe", H, eval_counts(alarms, ev.unsafe_events, seq, H), H == 20))
            rows.append(_row(base, method, "first_onset", 20, eval_counts(alarms, ev.first_onset, seq), False))
            alarms_u = warning.alarm_onsets(score, p["threshold"], p["k"], p["R"], None)
            for H in (20, 50):
                rows.append(_row(base, method, "deadlock", H,
                                 eval_counts(alarms_u, ev.deadlock_events, seq, H), H == 20))
            for i, th in enumerate(THRESHOLDS):  # PR sweep at the tuned k, R, weights
                r = eval_counts(warning.alarm_onsets(score, th, p["k"], p["R"], ev.mask), ev.unsafe_events, seq)
                pr[method][i] += [r["true"], r["false"], r["events"], r["captured"], r["T"]]
                for lead in r["leads"].values():
                    pr_leads[method][i, lead] += 1

        # robustness: the same tuned rules fed indicators computed from misdeclared claims
        for method in NOISY:
            if method not in best:
                continue
            p = best[method]
            score = score_for(seq, method, p.get("weights"), models, noisy=True)
            if score is None:
                continue
            alarms = warning.alarm_onsets(score, p["threshold"], p["k"], p["R"], ev.mask)
            rows.append(_row(base, method, "noisy_claims", 20, eval_counts(alarms, ev.unsafe_events, seq), True))

        # random baseline: average counts over `reps` draws; leads from the first draw
        rp = best["random"]
        targets = [("unsafe", H, ev.unsafe_events, ev.mask) for H in H_LIST] + \
                  [("first_onset", 20, ev.first_onset, ev.mask), ("deadlock", 20, ev.deadlock_events, None),
                   ("deadlock", 50, ev.deadlock_events, None)]
        for target, H, ev_steps, mask in targets:
            acc, first = None, None
            for rep in range(reps):
                al = warning.random_onsets(seq["T"], rp["p"], rp["R"], mask, random_rng(seq, rep + 1))
                r = eval_counts(al, ev_steps, seq, H)
                v = np.array([r[c] for c in COUNTS], float)
                acc = v if acc is None else acc + v
                first = first or r
            r = {**first, **dict(zip(COUNTS, acc / reps))}
            rows.append(_row(base, "random", target, H, r, H == 20 and target in ("unsafe", "deadlock")))

        # ablation: combined with each indicator removed (tuned for that weight vector)
        for wn, p in by_w.items():
            if not (wn == "equal" or wn.startswith("drop_")):
                continue
            score = score_for(seq, "combined", p["weights"])
            alarms = warning.alarm_onsets(score, p["threshold"], p["k"], p["R"], ev.mask)
            rows.append(_row(base, f"combined[{wn}]", "ablation", 20,
                             eval_counts(alarms, ev.unsafe_events, seq), False))
    return _compact(pd.DataFrame(rows)), pd.DataFrame(seqs), pr, pr_leads


def _compact(df: pd.DataFrame) -> pd.DataFrame:
    """Shrink per-sequence rows (about 60 per sequence) so large runs fit in memory."""
    if df.empty:
        return df
    for c in ("scenario", "method", "target"):
        df[c] = df[c].astype("category")
    for c in ("n", "m", "H_max"):
        df[c] = df[c].astype("int16")
    df["seed"] = df["seed"].astype("int32")
    for c in COUNTS:  # random-baseline rows hold averages over reps, so keep floats there
        df[c] = df[c].astype("float32") if (df[c] % 1 != 0).any() else df[c].astype("int32")
    return df


def _metrics_row(df: pd.DataFrame, ci: bool, B: int) -> dict:
    out = {"sequences": int(df[["scenario", "n", "seed"]].drop_duplicates().shape[0])}
    s = df[list(COUNTS)].sum()
    out.update({c: float(s[c]) for c in ("alarms", "true", "false", "censored", "events", "captured", "uncatchable")})
    out.update({k: float(v) for k, v in metrics.summarize_counts(s["true"], s["false"], s["events"],
                                                                  s["captured"], s["T"]).items()})
    leads = [v for js in df["leads"] for v in json.loads(js).values()]
    out.update(metrics.lead_stats(leads))
    out["n_leads"] = len(leads)
    out["alarms_per_1000"] = 1000.0 * float(s["alarms"]) / max(float(s["T"]), 1.0)
    # NAB-style score needs every captured event's lead, i.e. rows that kept their leads
    out["nab"] = metrics.nab_score(leads, float(s["false"]), float(s["events"])) \
        if len(leads) == int(s["captured"]) else np.nan
    if ci:
        for k, (lo, hi) in metrics.bootstrap_ci(df, B=B).items():
            out[f"{k}_lo"], out[f"{k}_hi"] = lo, hi
    return out


def table(rows: pd.DataFrame, by: list[str], ci: bool = False, B: int = 1000) -> pd.DataFrame:
    recs = []
    for key, g in rows.groupby(by, sort=False, observed=True):
        key = key if isinstance(key, tuple) else (key,)
        recs.append({**dict(zip(by, key)), **_metrics_row(g, ci, B)})
    return pd.DataFrame(recs)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="results/main_test")
    ap.add_argument("--params", default="results/tuning/best_params.json")
    ap.add_argument("--reps", type=int, default=10, help="random-baseline repetitions")
    ap.add_argument("--bootstrap", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    args = ap.parse_args(argv)

    meta = json.load(open(os.path.join(args.run, "meta.json")))
    assert meta["config"]["split"] == "test", "evaluate only on the test split"
    params = json.load(open(args.params))
    best, by_w = params["best"], params["best_by_weights"]
    gap = meta["config"].get("min_safe_gap", 5)
    models_path = params.get("models")
    models_path = models_path if models_path and os.path.exists(models_path) else None
    scored = [m for m in ALL_SCORED if m in best and (m not in learned.LEARNED or models_path)]
    out = os.path.join(args.run, "eval")
    os.makedirs(out, exist_ok=True)

    with ProcessPoolExecutor(args.workers) as ex:
        parts = list(ex.map(_eval_chunk, [(f, best, by_w, gap, args.reps, scored, models_path)
                                          for f in io.chunk_files(args.run)]))
    rows = pd.concat([p[0] for p in parts], ignore_index=True)
    for c in ("scenario", "method", "target"):  # concat of differing categories falls back to object
        rows[c] = rows[c].astype("category")
    for c in COUNTS:
        rows[c] = rows[c].astype("float64")  # sums over millions of rows: avoid overflow
    seqs = pd.concat([p[1] for p in parts], ignore_index=True)
    rows.to_parquet(os.path.join(out, "rows.parquet"))
    seqs.to_parquet(os.path.join(out, "sequences.parquet"))

    main_rows = rows[(rows.target == "unsafe") & (rows.H_max == 20)]
    tables = {
        "overall": table(main_rows, ["method"], ci=True, B=args.bootstrap),
        "per_scenario": table(main_rows, ["scenario", "method"], ci=True, B=args.bootstrap),
        "per_size": table(main_rows, ["n", "m", "method"]),
        "deadlock_target": table(rows[rows.target == "deadlock"], ["H_max", "method"], ci=True, B=args.bootstrap),
        "first_onset_target": table(rows[rows.target == "first_onset"], ["method"]),
        "hmax_sensitivity": table(rows[rows.target == "unsafe"], ["H_max", "method"]),
        "ablation": table(rows[rows.target == "ablation"], ["method"]),
        "lookahead_subset": table(main_rows[main_rows.has_lookahead], ["method"], ci=True, B=args.bootstrap),
    }
    noisy = rows[rows.target == "noisy_claims"]
    if len(noisy):
        clean = table(main_rows[main_rows.method.isin(list(NOISY))], ["method"])
        dirty = table(noisy, ["method"])
        tables["noisy_claims"] = clean[["method", "precision", "recall", "f1"]].merge(
            dirty[["method", "precision", "recall", "f1"]], on="method", suffixes=("_true_claims", "_noisy_claims"))

    # compute cost of each method, from the per-sequence timings of the simulation run
    summ = pd.read_parquet(os.path.join(args.run, "summary.parquet"))
    cost = []
    sim_us = 1e6 * (summ.runtime - summ.lookahead_time - summ.get("extras_time", 0)).sum() / summ["T"].sum()
    cost.append({"method": "simulation step (incl. 1 safety check + indicators)", "us_per_step": sim_us})
    cost.append({"method": "safety check (Banker's)", "us_per_step": 1e6 * summ.safety_time.sum() / summ["T"].sum()})
    for col, name in (("margin_time", "margin"), ("approx_time", "approx_lookahead"), ("lookahead_time", "lookahead")):
        if col in summ and summ[col].sum() > 0:
            sub = summ[summ[col] > 0]
            for n, g in [("all", sub), *sub.groupby("n")]:
                cost.append({"method": name, "n": n, "us_per_step": 1e6 * g[col].sum() / g["T"].sum()})
    cost = pd.DataFrame(cost)
    cost["relative_to_simulation_step"] = cost.us_per_step / sim_us
    tables["cost"] = cost

    # paired lead times: combined vs every other method, on events both captured (F11)
    pairs = []
    base = main_rows[main_rows.method == "combined"].set_index(["scenario", "n", "seed"])["leads"]
    for method in [str(x) for x in main_rows.method.unique()]:
        if method == "combined":
            continue
        other = main_rows[main_rows.method == method].set_index(["scenario", "n", "seed"])["leads"]
        common = base.index.intersection(other.index)
        a, b = metrics.paired_leads([json.loads(x) for x in base.loc[common]],
                                    [json.loads(x) for x in other.loc[common]])
        pairs.append({"method": method, "pairs": len(a),
                      "combined_median": float(np.median(a)) if len(a) else np.nan,
                      "other_median": float(np.median(b)) if len(b) else np.nan,
                      "median_diff": float(np.median(a - b)) if len(a) else np.nan,
                      "combined_earlier_frac": float((a > b).mean()) if len(a) else np.nan})
    tables["paired_leads"] = pd.DataFrame(pairs)

    ep = seqs.groupby("scenario", sort=False)[["ep_recovered", "ep_deadlocked", "ep_censored"]].sum()
    resolved = ep["ep_recovered"] + ep["ep_deadlocked"]
    ep["recovered_frac"] = ep["ep_recovered"] / resolved.where(resolved > 0)
    ep["deadlocked_frac"] = ep["ep_deadlocked"] / resolved.where(resolved > 0)
    tables["episode_outcomes"] = ep.reset_index()

    cls = seqs.groupby(["scenario", "n", "m"], sort=False).agg(
        sequences=("seed", "size"), with_event=("n_events", lambda x: float((x > 0).mean())),
        events=("n_events", "sum"), steps=("T", "sum"),
        deadlock_end=("end_reason", lambda x: float((x == "deadlock").mean())),
        tightness=("tightness", "mean"))
    tables["setup"] = cls.reset_index()

    sp = seqs[(seqs.scenario == "spike") & (seqs.n_events > 0) & (seqs.spike_start >= 0)]
    tables["spike_timing"] = pd.DataFrame([{
        "spike_sequences_with_event": len(sp),
        "event_before_spike": float((sp.first_event < sp.spike_start).mean()) if len(sp) else np.nan,
        "median_steps_from_spike_start": float((sp.first_event - sp.spike_start).median()) if len(sp) else np.nan,
    }])

    pr = []
    for method in scored:
        tot = sum(p[2][method] for p in parts)
        lh = sum(p[3][method] for p in parts)
        m = metrics.summarize_counts(tot[:, 0], tot[:, 1], tot[:, 2], tot[:, 3], tot[:, 4])
        for i, th in enumerate(THRESHOLDS):
            med = float(np.median(np.repeat(np.arange(lh.shape[1]), lh[i]))) if lh[i].sum() else np.nan
            pr.append({"method": method, "threshold": th, **{k: float(v[i]) for k, v in m.items()},
                       "lead_median": med, "tuned": th == best[method]["threshold"]})
    tables["pr_curves"] = pd.DataFrame(pr)

    lead_rows = [{"method": r.method, "scenario": r.scenario, "lead": v}
                 for r in main_rows.itertuples() for v in json.loads(r.leads).values()]
    tables["leads_long"] = pd.DataFrame(lead_rows)

    for name, t in tables.items():
        t.to_csv(os.path.join(out, f"{name}.csv"), index=False)

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    cols = ["method", "precision", "recall", "f1", "f1_lo", "f1_hi", "fa_per_1000", "lead_median", "events", "alarms"]
    print("== Overall, unsafe target, H_max = 20 (test split)")
    print(tables["overall"][cols].round(3).to_string(index=False))
    print("\n== Episode outcomes")
    print(tables["episode_outcomes"].round(3).to_string(index=False))
    print(f"\nWrote {len(tables)} tables to {out}")


if __name__ == "__main__":
    main()
