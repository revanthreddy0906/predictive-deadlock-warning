import numpy as np
import pytest

from pdw import indicators
from pdw.indicators import NAMES
from pdw.simulator import simulate
from pdw.state import SystemState, random_arbitrary_state

I = {name: i for i, name in enumerate(NAMES)}


def compute(state, req_units=None, t=0, window=10):
    req_units = np.zeros(100, np.int32) if req_units is None else req_units
    return indicators.compute(state, state.need, req_units, t, window)


def test_D1_no_active_processes_all_zero():
    s = SystemState(total=[3], available=[3], max_claim=[[2]], allocation=[[0]], finished=[True])
    assert not compute(s).any()


def test_D6_all_resources_free():
    s = SystemState(total=[4, 4], available=[4, 4], max_claim=[[2, 2], [2, 2]], allocation=[[0, 0], [0, 0]])
    ind = compute(s)
    assert ind[I["scarcity"]] == 0.0
    assert ind[I["need_pressure"]] == pytest.approx(0.5)   # S_j = 4, available = 4
    assert ind[I["contention"]] == 0.0
    assert ind[I["waiting_ratio"]] == 0.0


def test_D6_all_exhausted_and_D2_no_division_by_zero():
    s = SystemState(total=[4, 2], available=[0, 0], max_claim=[[4, 2], [4, 2]], allocation=[[2, 1], [2, 1]],
                    waiting=[True, False], pending=[[1, 0], [0, 0]], wait_since=[0, -1])
    ind = compute(s)
    assert ind[I["scarcity"]] == 1.0
    assert ind[I["need_pressure"]] == 1.0
    assert ind[I["contention"]] == 1.0      # both processes short on both resources
    assert ind[I["waiting_ratio"]] == 0.5


def test_hand_computed_small_state():
    # Silberschatz 5x3: available (3,3,2), total (10,5,7)
    s = SystemState(total=[10, 5, 7], available=[3, 3, 2],
                    max_claim=[[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]],
                    allocation=[[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]])
    ind = compute(s)
    assert ind[I["scarcity"]] == pytest.approx(1 - 8 / 22)
    S = np.array([18, 10, 7])  # column sums of need
    assert ind[I["need_pressure"]] == pytest.approx(np.mean(S / (S + [3, 3, 2])))
    # need > available: R0 by P0, P2, P4 (>=2) | R1 by P0 (1) | R2 by P0 (1)
    assert ind[I["contention"]] == pytest.approx(1 / 3)


def test_D4_request_rate_zero_until_two_windows():
    s = SystemState(total=[4], available=[4], max_claim=[[2]], allocation=[[0]])
    units = np.arange(1, 101, dtype=np.int32)
    assert compute(s, units, t=18, window=10)[I["request_rate"]] == 0.0
    assert compute(s, units, t=19, window=10)[I["request_rate"]] > 0.0


def test_request_rate_values():
    s = SystemState(total=[4], available=[4], max_claim=[[2]], allocation=[[0]])
    units = np.array([1] * 10 + [2] * 10, np.int32)   # doubled -> (20 - 10) / 10 = 1
    assert compute(s, units, t=19, window=10)[I["request_rate"]] == pytest.approx(1.0)
    units = np.array([2] * 10 + [1] * 10, np.int32)   # decreasing -> clipped to 0
    assert compute(s, units, t=19, window=10)[I["request_rate"]] == 0.0


def test_D5_indicators_always_in_unit_interval():
    rng = np.random.default_rng(0)
    for _ in range(500):
        s = random_arbitrary_state(int(rng.integers(1, 12)), int(rng.integers(1, 5)), rng)
        units = rng.integers(0, 20, size=50).astype(np.int32)
        ind = compute(s, units, t=int(rng.integers(0, 50)), window=5)
        assert ((ind >= 0) & (ind <= 1)).all()
    for name in ("normal", "spike", "deadlock_prone"):
        r = simulate(name, 25, 8, seed=0, steps=6000)
        assert ((r.indicators >= 0) & (r.indicators <= 1)).all()
