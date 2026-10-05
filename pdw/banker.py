"""Banker's safety check (vectorised + reference), request classification, deadlock detection.

Safety (pessimistic): every active process may still request its full remaining need.
Detection (optimistic): non-waiting processes will finish and release everything;
waiting processes need only their pending request to proceed.

Consequence: since pending <= need, deadlocked => unsafe (invariant A1).
"""

from __future__ import annotations

from enum import Enum

import numpy as np

from pdw.state import SystemState


class Decision(str, Enum):
    GRANT = "GRANT"
    WAIT = "WAIT"
    EXCEEDS_NEED = "EXCEEDS_NEED"


# ---------------------------------------------------------------- safety check


def is_safe(available, allocation, need, active) -> tuple[bool, list[int]]:
    """Vectorised Banker's safety check.

    Each pass finishes *all* unfinished active processes whose need fits `work` at once.
    Finishing only ever grows `work`, so this reaches the same verdict as the sequential
    textbook loop; the returned order is a valid safe sequence but may differ from it.
    Worst case n passes of O(n*m): Theta(m*n^2).
    """
    work = np.array(available, dtype=np.int64, copy=True)
    allocation = np.asarray(allocation)
    need = np.asarray(need)
    done = ~np.asarray(active, dtype=bool)
    order: list[int] = []
    while True:
        cand = ~done & (need <= work).all(axis=1)
        if not cand.any():
            break
        order.extend(np.flatnonzero(cand).tolist())
        work += allocation[cand].sum(axis=0)
        done |= cand
    return bool(done.all()), order


def is_safe_reference(available, allocation, need, active) -> tuple[bool, list[int]]:
    """Plain-loop textbook safety algorithm (Silberschatz). Slow; for tests only."""
    n, m = len(need), len(available)
    work = [int(x) for x in available]
    finish = [not bool(a) for a in active]
    order: list[int] = []
    progress = True
    while progress:
        progress = False
        for i in range(n):
            if finish[i]:
                continue
            if all(need[i][j] <= work[j] for j in range(m)):
                for j in range(m):
                    work[j] += int(allocation[i][j])
                finish[i] = True
                order.append(i)
                progress = True
    return all(finish), order


def is_valid_safe_order(available, allocation, need, active, order) -> bool:
    """True if `order` lists every active process once and each fits `work` when reached."""
    active = np.asarray(active, dtype=bool)
    if sorted(order) != np.flatnonzero(active).tolist():
        return False
    work = np.array(available, dtype=np.int64, copy=True)
    for i in order:
        if (np.asarray(need[i]) > work).any():
            return False
        work += np.asarray(allocation[i])
    return True


def state_is_safe(state: SystemState) -> tuple[bool, list[int]]:
    return is_safe(state.available, state.allocation, state.need, state.active)


# --------------------------------------------------------- request handling


def check_request(state: SystemState, pid: int, req) -> Decision:
    """Classify a new request (observer mode: never rejects for safety).

    EXCEEDS_NEED if any component exceeds the remaining need, else WAIT if any
    component exceeds available, else GRANT (even if the result is unsafe).
    """
    req = np.asarray(req, dtype=np.int64)
    if req.shape != (state.m,):
        raise ValueError(f"request shape {req.shape}, expected ({state.m},)")
    if (req < 0).any() or req.sum() == 0:
        raise ValueError("request must be non-negative and non-zero")
    if state.finished[pid]:
        raise ValueError(f"process {pid} has finished")
    if state.waiting[pid]:
        raise ValueError(f"process {pid} is waiting and cannot issue a new request")
    if (req > state.need[pid]).any():
        return Decision.EXCEEDS_NEED
    if (req > state.available).any():
        return Decision.WAIT
    return Decision.GRANT


# --------------------------------------------------------- deadlock detection


def detect_deadlock(available, allocation, request, active) -> tuple[bool, frozenset[int]]:
    """Vectorised textbook detection algorithm.

    `request[i]` is the outstanding request of process i (zero if running).
    Processes holding nothing start as finished (Silberschatz convention).
    Returns (deadlocked, set of deadlocked pids).
    """
    work = np.array(available, dtype=np.int64, copy=True)
    allocation = np.asarray(allocation)
    request = np.asarray(request)
    active = np.asarray(active, dtype=bool)
    done = ~active | (allocation.sum(axis=1) == 0)
    while True:
        cand = ~done & (request <= work).all(axis=1)
        if not cand.any():
            break
        work += allocation[cand].sum(axis=0)
        done |= cand
    stuck = frozenset(np.flatnonzero(~done).tolist())
    return bool(stuck), stuck


def detect_deadlock_reference(available, allocation, request, active) -> tuple[bool, frozenset[int]]:
    """Plain-loop textbook detection. Slow; for tests only."""
    n, m = len(request), len(available)
    work = [int(x) for x in available]
    finish = [(not bool(active[i])) or all(int(a) == 0 for a in allocation[i]) for i in range(n)]
    progress = True
    while progress:
        progress = False
        for i in range(n):
            if not finish[i] and all(request[i][j] <= work[j] for j in range(m)):
                for j in range(m):
                    work[j] += int(allocation[i][j])
                finish[i] = True
                progress = True
    stuck = frozenset(i for i in range(n) if not finish[i])
    return bool(stuck), stuck


def is_deadlocked(state: SystemState) -> tuple[bool, frozenset[int]]:
    """Deadlock detection on a state: waiting processes request `pending`,
    running processes request nothing (optimistic assumption)."""
    return detect_deadlock(state.available, state.allocation, state.pending, state.active)
