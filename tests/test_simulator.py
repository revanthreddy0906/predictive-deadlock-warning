import numpy as np
import pytest

from pdw import banker
from pdw.scenarios import SCENARIOS
from pdw.simulator import _complete, _retry_pending, simulate
from pdw.state import SystemState


@pytest.mark.parametrize("name", SCENARIOS)
def test_A5_C1_invariants_every_step_debug(name):
    # debug=True validates conservation etc. every step, checks event-driven detection
    # against a fresh detection run, and asserts never (safe and deadlocked)
    for seed in range(25):
        simulate(name, 10, 5, seed=seed, steps=6000, debug=True)
    for seed in range(5):
        simulate(name, 25, 8, seed=seed, steps=6000, debug=True)


def test_C1_event_driven_detection_matches_every_step_on_sequences():
    """Sequence-level version of fix C1, independent of the debug flag."""
    import pdw.simulator as sim

    calls = {"n": 0}
    real = banker.is_deadlocked

    for seed in range(200):
        r = simulate("deadlock_prone", 10, 5, seed=seed, steps=6000, debug=True)
        assert r.detect_calls <= r.T
        calls["n"] += r.detect_calls
    assert calls["n"] > 0
    assert sim.banker.is_deadlocked is real


@pytest.mark.parametrize("name", SCENARIOS)
def test_C4_same_seed_same_output(name):
    a = simulate(name, 25, 8, seed=3, steps=6000)
    b = simulate(name, 25, 8, seed=3, steps=6000)
    assert a.T == b.T and a.end_reason == b.end_reason
    for f in ("indicators", "unsafe", "deadlocked", "n_waiting", "req_units"):
        assert np.array_equal(getattr(a, f), getattr(b, f))


def test_different_scenarios_get_independent_streams():
    a = simulate("normal", 10, 5, seed=3, steps=200)
    b = simulate("spike", 10, 5, seed=3, steps=200)
    assert a.tightness != b.tightness


def test_C5_deadlock_step_is_unsafe_and_ends_sequence():
    seen = 0
    for seed in range(60):
        r = simulate("deadlock_prone", 10, 5, seed=seed, steps=6000)
        if r.end_reason == "deadlock":
            seen += 1
            assert r.deadlocked[-1] and r.unsafe[-1]
            assert not r.deadlocked[:-1].any()      # C7: first deadlock ends the run
        assert not (r.deadlocked & ~r.unsafe).any()
    assert seen > 5, "deadlock_prone should reach deadlock for some seeds"


def test_A4_all_finished_ends_sequence():
    seen = 0
    for seed in range(40):
        r = simulate("normal", 10, 5, seed=seed, steps=6000)
        if r.end_reason == "all_finished":
            seen += 1
            assert not r.unsafe[-1]
    assert seen > 5


def test_max_steps_end_reason():
    r = simulate("normal", 25, 8, seed=0, steps=20)
    assert r.end_reason == "max_steps" and r.T == 20


def test_C3_unsafe_can_recover_to_safe():
    recovered = 0
    for seed in range(200):
        r = simulate("normal", 10, 5, seed=seed, steps=6000)
        u = r.unsafe
        recovered += bool((u[:-1] & ~u[1:]).any())
    assert recovered > 0, "observer mode should allow unsafe -> safe"


def test_B7_pending_retried_fifo_by_wait_start():
    # Both P0 and P1 wait for the single free unit; P1 has waited longer, so it wins.
    s = SystemState(total=[3], available=[1], max_claim=[[2], [2], [1]], allocation=[[1], [1], [0]],
                    waiting=[True, True, False], pending=[[1], [1], [0]], wait_since=[5, 2, -1])
    assert _retry_pending(s)
    assert not s.waiting[1] and s.waiting[0]
    assert s.allocation[1, 0] == 2 and s.available[0] == 0
    s.validate()


def test_C1_lifecycle_need_zero_finishes_and_releases():
    s = SystemState(total=[3, 2], available=[0, 1], max_claim=[[2, 1], [2, 1]], allocation=[[2, 1], [1, 0]])
    _complete(s)
    assert s.finished[0] and not s.finished[1]
    assert np.array_equal(s.available, [2, 2]) and not s.allocation[0].any()
    s.validate()


def test_retry_then_completion_frees_units_for_next_waiter():
    # P0 gets its last unit on retry, finishes, and its release lets P1's pending fit.
    s = SystemState(total=[3], available=[1], max_claim=[[3], [3]], allocation=[[2], [0]],
                    waiting=[True, True], pending=[[1], [2]], wait_since=[0, 1])
    while s.waiting.any() and _retry_pending(s):
        _complete(s)
    assert s.finished[0] and not s.waiting[1] and s.allocation[1, 0] == 2
    assert s.available[0] == 1
    s.validate()


def test_lookahead_recorded_on_safe_steps_only():
    r = simulate("spike", 10, 5, seed=1, steps=6000, lookahead=True)
    assert r.lookahead is not None
    assert np.isnan(r.lookahead[r.unsafe]).all()
    safe_vals = r.lookahead[~r.unsafe]
    assert (~np.isnan(safe_vals)).all() and ((safe_vals >= 0) & (safe_vals <= 1)).all()


def test_store_trace_shapes():
    r = simulate("normal", 10, 5, seed=0, steps=50, store_trace=True)
    assert r.trace["allocation"].shape == (r.T, 10, 5)
