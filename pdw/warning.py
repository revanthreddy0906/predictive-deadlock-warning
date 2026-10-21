"""Risk score, alarm-onset logic and the warning methods compared in the paper.

Every method maps per-step data to a score in [0, 100]; alarms come from the same
onset rule for all of them:

    alarm onset at t  <=>  score >= threshold for k consecutive unmasked steps ending
                           at t, and no onset in the previous R steps (refractory).

`mask` (the merged unsafe-episode mask, fix A3) suppresses alarms while the system is
already unsafe: masked steps reset the k-counter and never start a refractory period.

Methods
    combined        weighted mean of the five indicators
    <indicator>     one indicator alone (need_pressure, contention, waiting_ratio,
                    request_rate)
    availability    alarm when the available fraction drops below t_a; identical to
                    the scarcity indicator alone, so scarcity is not listed separately
    lookahead       fraction of running processes whose max feasible grant would make
                    the state unsafe (fix B3)
    random          Bernoulli(p) onsets on unmasked steps, same refractory rule (fix B2)

Added for the full paper (need the simulator's `extras`):
    combined_max      weighted maximum instead of weighted mean of the indicators
    margin            1 - safety margin (scalar Finkel & Madduri-style distance to unsafe)
    approx_lookahead  lookahead restricted to the 3 processes with the largest grants
    logreg, gbt       learned models on the same signals (pdw.learned; scored in evalcore)
`noisy=True` recomputes claim-based indicators from misdeclared claims (robustness).
"""

from __future__ import annotations

import numpy as np

from pdw.indicators import NAMES

SINGLE = ("need_pressure", "contention", "waiting_ratio", "request_rate")
METHODS = ("combined", *SINGLE, "availability", "lookahead", "random")
EXTRA_METHODS = ("combined_max", "margin", "approx_lookahead")
EQUAL_WEIGHTS = (1.0,) * len(NAMES)
LEVELS = ((30, "LOW"), (60, "MEDIUM"), (80, "HIGH"), (100, "CRITICAL"))


def risk_score(ind: np.ndarray, weights=EQUAL_WEIGHTS) -> np.ndarray:
    """100 * sum(w_i * ind_i) / sum(w_i), clipped to [0, 100]."""
    w = np.asarray(weights, dtype=np.float64)
    if (w < 0).any() or w.sum() <= 0:
        raise ValueError("weights must be non-negative with positive sum")
    return np.clip(100.0 * (np.asarray(ind, dtype=np.float64) @ w) / w.sum(), 0.0, 100.0)


def level(score: float) -> str:
    for upper, name in LEVELS:
        if score <= upper:
            return name
    return "CRITICAL"


def max_score(ind: np.ndarray, weights=EQUAL_WEIGHTS) -> np.ndarray:
    """100 * max_i (w_i / max w) * ind_i: the most alarming indicator decides."""
    w = np.asarray(weights, dtype=np.float64)
    if (w < 0).any() or w.max() <= 0:
        raise ValueError("weights must be non-negative with a positive entry")
    return np.clip(100.0 * (np.asarray(ind, dtype=np.float64) * (w / w.max())).max(axis=1), 0.0, 100.0)


def noisy_indicators(ind: np.ndarray, extras: np.ndarray) -> np.ndarray:
    """Indicators with need_pressure and contention recomputed from misdeclared claims."""
    out = np.array(ind, dtype=np.float64, copy=True)
    out[:, NAMES.index("need_pressure")] = extras[:, 2]
    out[:, NAMES.index("contention")] = extras[:, 3]
    return out


def method_score(method: str, ind: np.ndarray, lookahead: np.ndarray | None = None,
                 weights=EQUAL_WEIGHTS, extras: np.ndarray | None = None,
                 noisy: bool = False) -> np.ndarray:
    if noisy:
        if extras is None:
            raise ValueError("noisy indicators need extras")
        ind = noisy_indicators(ind, extras)
    if method == "combined":
        return risk_score(ind, weights)
    if method == "combined_max":
        return max_score(ind, weights)
    if method in ("margin", "approx_lookahead"):
        if extras is None:
            raise ValueError(f"{method} needs the simulator's extras")
        col = 0 if method == "margin" else 1
        return 100.0 * np.nan_to_num(np.asarray(extras[:, col], dtype=np.float64), nan=0.0)
    if method in SINGLE:
        return 100.0 * np.asarray(ind[:, NAMES.index(method)], dtype=np.float64)
    if method == "availability":
        return 100.0 * np.asarray(ind[:, NAMES.index("scarcity")], dtype=np.float64)
    if method == "lookahead":
        if lookahead is None:
            raise ValueError("lookahead scores not recorded for this sequence")
        return 100.0 * np.nan_to_num(np.asarray(lookahead, dtype=np.float64), nan=0.0)
    raise ValueError(f"no score for method {method!r}")


def _refractory_filter(cand: np.ndarray, refractory: int) -> np.ndarray:
    """Greedy: keep the first candidate, skip candidates within `refractory` steps."""
    out = []
    i, c = 0, cand
    while i < c.size:
        o = int(c[i])
        out.append(o)
        i = int(np.searchsorted(c, o + refractory, side="right"))
    return np.array(out, dtype=np.int64)


def alarm_onsets(score: np.ndarray, threshold: float, k: int = 1, refractory: int = 20,
                 mask: np.ndarray | None = None) -> np.ndarray:
    if k < 1:
        raise ValueError("k must be >= 1")
    above = np.asarray(score) >= threshold
    if mask is not None:
        above &= ~np.asarray(mask, dtype=bool)
    if k > 1:
        idx = np.arange(above.size)
        last_off = np.maximum.accumulate(np.where(~above, idx, -1))
        above = (idx - last_off) >= k
    return _refractory_filter(np.flatnonzero(above), refractory)


def random_onsets(T: int, p: float, refractory: int, mask: np.ndarray | None,
                  rng: np.random.Generator) -> np.ndarray:
    cand = rng.random(T) < p
    if mask is not None:
        cand &= ~np.asarray(mask, dtype=bool)
    return _refractory_filter(np.flatnonzero(cand), refractory)


def weight_grid() -> list[tuple[str, tuple[float, ...]]]:
    """Equal weights, each indicator doubled, each indicator removed (Phase 10)."""
    grid = [("equal", EQUAL_WEIGHTS)]
    for i, name in enumerate(NAMES):
        w = list(EQUAL_WEIGHTS)
        w[i] = 2.0
        grid.append((f"double_{name}", tuple(w)))
    for i, name in enumerate(NAMES):
        w = list(EQUAL_WEIGHTS)
        w[i] = 0.0
        grid.append((f"drop_{name}", tuple(w)))
    return grid
