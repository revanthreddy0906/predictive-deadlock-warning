"""Observer-mode simulator: every valid request is granted, Banker's only observes.

One step (fix C5):
    1. retry waiting processes, FIFO by wait-start step: grant those that now fit;
       processes whose claim is now fully met finish, and the retry repeats with the
       released units until nothing changes
    2. draw one new request; GRANT (allocate) or WAIT (block, store pending)
    3. processes whose need reached zero finish and release everything
    4. optional voluntary partial release (scenario.release_prob)
    5. record unsafe[t], deadlocked[t], indicators[t] (and lookahead[t] if enabled)

Deadlock detection is event-driven (fix C1): it reruns only when the waiting set or a
pending request changed; otherwise its previous result is still exact.

Sequences end with end_reason in {"max_steps", "deadlock", "all_finished"}.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from pdw import banker, indicators
from pdw.banker import Decision
from pdw.scenarios import make_scenario, scenario_cfg
from pdw.state import SystemState

SCENARIO_IDS = {"normal": 0, "spike": 1, "deadlock_prone": 2}

# Extra per-step measurements for the full paper (computed when extras=True):
#   margin            1 - safety_margin: share of free units that cannot be removed safely
#   approx_lookahead  top-k (k=3) approximate lookahead
#   need_pressure_noisy, contention_noisy
#                     the two claim-based indicators computed from misdeclared claims
#                     (each max_claim[i, j] scaled by U(1 - noise, 1 + noise), fixed per run)
EXTRAS = ("margin", "approx_lookahead", "need_pressure_noisy", "contention_noisy")
CLAIM_NOISE = 0.2


def _complete(state: SystemState) -> None:
    """Processes whose need reached zero finish and release everything (test-matrix row C1)."""
    done = state.active & ~state.waiting & (state.allocation == state.max_claim).all(axis=1)
    if done.any():
        state.available += state.allocation[done].sum(axis=0)
        state.allocation[done] = 0
        state.finished |= done


def _retry_pending(state: SystemState) -> bool:
    """Grant pending requests that now fit, FIFO by wait-start step (B7). True if any."""
    waiters = np.flatnonzero(state.waiting)
    granted = False
    for i in waiters[np.lexsort((waiters, state.wait_since[waiters]))]:
        req = state.pending[i]
        if (req <= state.available).all():
            state.allocation[i] += req
            state.available -= req
            state.pending[i] = 0
            state.waiting[i] = False
            state.wait_since[i] = -1
            granted = True
    return granted


def sequence_rng(seed: int, scenario: str, n: int, m: int) -> np.random.Generator:
    """Independent stream per (seed, scenario, size) (fix C4)."""
    return np.random.default_rng(np.random.SeedSequence([seed, SCENARIO_IDS[scenario], n, m]))


@dataclass
class SequenceResult:
    scenario: str
    n: int
    m: int
    seed: int
    T: int                          # number of recorded steps
    end_reason: str
    indicators: np.ndarray          # (T, 5) float32
    unsafe: np.ndarray              # (T,) bool
    deadlocked: np.ndarray          # (T,) bool
    n_waiting: np.ndarray           # (T,) int16
    req_units: np.ndarray           # (T,) int32, units of the new request
    lookahead: np.ndarray | None    # (T,) float32 or None
    in_spike: np.ndarray            # (T,) bool
    extras: np.ndarray | None = None  # (T, len(EXTRAS)) float32 or None
    exceeds_need: int = 0
    runtime: float = 0.0
    safety_time: float = 0.0
    safety_calls: int = 0
    detect_time: float = 0.0
    detect_calls: int = 0
    lookahead_time: float = 0.0
    extras_time: float = 0.0
    margin_time: float = 0.0
    approx_time: float = 0.0
    tightness: float = 0.0
    trace: dict | None = field(default=None, repr=False)


def simulate(
    scenario: str,
    n: int,
    m: int,
    seed: int,
    steps: int,
    window: int = 10,
    overrides: dict | None = None,
    lookahead: bool = False,
    store_trace: bool = False,
    debug: bool = False,
    extras: bool = False,
) -> SequenceResult:
    t_start = time.perf_counter()
    rng = sequence_rng(seed, scenario, n, m)
    cfg = scenario_cfg(scenario, overrides)
    state = SystemState.random(n, m, rng, cfg["state"])
    gen = make_scenario(scenario, cfg, n, m, rng)

    ind = np.zeros((steps, len(indicators.NAMES)), np.float32)
    unsafe = np.zeros(steps, bool)
    dead = np.zeros(steps, bool)
    n_wait = np.zeros(steps, np.int16)
    req_units = np.zeros(steps, np.int32)
    in_spike = np.zeros(steps, bool)
    look = np.full(steps, np.nan, np.float32) if lookahead else None
    ext = np.full((steps, len(EXTRAS)), np.nan, np.float32) if extras else None
    if extras:
        # Separate stream so the simulated workload is identical with or without extras.
        noise_rng = np.random.default_rng(np.random.SeedSequence([seed, SCENARIO_IDS[scenario], n, m, 104729]))
        perceived_claim = np.rint(state.max_claim * noise_rng.uniform(1 - CLAIM_NOISE, 1 + CLAIM_NOISE,
                                                                       size=(n, m))).astype(np.int64)
    trace = {"available": [], "allocation": [], "waiting": []} if store_trace else None

    res = SequenceResult(scenario, n, m, seed, 0, "max_steps", ind, unsafe, dead, n_wait,
                         req_units, look, in_spike, ext, tightness=float(state.tightness().mean()))
    deadlocked = False
    dirty = False  # waiting set / pending changed since last detection run
    T = steps

    for t in range(steps):
        # 1. FIFO retry of waiting processes; completions free units, so repeat
        while state.waiting.any() and _retry_pending(state):
            dirty = True
            _complete(state)

        need = state.need
        # 2. new request
        draw = gen.request(state, need, t, rng)
        if draw is None:
            if state.waiting.any():
                # Every active process waits and nothing fits: must already be deadlocked.
                raise AssertionError("generator exhausted with waiting processes but no deadlock")
            T, res.end_reason = t, "all_finished"
            break
        pid, req = draw
        in_spike[t] = gen.in_spike(t)
        decision = banker.check_request(state, pid, req)
        if decision is Decision.GRANT:
            state.allocation[pid] += req
            state.available -= req
            req_units[t] = req.sum()
        elif decision is Decision.WAIT:
            state.waiting[pid] = True
            state.pending[pid] = req
            state.wait_since[pid] = t
            req_units[t] = req.sum()
            dirty = True
        else:
            res.exceeds_need += 1  # B2: logged and skipped

        # 3. completions
        _complete(state)

        # 4. voluntary partial release
        if gen.release_prob and rng.random() < gen.release_prob:
            holders = np.flatnonzero(state.active & ~state.waiting & (state.allocation.sum(axis=1) > 0))
            if holders.size:
                i = int(rng.choice(holders))
                rel = np.floor(state.allocation[i] * rng.random(m) * gen.release_frac).astype(np.int64)
                state.allocation[i] -= rel
                state.available += rel

        # 5. observe
        need = state.need
        active = state.active
        t0 = time.perf_counter()
        safe, _ = banker.is_safe(state.available, state.allocation, need, active)
        res.safety_time += time.perf_counter() - t0
        res.safety_calls += 1
        unsafe[t] = not safe

        if dirty:
            t0 = time.perf_counter()
            deadlocked = banker.is_deadlocked(state)[0]
            res.detect_time += time.perf_counter() - t0
            res.detect_calls += 1
            dirty = False
        if debug:
            state.validate()
            assert deadlocked == banker.is_deadlocked(state)[0], "event-driven detection drifted"
            assert not (deadlocked and safe), "safe and deadlocked"
        dead[t] = deadlocked
        n_wait[t] = state.waiting.sum()
        ind[t] = indicators.compute(state, need, req_units, t, window)

        if lookahead and safe:
            t0 = time.perf_counter()
            look[t] = banker.lookahead_fraction(state.available, state.allocation, need, active,
                                                active & ~state.waiting)
            res.lookahead_time += time.perf_counter() - t0
        if extras:
            t0 = time.perf_counter()
            if safe:
                running = active & ~state.waiting
                t1 = time.perf_counter()
                ext[t, 0] = 1.0 - banker.safety_margin(state.available, state.allocation, need, active)
                t2 = time.perf_counter()
                ext[t, 1] = banker.lookahead_topk(state.available, state.allocation, need, active, running)
                res.margin_time += t2 - t1
                res.approx_time += time.perf_counter() - t2
            noisy_need = np.clip(perceived_claim - state.allocation, 0, None)
            noisy_need[state.finished] = 0
            noisy = indicators.compute(state, noisy_need, req_units, t, window)
            ext[t, 2], ext[t, 3] = noisy[1], noisy[2]
            res.extras_time += time.perf_counter() - t0
        if store_trace:
            trace["available"].append(state.available.copy())
            trace["allocation"].append(state.allocation.copy())
            trace["waiting"].append(state.waiting.copy())

        if deadlocked:
            T, res.end_reason = t + 1, "deadlock"
            break
        if not state.active.any():
            T, res.end_reason = t + 1, "all_finished"
            break

    res.T = T
    for name in ("indicators", "unsafe", "deadlocked", "n_waiting", "req_units", "in_spike"):
        setattr(res, name, getattr(res, name)[:T])
    if look is not None:
        res.lookahead = look[:T]
    if ext is not None:
        res.extras = ext[:T]
    if store_trace:
        res.trace = {k: np.array(v) for k, v in trace.items()}
    res.runtime = time.perf_counter() - t_start
    return res
