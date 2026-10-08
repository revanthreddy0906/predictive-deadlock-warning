"""Phase 8: scenario class-balance check on tuning seeds.

    python -m experiments.calibrate --config configs/calibrate.yaml

Prints, per scenario and size: fraction of sequences with >= 1 primary unsafe event,
mean events, end reasons, median first-event step, fraction of events too early to
catch, mean T, realised claim tightness. Never touches test seeds.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from experiments.common import load_config, n_workers, TUNING_SEEDS
from pdw import events
from pdw.simulator import simulate

UNCATCHABLE_BEFORE = 3  # k_max - 1 + H_min with k_max = 3, H_min = 1 (fix A5)


def _one(args):
    sc, n, m, seed, steps, window, overrides, gap = args
    r = simulate(sc, n, m, seed, steps, window, overrides)
    ev = events.extract(r.unsafe, r.deadlocked, r.end_reason, gap)
    e = ev.unsafe_events
    return {
        "scenario": sc, "n": n, "m": m, "seed": seed, "T": r.T, "end": r.end_reason,
        "n_events": len(e), "first_event": int(e[0]) if len(e) else np.nan,
        "early": int((e < UNCATCHABLE_BEFORE).sum()), "tightness": r.tightness,
        "unsafe_frac": float(r.unsafe.mean()) if r.T else 0.0,
        "raw_onsets": ev.n_raw_onsets,
    }


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["scenario", "n", "m"], sort=False)
    out = g.agg(
        seqs=("seed", "size"),
        any_event=("n_events", lambda x: (x > 0).mean()),
        mean_events=("n_events", "mean"),
        raw_onsets=("raw_onsets", "mean"),
        first_event_med=("first_event", "median"),
        early_frac=("early", "sum"),
        T_mean=("T", "mean"),
        unsafe_frac=("unsafe_frac", "mean"),
        tightness=("tightness", "mean"),
    )
    out["early_frac"] = out["early_frac"] / g["n_events"].sum().clip(lower=1)
    for reason in ("deadlock", "all_finished", "max_steps"):
        out[f"end_{reason}"] = g["end"].apply(lambda x, r=reason: (x == r).mean())
    return out.round(3)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/calibrate.yaml")
    ap.add_argument("--seeds", type=int, default=None, help="override seed count")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    count = args.seeds or cfg["seeds"]["count"]
    start = cfg["seeds"]["start"]
    assert start + count <= TUNING_SEEDS.stop, "calibration must use tuning seeds only"
    jobs = [
        (sc, s["processes"], s["resources"], seed, cfg["steps"], cfg["indicator_window"],
         cfg.get("scenario_params", {}).get(sc), cfg["min_safe_gap"])
        for sc in cfg["scenarios"] for s in cfg["sizes"] for seed in range(start, start + count)
    ]
    with ProcessPoolExecutor(n_workers(cfg)) as ex:
        rows = list(ex.map(_one, jobs, chunksize=8))
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    print(summarize(pd.DataFrame(rows)).to_string())


if __name__ == "__main__":
    main()
