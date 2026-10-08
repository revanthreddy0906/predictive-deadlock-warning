"""Phase 12: runtime scaling versus the Theta(m * n^2) safety-check bound.

    python -m experiments.scaling --config configs/scaling.yaml

Per (n, m): time per safety check, per detection run, detection runs per step (fix E3),
steps/sec, peak RSS; plus vectorised-vs-reference safety-check timing on random valid
states. Fits log(time per check) = a + b log(n) for each m.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from experiments.common import load_config
from pdw import banker
from pdw.simulator import simulate
from pdw.state import random_arbitrary_state


def _peak_rss_mb() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 2**20 if sys.platform == "darwin" else r / 2**10  # bytes on macOS, KB on Linux


def _time_impl(fn, states, reps):
    t0 = time.perf_counter()
    for _ in range(reps):
        for s in states:
            fn(s.available, s.allocation, s.need, s.active)
    return (time.perf_counter() - t0) / (reps * len(states))


def _one(args):
    scenario, n, m, seeds, steps, ref_states = args
    rows = []
    for seed in seeds:
        r = simulate(scenario, n, m, seed, steps)
        rows.append({"T": r.T, "runtime": r.runtime, "safety_time": r.safety_time, "safety_calls": r.safety_calls,
                     "detect_time": r.detect_time, "detect_calls": r.detect_calls})
    df = pd.DataFrame(rows).sum()
    rng = np.random.default_rng(n * 1000 + m)
    states = [random_arbitrary_state(n, m, rng) for _ in range(ref_states)]
    vec = _time_impl(banker.is_safe, states, reps=20)
    ref = _time_impl(banker.is_safe_reference, states, reps=1)
    return {
        "n": n, "m": m, "sequences": len(seeds), "steps": int(df["T"]),
        "safety_us_per_call": 1e6 * df["safety_time"] / max(df["safety_calls"], 1),
        "detect_us_per_call": 1e6 * df["detect_time"] / max(df["detect_calls"], 1),
        "detect_calls_per_step": df["detect_calls"] / max(df["T"], 1),
        "steps_per_sec": df["T"] / df["runtime"],
        "us_per_step": 1e6 * df["runtime"] / max(df["T"], 1),
        "vectorised_us_random_states": 1e6 * vec, "reference_us_random_states": 1e6 * ref,
        "speedup": ref / vec, "peak_rss_mb": _peak_rss_mb(),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/scaling.yaml")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    out = os.path.join("results", cfg["run_name"])
    os.makedirs(out, exist_ok=True)
    seeds = list(range(cfg["seeds"]["start"], cfg["seeds"]["start"] + cfg["seeds"]["count"]))
    jobs = [(cfg["scenario"], n, m, seeds, cfg["steps"], cfg["reference_states"])
            for n in cfg["processes"] for m in cfg["resources"]]
    # Few workers: timings are less distorted when cores are not all saturated.
    with ProcessPoolExecutor(int(cfg.get("workers", 4))) as ex:
        df = pd.DataFrame(list(ex.map(_one, jobs)))
    df.to_csv(os.path.join(out, "scaling.csv"), index=False)

    fits = []
    for col in ("safety_us_per_call", "vectorised_us_random_states", "reference_us_random_states"):
        for m, g in df.groupby("m"):
            b, a = np.polyfit(np.log(g["n"]), np.log(g[col]), 1)
            fits.append({"metric": col, "m": m, "slope_log_n": b})
    fits = pd.DataFrame(fits)
    fits.to_csv(os.path.join(out, "scaling_fits.csv"), index=False)
    json.dump({"config": cfg}, open(os.path.join(out, "meta.json"), "w"), indent=2)
    pd.set_option("display.width", 250)
    print(df.round(2).to_string(index=False))
    print(fits.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
