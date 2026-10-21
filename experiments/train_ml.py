"""Train the learned baselines (logistic regression, gradient-boosted trees).

    python -m experiments.train_ml --run results/c_tuning

Training data: even tuning seeds only; safe, unmasked steps; label = primary unsafe
onset within the next H_max steps. All positive steps are kept and negatives are
subsampled (default 2%), since onsets are rare. Thresholds for these models are then
tuned on odd tuning seeds (experiments.tune), and reported on the test split.
Writes <run>/ml_models.pkl and <run>/ml_meta.json.
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from experiments.common import TUNING_SEEDS
from experiments.evalcore import H_MAX, H_MIN, ml_tunes_on, prepare
from pdw import io, learned


def _chunk(args):
    path, gap, neg_rate, window = args
    Xs, ys = [], []
    for row in io.read_chunk(path, columns=["scenario", "n", "m", "seed", "T", "end_reason",
                                            "indicators", "unsafe", "deadlocked"]):
        assert row["seed"] in TUNING_SEEDS, "ML training must only see tuning seeds"
        if ml_tunes_on(row["seed"]):
            continue  # odd seeds are reserved for threshold tuning
        seq = prepare(row, gap)
        y = learned.labels(seq["T"], seq["ev"].unsafe_events, H_MAX, H_MIN)
        usable = ~seq["ev"].mask
        rng = np.random.default_rng(row["seed"] * 7 + row["n"])
        keep = usable & (y | (rng.random(seq["T"]) < neg_rate))
        if keep.any():
            Xs.append(learned.features(seq["indicators"], window)[keep])
            ys.append(y[keep])
    if not Xs:
        return np.zeros((0, 10), np.float32), np.zeros(0, bool)
    return np.vstack(Xs).astype(np.float32), np.concatenate(ys)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="results/c_tuning")
    ap.add_argument("--neg-rate", type=float, default=0.05)
    ap.add_argument("--max-rows", type=int, default=4_000_000)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    args = ap.parse_args(argv)

    meta = json.load(open(os.path.join(args.run, "meta.json")))
    assert meta["config"]["split"] == "tuning", "train only on the tuning split"
    gap = meta["config"].get("min_safe_gap", 5)
    window = meta["config"].get("indicator_window", 10)
    t0 = time.time()
    with ProcessPoolExecutor(args.workers) as ex:
        parts = list(ex.map(_chunk, [(f, gap, args.neg_rate, window) for f in io.chunk_files(args.run)]))
    X = np.vstack([p[0] for p in parts])
    y = np.concatenate([p[1] for p in parts])
    # true share of positive steps: negatives were kept with probability neg_rate
    prior = y.sum() / (y.sum() + (~y).sum() / args.neg_rate)
    # Balance classes exactly (equal positives and negatives), capped at max_rows.
    rng = np.random.default_rng(0)
    pos, neg = np.flatnonzero(y), np.flatnonzero(~y)
    k = min(len(pos), len(neg), args.max_rows // 2)
    idx = np.concatenate([rng.choice(pos, k, replace=False), rng.choice(neg, k, replace=False)])
    X, y = X[idx], y[idx]
    models = learned.fit(X, y, prior)
    with open(os.path.join(args.run, "ml_models.pkl"), "wb") as f:
        pickle.dump(models, f)
    info = {"rows": int(len(y)), "positives": int(y.sum()), "neg_sample_rate": args.neg_rate,
            "true_positive_step_share": round(float(prior), 5),
            "features": "5 indicators + their change over the indicator window",
            "label": f"primary unsafe onset within [t+{H_MIN}, t+{H_MAX}]",
            "train_seeds": "even tuning seeds", "threshold_tuning_seeds": "odd tuning seeds",
            "seconds": round(time.time() - t0, 1)}
    json.dump(info, open(os.path.join(args.run, "ml_meta.json"), "w"), indent=2)
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
