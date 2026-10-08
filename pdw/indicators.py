"""Explainable resource-pressure indicators, each in [0, 1].

    scarcity       1 - sum(available) / sum(total)
    need_pressure  mean_j S_j / (S_j + available_j), S_j = outstanding need of active
                   processes for resource j (0 when S_j + available_j == 0)   [fix D1]
    contention     fraction of resource types where >= 2 active processes have
                   need[i, j] > available[j]                                   [fix D2]
    waiting_ratio  waiting processes / active processes
    request_rate   clip((U_last - U_prev) / (U_prev + eps), 0, 1), U = units of *new*
                   requests in the last / previous W steps; 0 until 2W steps exist [D3]

Note: the `availability` baseline (alarm when available fraction < t_a) is exactly
the scarcity indicator on its own, so it is reported once.
"""

from __future__ import annotations

import numpy as np

NAMES = ("scarcity", "need_pressure", "contention", "waiting_ratio", "request_rate")
EPS = 1e-9


def compute(state, need: np.ndarray, req_units: np.ndarray, t: int, window: int) -> np.ndarray:
    """Indicators after step t. `req_units[s]` = units of the new request at step s."""
    out = np.zeros(len(NAMES))
    active = state.active
    if not active.any():
        return out  # D1

    avail = state.available
    out[0] = 1.0 - avail.sum() / state.total.sum()

    s = need[active].sum(axis=0)
    denom = s + avail
    out[1] = np.divide(s, denom, out=np.zeros(len(s)), where=denom > 0).mean()

    short = (need[active] > avail).sum(axis=0)
    out[2] = (short >= 2).mean()

    out[3] = state.waiting.sum() / active.sum()

    if t + 1 >= 2 * window:
        last = req_units[t - window + 1 : t + 1].sum()
        prev = req_units[t - 2 * window + 1 : t - window + 1].sum()
        out[4] = min(1.0, max(0.0, (last - prev) / (prev + EPS)))
    return out
