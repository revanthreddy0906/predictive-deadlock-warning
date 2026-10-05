import numpy as np
import pytest

from pdw import banker
from pdw.banker import Decision
from pdw.state import SystemState, random_arbitrary_state

N_RANDOM = 2000


def silberschatz():
    """Silberschatz 5x3 Banker's example: SAFE, e.g. <P1, P3, P4, P2, P0>."""
    return SystemState(
        total=[10, 5, 7],
        available=[3, 3, 2],
        max_claim=[[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]],
        allocation=[[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]],
    )


def grant(state, pid, req):
    req = np.asarray(req)
    state.allocation[pid] += req
    state.available -= req
    state.validate()


def silberschatz_unsafe():
    """Textbook follow-up: P1 requests (1,0,2) (safe), then P0 requests (0,2,0) -> UNSAFE."""
    s = silberschatz()
    grant(s, 1, [1, 0, 2])
    grant(s, 0, [0, 2, 0])
    return s


def detection_example(p2_extra_c=False):
    """Silberschatz detection example: 7 A, 2 B, 6 C, available (0,0,0).

    Requests: P0 (0,0,0), P1 (2,0,2), P2 (0,0,0), P3 (1,0,0), P4 (0,0,2).
    Not deadlocked. If P2 then requests one more C, P1..P4 are deadlocked.
    """
    allocation = [[0, 1, 0], [2, 0, 0], [3, 0, 3], [2, 1, 1], [0, 0, 2]]
    pending = [[0, 0, 0], [2, 0, 2], [0, 0, 0], [1, 0, 0], [0, 0, 2]]
    if p2_extra_c:
        pending[2] = [0, 0, 1]
    waiting = [any(r) for r in pending]
    max_claim = (np.array(allocation) + np.array(pending) + [[1, 0, 0]] * 5).clip(max=[7, 2, 6])
    return SystemState(
        total=[7, 2, 6], available=[0, 0, 0], max_claim=max_claim, allocation=allocation,
        waiting=waiting, pending=pending, wait_since=[0 if w else -1 for w in waiting],
    )


def random_states(seed=0, count=N_RANDOM):
    rng = np.random.default_rng(seed)
    for k in range(count):
        n = int(rng.integers(1, 15))
        m = int(rng.integers(1, 6))
        yield random_arbitrary_state(n, m, rng, wait_prob=float(rng.random()), finish_prob=0.15)


# --------------------------------------------------------------- A8 ground truth


def test_A8_silberschatz_is_safe_with_valid_order():
    s = silberschatz()
    for fn in (banker.is_safe, banker.is_safe_reference):
        safe, order = fn(s.available, s.allocation, s.need, s.active)
        assert safe
        assert banker.is_valid_safe_order(s.available, s.allocation, s.need, s.active, order)
    # the textbook sequence is valid too
    assert banker.is_valid_safe_order(s.available, s.allocation, s.need, s.active, [1, 3, 4, 2, 0])


def test_known_unsafe_example():
    s = silberschatz_unsafe()
    assert np.array_equal(s.available, [2, 1, 0])
    assert not banker.state_is_safe(s)[0]
    assert not banker.is_safe_reference(s.available, s.allocation, s.need, s.active)[0]


def test_A2_unsafe_but_not_deadlocked():
    s = silberschatz_unsafe()
    assert not banker.state_is_safe(s)[0]
    assert banker.is_deadlocked(s) == (False, frozenset())


def test_A8_detection_example_not_deadlocked():
    s = detection_example()
    for fn in (banker.detect_deadlock, banker.detect_deadlock_reference):
        assert fn(s.available, s.allocation, s.pending, s.active) == (False, frozenset())


def test_A8_detection_example_deadlocked_after_p2_requests_c():
    s = detection_example(p2_extra_c=True)
    expected = (True, frozenset({1, 2, 3, 4}))
    assert banker.is_deadlocked(s) == expected
    assert banker.detect_deadlock_reference(s.available, s.allocation, s.pending, s.active) == expected
    assert not banker.state_is_safe(s)[0]  # A1 / C5 on a concrete case


# ----------------------------------------------------------------- A4, edge cases


def test_A4_all_finished_is_safe_and_not_deadlocked():
    s = SystemState(total=[3, 2], available=[3, 2], max_claim=[[1, 1], [2, 0]],
                    allocation=[[0, 0], [0, 0]], finished=[True, True])
    assert banker.state_is_safe(s) == (True, [])
    assert banker.is_deadlocked(s) == (False, frozenset())


def test_finished_processes_ignored_by_safety_check():
    # P1 is finished; its stale claim would otherwise make the state unsafe
    s = SystemState(total=[4], available=[2], max_claim=[[3], [4]], allocation=[[2], [0]],
                    finished=[False, True])
    assert banker.state_is_safe(s) == (True, [0])


def test_waiting_process_holding_nothing_is_not_deadlocked():
    # Silberschatz convention: a process with zero allocation starts as finished
    s = SystemState(total=[2], available=[0], max_claim=[[2], [2]], allocation=[[2], [0]],
                    waiting=[False, True], pending=[[0], [1]], wait_since=[-1, 0])
    assert banker.is_deadlocked(s) == (False, frozenset())


# ------------------------------------------------------- A7 vectorised == reference


def test_A7_vectorised_safety_matches_reference():
    n_unsafe = 0
    for s in random_states(seed=1):
        args = (s.available, s.allocation, s.need, s.active)
        safe_v, order_v = banker.is_safe(*args)
        safe_r, order_r = banker.is_safe_reference(*args)
        assert safe_v == safe_r
        if safe_v:
            assert banker.is_valid_safe_order(*args, order_v)
            assert banker.is_valid_safe_order(*args, order_r)
        n_unsafe += not safe_v
    assert 0.1 * N_RANDOM < n_unsafe < 0.9 * N_RANDOM, "random states should mix safe/unsafe"


def test_vectorised_detection_matches_reference():
    for s in random_states(seed=2):
        args = (s.available, s.allocation, s.pending, s.active)
        assert banker.detect_deadlock(*args) == banker.detect_deadlock_reference(*args)


# ------------------------------------------------------ A1 deadlocked => unsafe


def test_A1_deadlocked_implies_unsafe_property():
    n_deadlocked = 0
    for s in random_states(seed=3):
        deadlocked, pids = banker.is_deadlocked(s)
        if deadlocked:
            n_deadlocked += 1
            assert not banker.state_is_safe(s)[0], "safe AND deadlocked is impossible"
            assert all(s.waiting[i] for i in pids), "only waiting processes can be deadlocked"
    assert n_deadlocked >= 50, f"property test is vacuous ({n_deadlocked} deadlocked states)"


# ---------------------------------------------------------------- requests (B)


def test_request_grant():
    assert banker.check_request(silberschatz(), 1, [1, 0, 2]) == Decision.GRANT


def test_B3_request_within_need_but_over_available_waits():
    # need[0] = (7,4,3), available = (3,3,2)
    assert banker.check_request(silberschatz(), 0, [4, 0, 0]) == Decision.WAIT


def test_B2_request_over_need_flagged():
    # need[3] = (0,1,1)
    assert banker.check_request(silberschatz(), 3, [1, 0, 0]) == Decision.EXCEEDS_NEED


def test_B4_request_that_makes_state_unsafe_is_still_granted():
    s = silberschatz()
    grant(s, 1, [1, 0, 2])
    assert banker.state_is_safe(s)[0]
    assert banker.check_request(s, 0, [0, 2, 0]) == Decision.GRANT  # observer mode
    grant(s, 0, [0, 2, 0])
    assert not banker.state_is_safe(s)[0]


@pytest.mark.parametrize("req", [[0, 0, 0], [-1, 1, 0]])
def test_B1_zero_or_negative_request_rejected(req):
    with pytest.raises(ValueError, match="non-zero"):
        banker.check_request(silberschatz(), 1, req)


def test_request_wrong_shape_rejected():
    with pytest.raises(ValueError, match="shape"):
        banker.check_request(silberschatz(), 1, [1, 0])


def test_B5_waiting_process_cannot_request():
    s = detection_example()
    with pytest.raises(ValueError, match="waiting"):
        banker.check_request(s, 1, [1, 0, 0])


def test_B6_finished_process_cannot_request():
    s = SystemState(total=[3], available=[3], max_claim=[[2]], allocation=[[0]], finished=[True])
    with pytest.raises(ValueError, match="finished"):
        banker.check_request(s, 0, [1])


# ---------------------- C1: detection only changes with the waiting set / pending


def test_C1_running_process_changes_never_change_detection():
    """Grants to, partial releases by, or completion of a non-waiting process only move
    units between `available` and that process's allocation, which detection hands back
    anyway. So the detection result must be identical before and after."""
    rng = np.random.default_rng(4)
    checked = 0
    for s in random_states(seed=5):
        running = np.flatnonzero(s.active & ~s.waiting)
        if running.size == 0:
            continue
        before = banker.is_deadlocked(s)
        i = rng.choice(running)
        kind = rng.integers(3)
        if kind == 0:  # grant within need and available
            req = np.floor(np.minimum(s.need[i], s.available) * rng.random(s.m)).astype(np.int64)
            s.allocation[i] += req
            s.available -= req
        elif kind == 1:  # voluntary partial release
            rel = np.floor(s.allocation[i] * rng.random(s.m)).astype(np.int64)
            s.allocation[i] -= rel
            s.available += rel
        else:  # completion: release everything
            s.available += s.allocation[i]
            s.allocation[i] = 0
            s.finished[i] = True
        s.validate()
        assert banker.is_deadlocked(s) == before
        checked += 1
    assert checked > 1000
