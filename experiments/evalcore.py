"""Shared evaluation machinery for tuning (Phase 10) and evaluation (Phase 11).

Everything is recomputed offline from stored per-step arrays, so one simulation run
feeds every method, threshold and target.
"""

from __future__ import annotations

import os
import pickle

import numpy as np

from pdw import events, learned, warning
from pdw.metrics import evaluate_sequence
from pdw.simulator import SCENARIO_IDS

THRESHOLDS = tuple(range(5, 100, 5))
KS = (1, 2, 3)
REFRACTORIES = (10, 20)
H_MAX = 20
H_MIN = 1
COUNTS = ("alarms", "true", "false", "censored", "events", "captured", "uncatchable", "T")


MAX_WEIGHTS = ("equal", "double_contention", "drop_request_rate")  # combined_max variants


def score_sources(extras: bool = False, ml: bool = False) -> list[tuple[str, str, tuple]]:
    """(method, weights_name, weights) for every score vector the tuner sweeps."""
    grid = warning.weight_grid()
    out = [("combined", wn, w) for wn, w in grid]
    out += [(m, "-", ()) for m in (*warning.SINGLE, "availability", "lookahead")]
    if extras:
        out += [("combined_max", wn, w) for wn, w in grid if wn in MAX_WEIGHTS]
        out += [("margin", "-", ()), ("approx_lookahead", "-", ())]
    if ml:
        out += [(m, "-", ()) for m in learned.LEARNED]
    return out


def tuning_configs(extras: bool = False, ml: bool = False) -> list[dict]:
    return [
        {"method": m, "weights_name": wn, "weights": w, "threshold": th, "k": k, "R": R}
        for m, wn, w in score_sources(extras, ml) for k in KS for R in REFRACTORIES for th in THRESHOLDS
    ]


def ml_tunes_on(seed: int) -> bool:
    """Learned models are trained on even tuning seeds; their thresholds are tuned on odd ones."""
    return seed % 2 == 1


_MODELS: dict = {}


def load_models(path: str | None) -> dict | None:
    """Load (and cache per process) the learned models saved by experiments.train_ml."""
    if not path or not os.path.exists(path):
        return None
    if path not in _MODELS:
        with open(path, "rb") as f:
            _MODELS[path] = pickle.load(f)
    return _MODELS[path]


def prepare(row: dict, gap: int) -> dict:
    ev = events.extract(row["unsafe"], row["deadlocked"], row["end_reason"], gap)
    return {**row, "ev": ev}


def score_for(seq: dict, method: str, weights, models: dict | None = None,
              noisy: bool = False) -> np.ndarray | None:
    """Score vector for one sequence, or None if this sequence lacks the data it needs."""
    if method == "lookahead" and seq.get("lookahead") is None:
        return None
    if (method in warning.EXTRA_METHODS or noisy) and seq.get("extras") is None:
        return None
    if method in learned.LEARNED:
        if models is None:
            return None
        ind = warning.noisy_indicators(seq["indicators"], seq["extras"]) if noisy else seq["indicators"]
        return learned.score(models[method], ind, models.get("prior", 0.5))
    w = weights if method in ("combined", "combined_max") else warning.EQUAL_WEIGHTS
    return warning.method_score(method, seq["indicators"], seq.get("lookahead"), w,
                                extras=seq.get("extras"), noisy=noisy)


def eval_counts(alarms, ev_steps, seq: dict, H_max: int = H_MAX) -> dict:
    return evaluate_sequence(alarms, ev_steps, seq["T"], seq["end_reason"], H_MIN, H_max)


def random_rng(seq: dict, rep: int) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence(
        [seq["seed"], SCENARIO_IDS[seq["scenario"]], seq["n"], seq["m"], 7919, rep]))
