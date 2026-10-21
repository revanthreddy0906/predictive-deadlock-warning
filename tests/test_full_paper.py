"""Tests for the full-paper additions: safety margin, top-k lookahead, max aggregation,
misdeclared-claim indicators, learned baselines and the NAB-style score."""

import numpy as np
import pytest

from pdw import banker, learned, metrics, warning
from pdw.simulator import EXTRAS, simulate
from pdw.state import random_arbitrary_state
from tests.test_banker import silberschatz, silberschatz_unsafe


def args(s):
    return s.available, s.allocation, s.need, s.active


def test_safety_margin_bounds_and_meaning():
    s = silberschatz()
    f = banker.safety_margin(*args(s))
    assert 0.0 <= f < 1.0
    # removing a fraction f of the free units keeps the state safe ...
    shrunk = np.floor(s.available * (1 - f)).astype(np.int64)
    assert banker.is_safe(shrunk, s.allocation, s.need, s.active)[0]
    # ... while removing everything does not (P1 and P3 need units to start)
    assert not banker.is_safe(np.zeros(3, np.int64), s.allocation, s.need, s.active)[0]


def test_safety_margin_is_one_when_nothing_is_needed():
    s = silberschatz()
    s.finished[:] = True
    s.allocation[:] = 0
    s.available[:] = s.total
    assert banker.safety_margin(*args(s)) == 1.0


def test_safety_margin_monotone_in_available():
    rng = np.random.default_rng(0)
    checked = 0
    for _ in range(300):
        s = random_arbitrary_state(int(rng.integers(2, 10)), int(rng.integers(1, 4)), rng, wait_prob=0)
        if not banker.state_is_safe(s)[0]:
            continue
        f = banker.safety_margin(*args(s), iters=8)
        bigger = s.available + 1
        assert banker.safety_margin(bigger, s.allocation, s.need, s.active, iters=8) >= f - 1 / 2 ** 7
        checked += 1
    assert checked > 50


def test_topk_lookahead_matches_full_lookahead_when_k_covers_all():
    rng = np.random.default_rng(1)
    for _ in range(200):
        s = random_arbitrary_state(int(rng.integers(1, 6)), int(rng.integers(1, 4)), rng, wait_prob=0.3)
        running = s.active & ~s.waiting
        full = banker.lookahead_fraction(*args(s), running)
        assert banker.lookahead_topk(*args(s), running, k=s.n) == pytest.approx(full)
        assert 0.0 <= banker.lookahead_topk(*args(s), running, k=2) <= 1.0


def test_topk_lookahead_detects_known_flip():
    # Granting P0 (0,2,0) after P1's request makes the textbook state unsafe; P0's largest
    # feasible grant here is at least that much, so at least one checked process flips.
    s = silberschatz()
    s.allocation[1] += [1, 0, 2]
    s.available -= [1, 0, 2]
    running = s.active & ~s.waiting
    assert banker.lookahead_topk(*args(s), running, k=s.n) > 0


def test_max_score():
    ind = np.array([[0.2, 0.4, 0.9, 0.1, 0.0]])
    assert warning.max_score(ind)[0] == pytest.approx(90)
    # contention weight 0 -> the maximum comes from need pressure
    assert warning.max_score(ind, (1, 1, 0, 1, 1))[0] == pytest.approx(40)
    with pytest.raises(ValueError):
        warning.max_score(ind, (0, 0, 0, 0, 0))


def test_noisy_indicators_replace_only_claim_based_columns():
    ind = np.full((3, 5), 0.5)
    extras = np.array([[np.nan, np.nan, 0.1, 0.2]] * 3)
    out = warning.noisy_indicators(ind, extras)
    assert (out[:, 1] == 0.1).all() and (out[:, 2] == 0.2).all()
    assert (out[:, [0, 3, 4]] == 0.5).all()


def test_extras_do_not_change_the_simulated_workload():
    for sc in ("normal", "spike", "deadlock_prone"):
        a = simulate(sc, 10, 5, 7, 15000)
        b = simulate(sc, 10, 5, 7, 15000, extras=True)
        assert a.T == b.T and np.array_equal(a.unsafe, b.unsafe)
        assert np.allclose(a.indicators, b.indicators)
        assert b.extras.shape == (b.T, len(EXTRAS))
        assert np.isnan(b.extras[b.unsafe, :2]).all()          # margin/lookahead only when safe
        safe_vals = b.extras[~b.unsafe, :2]
        assert ((safe_vals >= 0) & (safe_vals <= 1)).all()
        assert ((b.extras[:, 2:] >= 0) & (b.extras[:, 2:] <= 1)).all()


def test_learned_features_and_labels():
    ind = np.arange(20, dtype=float).reshape(4, 5) / 20
    X = learned.features(ind, window=2)
    assert X.shape == (4, 10)
    assert np.allclose(X[:, :5], ind) and np.allclose(X[0, 5:], 0)
    assert np.allclose(X[3, 5:], ind[3] - ind[1])
    y = learned.labels(30, np.array([10, 25]), H_max=5, H_min=1)
    assert y[5:10].all() and not y[10] and not y[4]
    assert y[20:25].all() and y.sum() == 10


def test_learned_score_prior_correction():
    class Fixed:
        def predict_proba(self, X):
            return np.tile([0.5, 0.5], (len(X), 1))
    s = learned.score(Fixed(), np.zeros((3, 5)), prior=0.1)
    assert s == pytest.approx(10.0)   # even odds on a balanced set -> the true prior
    assert learned.score(Fixed(), np.zeros((0, 5))).size == 0


def test_nab_score_anchors():
    assert metrics.nab_score([], 0, 10) == pytest.approx(0.0)              # null detector
    assert metrics.nab_score([20] * 10, 0, 10, H_max=20) > 99.0           # earliest, no FP
    assert metrics.nab_score([1] * 10, 0, 10) < metrics.nab_score([15] * 10, 0, 10)
    assert metrics.nab_score([10] * 10, 50, 10) < metrics.nab_score([10] * 10, 0, 10)
    assert np.isnan(metrics.nab_score([], 3, 0))
