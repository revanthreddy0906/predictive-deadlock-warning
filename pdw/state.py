"""System state model: resources, claims, allocations, waiting and finished processes.

All arrays are int64. Shapes: n processes, m resource types.

    total      (m,)    units of each resource type (each >= 1)
    available  (m,)    units not held by anyone
    max_claim  (n, m)  most units a process may ever hold
    allocation (n, m)  units currently held
    waiting    (n,)    process is blocked on a pending request
    pending    (n, m)  the blocked request (zero when not waiting)
    wait_since (n,)    step at which the process started waiting (-1 when not waiting)
    finished   (n,)    process completed and released everything
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

DEFAULT_RANDOM_CFG = {
    # total_j is drawn uniformly from [lo * n, hi * n] (at least 1)
    "total_per_process": (1.0, 3.0),
    # tightness_j = sum_i max_claim[i, j] / total_j (main calibration knob, fix C3)
    "tightness": (1.5, 3.0),
    # each process initially holds up to this fraction of its max claim
    "init_alloc_frac": (0.0, 0.5),
    "max_attempts": 1000,
}


class InvalidStateError(ValueError):
    """A state invariant is violated."""


def _arr(x, ndim: int, dtype) -> np.ndarray:
    a = np.array(x, dtype=dtype, copy=True)
    if a.ndim != ndim:
        raise InvalidStateError(f"expected {ndim}-d array, got shape {a.shape}")
    return a


@dataclass
class SystemState:
    total: np.ndarray
    available: np.ndarray
    max_claim: np.ndarray
    allocation: np.ndarray
    waiting: np.ndarray = None
    pending: np.ndarray = None
    wait_since: np.ndarray = None
    finished: np.ndarray = None
    _validate: bool = field(default=True, repr=False)

    def __post_init__(self):
        self.total = _arr(self.total, 1, np.int64)
        self.available = _arr(self.available, 1, np.int64)
        self.max_claim = _arr(self.max_claim, 2, np.int64)
        self.allocation = _arr(self.allocation, 2, np.int64)
        n = self.max_claim.shape[0]
        m = self.total.shape[0]
        self.waiting = np.zeros(n, bool) if self.waiting is None else _arr(self.waiting, 1, bool)
        self.pending = np.zeros((n, m), np.int64) if self.pending is None else _arr(self.pending, 2, np.int64)
        self.wait_since = (
            np.full(n, -1, np.int64) if self.wait_since is None else _arr(self.wait_since, 1, np.int64)
        )
        self.finished = np.zeros(n, bool) if self.finished is None else _arr(self.finished, 1, bool)
        if self._validate:
            self.validate()

    # ------------------------------------------------------------------ views

    @property
    def n(self) -> int:
        return self.max_claim.shape[0]

    @property
    def m(self) -> int:
        return self.total.shape[0]

    @property
    def active(self) -> np.ndarray:
        """Processes that have not finished."""
        return ~self.finished

    @property
    def need(self) -> np.ndarray:
        """Remaining claim, max_claim - allocation; zero for finished processes."""
        need = self.max_claim - self.allocation
        need[self.finished] = 0
        return need

    def tightness(self) -> np.ndarray:
        """Per-resource claim tightness: sum of max claims / total units."""
        return self.max_claim.sum(axis=0) / self.total

    def copy(self) -> "SystemState":
        return SystemState(
            self.total, self.available, self.max_claim, self.allocation,
            self.waiting, self.pending, self.wait_since, self.finished, _validate=False,
        )

    # ------------------------------------------------------------- invariants

    def validate(self) -> None:
        """Raise InvalidStateError if any invariant is violated."""
        n, m = self.n, self.m

        def fail(msg):
            raise InvalidStateError(msg)

        shapes = {
            "available": (self.available.shape, (m,)),
            "allocation": (self.allocation.shape, (n, m)),
            "pending": (self.pending.shape, (n, m)),
            "waiting": (self.waiting.shape, (n,)),
            "wait_since": (self.wait_since.shape, (n,)),
            "finished": (self.finished.shape, (n,)),
        }
        for name, (got, want) in shapes.items():
            if got != want:
                fail(f"{name} has shape {got}, expected {want}")

        if n < 1 or m < 1:
            fail("need at least one process and one resource type")
        if (self.total < 1).any():
            fail("every resource type must have at least 1 unit")
        for name in ("available", "max_claim", "allocation", "pending"):
            if (getattr(self, name) < 0).any():
                fail(f"{name} has negative entries")
        if (self.max_claim > self.total).any():
            fail("max_claim exceeds total units")
        if (self.allocation > self.max_claim).any():
            fail("allocation exceeds max_claim")
        if not np.array_equal(self.available + self.allocation.sum(axis=0), self.total):
            fail("conservation violated: available + sum(allocation) != total")

        if self.allocation[self.finished].any():
            fail("finished process still holds resources")
        if (self.waiting & self.finished).any():
            fail("finished process is waiting")

        # fix C2: pending <= need for waiting processes, zero otherwise
        if self.pending[~self.waiting].any():
            fail("non-waiting process has a pending request")
        need = self.max_claim - self.allocation
        if (self.pending[self.waiting] > need[self.waiting]).any():
            fail("pending request exceeds remaining need")
        if (self.pending[self.waiting].sum(axis=1) == 0).any():
            fail("waiting process has a zero pending request")
        if (self.wait_since[self.waiting] < 0).any() or (self.wait_since[~self.waiting] != -1).any():
            fail("wait_since inconsistent with waiting")

    # -------------------------------------------------------------- generator

    @classmethod
    def random(cls, n: int, m: int, rng: np.random.Generator, cfg: dict | None = None) -> "SystemState":
        """Random valid initial state that is SAFE under Banker's algorithm.

        Regenerates until safe; raises RuntimeError after cfg['max_attempts'] tries.
        Nobody is waiting or finished, and every process has non-zero remaining need.
        """
        from pdw import banker  # local import: banker imports this module

        cfg = {**DEFAULT_RANDOM_CFG, **(cfg or {})}
        for _ in range(int(cfg["max_attempts"])):
            state = cls._draw(n, m, rng, cfg)
            safe, _ = banker.is_safe(state.available, state.allocation, state.need, state.active)
            if safe:
                return state
        raise RuntimeError(f"no safe initial state after {cfg['max_attempts']} attempts")

    @classmethod
    def _draw(cls, n: int, m: int, rng: np.random.Generator, cfg: dict) -> "SystemState":
        lo, hi = cfg["total_per_process"]
        total = np.maximum(1, np.rint(rng.uniform(lo * n, hi * n, size=m))).astype(np.int64)

        # Spread tightness_j * total_j claim units across processes, capped at total_j.
        tight = rng.uniform(*cfg["tightness"], size=m)
        weights = rng.random((n, m)) + 1e-9
        weights /= weights.sum(axis=0)
        max_claim = np.floor(weights * tight * total).astype(np.int64)
        max_claim = np.minimum(max_claim, total)
        # Every process claims at least one unit somewhere.
        for i in np.flatnonzero(max_claim.sum(axis=1) == 0):
            max_claim[i, rng.integers(m)] = 1

        frac = rng.uniform(*cfg["init_alloc_frac"], size=(n, 1))
        allocation = np.floor(max_claim * frac * rng.random((n, m))).astype(np.int64)
        # Scale down columns that over-allocate.
        col = allocation.sum(axis=0)
        over = col > total
        if over.any():
            scale = np.where(over, total / np.maximum(col, 1), 1.0)
            allocation = np.floor(allocation * scale).astype(np.int64)
        # Every process must still need something (otherwise it is already done).
        for i in np.flatnonzero((max_claim - allocation).sum(axis=1) == 0):
            j = rng.choice(np.flatnonzero(allocation[i]))
            allocation[i, j] -= 1

        available = total - allocation.sum(axis=0)
        return cls(total, available, max_claim, allocation)


def random_arbitrary_state(
    n: int, m: int, rng: np.random.Generator, wait_prob: float = 0.5, finish_prob: float = 0.1
) -> SystemState:
    """Random *valid but not necessarily safe* state, including waiting and finished
    processes. Used by property tests (A1, A7); never by experiments.

    Waiting processes hold a pending request <= need that does not fit `available`
    (otherwise the retry step would have granted it).
    """
    total = rng.integers(1, 3 * n + 2, size=m)
    max_claim = np.minimum(rng.integers(0, total + 1, size=(n, m)), total)
    allocation = np.floor(max_claim * rng.random((n, m))).astype(np.int64)
    finished = rng.random(n) < finish_prob
    allocation[finished] = 0
    col = allocation.sum(axis=0)
    over = col > total
    if over.any():
        allocation = np.floor(allocation * np.where(over, total / np.maximum(col, 1), 1.0)).astype(np.int64)
    available = total - allocation.sum(axis=0)

    need = max_claim - allocation
    waiting = np.zeros(n, bool)
    pending = np.zeros((n, m), np.int64)
    for i in range(n):
        if finished[i] or rng.random() >= wait_prob:
            continue
        blockers = np.flatnonzero(need[i] > available)
        if blockers.size == 0:
            continue
        req = np.floor(need[i] * rng.random(m)).astype(np.int64)
        j = rng.choice(blockers)
        req[j] = rng.integers(available[j] + 1, need[i, j] + 1)  # make it not fit
        waiting[i] = True
        pending[i] = req
    wait_since = np.where(waiting, 0, -1)
    return SystemState(total, available, max_claim, allocation, waiting, pending, wait_since, finished)
