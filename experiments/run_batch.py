"""Phase 9: run a grid of sequences and store them as chunked Parquet.

    python -m experiments.run_batch --config configs/main.yaml [--force]

Grid = scenario x size x seed. Each worker simulates one chunk of seeds for one cell
and writes it atomically, so a crashed run resumes by skipping finished chunks (G3).
Re-running the same config is a no-op unless --force (G5); a different config with the
same run_name is refused. Writes meta.json and run.log into results/<run_name>/.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

from experiments.common import config_hash, load_config, n_workers, seed_range
from pdw import io
from pdw.simulator import simulate

log = logging.getLogger("run_batch")


def _git_info() -> dict:
    def run(*a):
        try:
            return subprocess.run(["git", *a], capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:
            return ""
    commit = run("rev-parse", "HEAD") or os.environ.get("PDW_GIT_COMMIT", "")
    return {"commit": commit, "dirty": bool(run("status", "--porcelain"))}


def _machine_info() -> dict:
    import psutil

    info = {
        "platform": platform.platform(), "machine": platform.machine(), "python": sys.version.split()[0],
        "cpu_count": os.cpu_count(), "ram_gb": round(psutil.virtual_memory().total / 2**30, 1),
        "instance_type": os.environ.get("INSTANCE_TYPE", "local"),
    }
    import numpy, pandas, pyarrow
    info["libs"] = {"numpy": numpy.__version__, "pandas": pandas.__version__, "pyarrow": pyarrow.__version__}
    return info


def lookahead_subsample(look: dict, n: int) -> int:
    """Seeds per cell (from the split start) that get the lookahead baseline when
    n > max_n_all_seeds. `subsample_by_n` overrides `subsample_seeds` per size."""
    by_n = {int(k): int(v) for k, v in (look.get("subsample_by_n") or {}).items()}
    return by_n.get(n, int(look.get("subsample_seeds", 0)))


def _run_chunk(job: dict) -> dict:
    results = []
    for seed in job["seeds"]:
        look = job["n"] <= job["look_max_n"] or (seed - job["split_start"]) < job["look_subsample"]
        trace = (seed - job["split_start"]) < job["trace_seeds"]
        r = simulate(job["scenario"], job["n"], job["m"], seed, job["steps"], job["window"],
                     job["overrides"], lookahead=look, store_trace=trace)
        if trace:
            np.savez_compressed(os.path.join(job["trace_dir"], f"{job['scenario']}_{job['n']}x{job['m']}_{seed}.npz"),
                                unsafe=r.unsafe, deadlocked=r.deadlocked, indicators=r.indicators,
                                lookahead=r.lookahead if r.lookahead is not None else np.zeros(0),
                                in_spike=r.in_spike, **r.trace)
            r.trace = None
        results.append(r)
    io.write_chunk(results, job["path"])
    return {"path": job["path"], "sequences": len(results), "steps": int(sum(r.T for r in results)),
            "cpu_s": float(sum(r.runtime for r in results))}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--force", action="store_true", help="delete existing results for this run_name")
    ap.add_argument("--out", default="results")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    seeds = seed_range(cfg)
    h = config_hash(cfg)
    run_dir = os.path.join(args.out, cfg["run_name"])
    meta_path = os.path.join(run_dir, "meta.json")

    if os.path.exists(meta_path):
        old = json.load(open(meta_path))
        if args.force:
            shutil.rmtree(run_dir)
        elif old.get("config_hash") != h:
            sys.exit(f"{run_dir} holds a different config (hash {old.get('config_hash')} != {h}); use --force")
    os.makedirs(os.path.join(run_dir, "chunks"), exist_ok=True)
    os.makedirs(os.path.join(run_dir, "traces"), exist_ok=True)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(os.path.join(run_dir, "run.log")),
                                  logging.StreamHandler()])

    look = cfg.get("lookahead") or {}
    chunk = int(cfg.get("chunk_size", 50))
    jobs = []
    for sc in cfg["scenarios"]:
        for size in cfg["sizes"]:
            n, m = size["processes"], size["resources"]
            for lo in range(seeds.start, seeds.stop, chunk):
                path = os.path.join(run_dir, "chunks", f"{sc}_{n}x{m}_{lo:07d}.parquet")
                if os.path.exists(path):
                    continue
                jobs.append({
                    "scenario": sc, "n": n, "m": m, "seeds": list(range(lo, min(lo + chunk, seeds.stop))),
                    "steps": cfg["steps"], "window": cfg["indicator_window"],
                    "overrides": (cfg.get("scenario_params") or {}).get(sc),
                    "look_max_n": look.get("max_n_all_seeds", 0),
                    "look_subsample": lookahead_subsample(look, n),
                    "trace_seeds": cfg.get("store_full_trace_seeds", 0), "split_start": seeds.start,
                    "trace_dir": os.path.join(run_dir, "traces"), "path": path,
                })

    # Longest chunks first (lookahead chunks, then by size) so no slow chunk is left
    # running alone at the end of the run.
    jobs.sort(key=lambda j: (j["seeds"][0] - j["split_start"] < j["look_subsample"] or j["n"] <= j["look_max_n"],
                             j["n"]), reverse=True)

    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {
        "run_name": cfg["run_name"], "config": cfg, "config_hash": h, "git": _git_info(),
        "machine": _machine_info(), "started": dt.datetime.now().isoformat(timespec="seconds"),
    }
    json.dump(meta, open(meta_path, "w"), indent=2, default=str)
    log.info("run %s (hash %s): %d chunks to do, %d workers", cfg["run_name"], h, len(jobs), n_workers(cfg))

    t0 = time.time()
    done_seq = done_steps = 0
    cpu = 0.0
    if jobs:
        with ProcessPoolExecutor(n_workers(cfg)) as ex:
            futs = [ex.submit(_run_chunk, j) for j in jobs]
            for i, f in enumerate(as_completed(futs), 1):
                r = f.result()
                done_seq += r["sequences"]
                done_steps += r["steps"]
                cpu += r["cpu_s"]
                if i % max(1, len(jobs) // 20) == 0 or i == len(jobs):
                    log.info("%d/%d chunks, %d sequences, %.0fs elapsed", i, len(jobs), done_seq, time.time() - t0)

    summary = io.read_summary(run_dir)
    summary.to_parquet(os.path.join(run_dir, "summary.parquet"))
    meta.update({
        "finished": dt.datetime.now().isoformat(timespec="seconds"),
        "wall_s_last_invocation": round(time.time() - t0, 1),
        "cpu_s_last_invocation": round(cpu, 1),
        "totals": {"sequences": int(len(summary)), "steps": int(summary["T"].sum()),
                   "requests": int(summary["T"].sum())},
    })
    json.dump(meta, open(meta_path, "w"), indent=2, default=str)
    log.info("done: %d sequences, %d steps total", len(summary), int(summary["T"].sum()))


if __name__ == "__main__":
    main()
