import numpy as np
import pytest

from pdw.scenarios import SCENARIOS, make_scenario, scenario_cfg
from pdw.simulator import simulate
from pdw.state import SystemState, random_arbitrary_state


@pytest.mark.parametrize("name", SCENARIOS)
def test_B1_B2_B5_B6_requests_valid_and_from_eligible_processes(name):
    rng = np.random.default_rng(0)
    for _ in range(100):
        n, m = int(rng.integers(2, 15)), int(rng.integers(1, 6))
        state = random_arbitrary_state(n, m, rng, wait_prob=0.3, finish_prob=0.2)
        gen = make_scenario(name, scenario_cfg(name), n, m, rng)
        need = state.need
        for t in range(30):
            out = gen.request(state, need, t, rng)
            if out is None:
                assert not (state.active & ~state.waiting & (need.sum(1) > 0)).any()
                break
            pid, req = out
            assert req.sum() > 0 and (req >= 0).all()             # B1
            assert (req <= need[pid]).all()                        # B2
            assert not state.waiting[pid]                          # B5
            assert not state.finished[pid]                         # B6


def test_B8_no_eligible_process_returns_none():
    state = SystemState(total=[2], available=[2], max_claim=[[1]], allocation=[[0]], finished=[True])
    gen = make_scenario("normal", scenario_cfg("normal"), 1, 1, np.random.default_rng(0))
    assert gen.request(state, state.need, 0, np.random.default_rng(0)) is None


@pytest.mark.parametrize("name", SCENARIOS)
def test_scenario_deterministic_by_seed(name):
    a = simulate(name, 10, 5, seed=7, steps=300)
    b = simulate(name, 10, 5, seed=7, steps=300)
    assert a.T == b.T and np.array_equal(a.req_units, b.req_units)


def test_spike_window_has_larger_requests():
    ratios = []
    for seed in range(30):
        r = simulate("spike", 25, 8, seed=seed, steps=6000)
        if r.in_spike.any() and (~r.in_spike).any():
            ratios.append(r.req_units[r.in_spike].mean() / max(r.req_units[~r.in_spike].mean(), 1e-9))
    assert len(ratios) >= 20 and np.median(ratios) > 2


def test_deadlock_prone_prefers_next_resource():
    rng = np.random.default_rng(1)
    state = SystemState.random(10, 5, rng, scenario_cfg("deadlock_prone")["state"])
    gen = make_scenario("deadlock_prone", scenario_cfg("deadlock_prone"), 10, 5, rng)
    hits = total = 0
    for t in range(500):
        pid, req = gen.request(state, state.need, t, rng)
        pref = (pid + 1) % 5
        if state.need[pid, pref] > 0:
            total += 1
            hits += req[pref] > 0
    assert hits / total > 0.7


def test_unknown_scenario_rejected():
    with pytest.raises(ValueError):
        scenario_cfg("bogus")
