import numpy as np
import pytest

from pdw import banker
from pdw.state import InvalidStateError, SystemState, random_arbitrary_state

SIZES = [(1, 1), (5, 3), (10, 5), (25, 8), (50, 10)]


def small_state(**overrides):
    kw = dict(
        total=[10, 5, 7],
        available=[3, 3, 2],
        max_claim=[[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]],
        allocation=[[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]],
    )
    kw.update(overrides)
    return SystemState(**kw)


# ----------------------------------------------------------- random states


@pytest.mark.parametrize("n,m", SIZES)
def test_random_state_is_valid_and_safe(n, m):
    for seed in range(40):
        s = SystemState.random(n, m, np.random.default_rng(seed))
        s.validate()
        assert s.n == n and s.m == m
        assert banker.state_is_safe(s)[0]
        assert not s.waiting.any() and not s.finished.any()
        assert (s.need.sum(axis=1) > 0).all(), "every process starts with remaining need"


def test_random_state_deterministic_by_seed():
    a = SystemState.random(25, 8, np.random.default_rng(123))
    b = SystemState.random(25, 8, np.random.default_rng(123))
    c = SystemState.random(25, 8, np.random.default_rng(124))
    for name in ("total", "available", "max_claim", "allocation"):
        assert np.array_equal(getattr(a, name), getattr(b, name))
    assert not np.array_equal(a.max_claim, c.max_claim)


def test_tightness_respects_upper_bound():
    cfg = {"tightness": (1.2, 1.5)}
    for seed in range(20):
        s = SystemState.random(20, 5, np.random.default_rng(seed), cfg)
        # flooring and capping only lower it; the at-least-one-unit rule can add <= n units
        assert (s.max_claim.sum(axis=0) <= 1.5 * s.total + s.n).all()


def test_A3_unsafe_initial_state_raises_after_max_attempts(monkeypatch):
    monkeypatch.setattr(banker, "is_safe", lambda *a, **k: (False, []))
    with pytest.raises(RuntimeError, match="no safe initial state"):
        SystemState.random(5, 3, np.random.default_rng(0), {"max_attempts": 7})


@pytest.mark.parametrize("n,m", SIZES)
def test_arbitrary_states_are_valid(n, m):
    rng = np.random.default_rng(99)
    for _ in range(50):
        random_arbitrary_state(n, m, rng).validate()


# ------------------------------------------------------------- invariants


def test_textbook_state_valid():
    s = small_state()
    assert s.n == 5 and s.m == 3
    assert np.array_equal(s.need[1], [1, 2, 2])


def test_A5_conservation_violation_rejected():
    with pytest.raises(InvalidStateError, match="conservation"):
        small_state(available=[3, 3, 3])


def test_A5_conservation_checked_after_mutation():
    s = small_state()
    s.available[0] -= 1
    with pytest.raises(InvalidStateError, match="conservation"):
        s.validate()


def test_A6_finished_process_holding_resources_rejected():
    with pytest.raises(InvalidStateError, match="finished process still holds"):
        small_state(finished=[False, True, False, False, False])


def test_finished_process_has_zero_need():
    s = small_state(
        available=[5, 3, 2],
        allocation=[[0, 1, 0], [0, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]],
        finished=[False, True, False, False, False],
    )
    assert not s.need[1].any()


def test_D3_zero_unit_resource_rejected():
    with pytest.raises(InvalidStateError, match="at least 1 unit"):
        SystemState(total=[0, 2], available=[0, 2], max_claim=[[0, 1]], allocation=[[0, 0]])


@pytest.mark.parametrize(
    "overrides,match",
    [
        ({"allocation": [[8, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]], "available": [-5, 3, 2]},
         "negative"),
        ({"max_claim": [[7, 5, 3], [3, 2, 2], [11, 0, 2], [2, 2, 2], [4, 3, 3]]}, "exceeds total"),
        ({"max_claim": [[7, 5, 3], [1, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]]}, "allocation exceeds max_claim"),
    ],
)
def test_bad_arrays_rejected(overrides, match):
    with pytest.raises(InvalidStateError, match=match):
        small_state(**overrides)


def test_C2_pending_exceeding_need_rejected():
    pending = np.zeros((5, 3), int)
    pending[1] = [2, 0, 0]  # need[1] = [1, 2, 2]
    with pytest.raises(InvalidStateError, match="exceeds remaining need"):
        small_state(waiting=[False, True, False, False, False], pending=pending,
                    wait_since=[-1, 0, -1, -1, -1])


def test_C2_pending_on_non_waiting_process_rejected():
    pending = np.zeros((5, 3), int)
    pending[1] = [1, 0, 0]
    with pytest.raises(InvalidStateError, match="non-waiting process has a pending"):
        small_state(pending=pending)


def test_waiting_process_needs_nonzero_pending_and_wait_since():
    with pytest.raises(InvalidStateError, match="zero pending"):
        small_state(waiting=[False, True, False, False, False], wait_since=[-1, 0, -1, -1, -1])
    pending = np.zeros((5, 3), int)
    pending[1] = [1, 0, 0]
    with pytest.raises(InvalidStateError, match="wait_since"):
        small_state(waiting=[False, True, False, False, False], pending=pending)


def test_finished_process_cannot_wait():
    pending = np.zeros((5, 3), int)
    with pytest.raises(InvalidStateError):
        small_state(
            available=[5, 3, 2],
            allocation=[[0, 1, 0], [0, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]],
            finished=[False, True, False, False, False],
            waiting=[False, True, False, False, False],
            pending=pending, wait_since=[-1, 0, -1, -1, -1],
        )


def test_copy_is_independent():
    s = small_state()
    c = s.copy()
    c.available[0] = 99
    c.allocation[0, 0] = 5
    assert s.available[0] == 3 and s.allocation[0, 0] == 0
