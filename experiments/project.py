"""Project the wall-clock time of full runs from a pilot run on the same machine.

    python -m experiments.project --pilot results/b_pilot \
        --configs configs/b_tuning.yaml configs/b_main.yaml

Per (scenario, n) the pilot gives the mean per-sequence runtime with and without the
lookahead baseline (measured while all workers were busy, so it already reflects the
machine under load). The projection counts how many sequences of each kind every target
config runs, adds tuning and evaluation (scaled from steps), and divides by workers.
"""

from __future__ import annotations

import argparse
import json
import os

import pandas as pd

from experiments.common import load_config, n_workers, seed_range
from experiments.run_batch import lookahead_subsample

# Offline tuning/evaluation cost per stored step, relative to simulation cost per step.
# Measured on the Mac run: tuning 4,014 CPU-s and simulation ~5,600 CPU-s (no lookahead)
# for 27.9M steps -> ~0.7; evaluation roughly 0.25.
TUNE_PER_SIM_STEP = 0.75
EVAL_PER_SIM_STEP = 0.30
EFFICIENCY = 0.85  # parallel efficiency (scheduling tail, I/O)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", required=True)
    ap.add_argument("--configs", nargs="+", required=True)
    args = ap.parse_args(argv)

    s = pd.read_parquet(os.path.join(args.pilot, "summary.parquet"))
    s["look"] = s["lookahead_time"] > 0
    s["sim_s"] = s["runtime"] - s["lookahead_time"]
    by = s.groupby(["scenario", "n"])
    sim_per_seq = by["sim_s"].mean()
    look_per_seq = s[s.look].groupby(["scenario", "n"])["lookahead_time"].mean()
    steps_per_seq = by["T"].mean()
    us_per_step = 1e6 * s["sim_s"].sum() / s["T"].sum()

    workers = None
    total_cpu = 0.0
    lines = []
    for path in args.configs:
        cfg = load_config(path)
        workers = workers or n_workers(cfg)
        seeds = seed_range(cfg)
        look = cfg.get("lookahead") or {}
        cpu = steps = 0.0
        for sc in cfg["scenarios"]:
            for size in cfg["sizes"]:
                n = size["processes"]
                k = len(seeds)
                k_look = k if n <= look.get("max_n_all_seeds", 0) else min(k, lookahead_subsample(look, n))
                cpu += k * sim_per_seq[(sc, n)] + k_look * look_per_seq.get((sc, n), 0.0)
                steps += k * steps_per_seq[(sc, n)]
        offline = steps * us_per_step / 1e6 * (TUNE_PER_SIM_STEP if cfg["split"] == "tuning" else EVAL_PER_SIM_STEP)
        total_cpu += cpu + offline
        lines.append({"config": path, "sequences": len(seeds) * len(cfg["scenarios"]) * len(cfg["sizes"]),
                      "steps_M": round(steps / 1e6, 1), "sim_cpu_h": round(cpu / 3600, 2),
                      "offline_cpu_h": round(offline / 3600, 2)})
    wall_h = total_cpu / 3600 / workers / EFFICIENCY
    out = {"workers": workers, "us_per_step_no_lookahead": round(us_per_step, 1),
           "per_config": lines, "projected_wall_hours": round(wall_h, 2)}
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    main()
