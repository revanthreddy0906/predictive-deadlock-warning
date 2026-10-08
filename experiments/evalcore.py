"""Shared evaluation machinery for tuning (Phase 10) and evaluation (Phase 11).

Everything is recomputed offline from stored per-step arrays, so one simulation run
feeds every method, threshold and target.
"""

from __future__ import annotations

import numpy as np

from pdw import events, warning
from pdw.metrics import evaluate_sequence
from pdw.simulator import SCENARIO_IDS

THRESHOLDS = tuple(range(5, 100, 5))
KS = (1, 2, 3)
REFRACTORIES = (10, 20)
H_MAX = 20
H_MIN = 1
COUNTS = ("alarms", "true", "false", "censored", "events", "captured", "uncatchable", "T")


def score_sources() -> list[tuple[str, str, tuple]]:
    """(method, weights_name, weights) for every score vector the tuner sweeps."""
    out = [("combined", wn, w) for wn, w in warning.weight_grid()]
    out += [(m, "-", ()) for m in (*warning.SINGLE, "availability", "lookahead")]
    return out


def tuning_configs() -> list[dict]:
    return [
        {"method": m, "weights_name": wn, "weights": w, "threshold": th, "k": k, "R": R}
        for m, wn, w in score_sources() for k in KS for R in REFRACTORIES for th in THRESHOLDS
    ]


def prepare(row: dict, gap: int) -> dict:
    ev = events.extract(row["unsafe"], row["deadlocked"], row["end_reason"], gap)
    return {**row, "ev": ev}


def score_for(seq: dict, method: str, weights) -> np.ndarray | None:
    if method == "lookahead" and seq.get("lookahead") is None:
        return None
    return warning.method_score(method, seq["indicators"], seq.get("lookahead"),
                                weights if method == "combined" else warning.EQUAL_WEIGHTS)


def eval_counts(alarms, ev_steps, seq: dict, H_max: int = H_MAX) -> dict:
    return evaluate_sequence(alarms, ev_steps, seq["T"], seq["end_reason"], H_MIN, H_max)


def random_rng(seq: dict, rep: int) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence(
        [seq["seed"], SCENARIO_IDS[seq["scenario"]], seq["n"], seq["m"], 7919, rep]))
