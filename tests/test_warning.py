import numpy as np
import pytest

from pdw import warning
from pdw.warning import alarm_onsets, random_onsets, risk_score


def test_E3_risk_score_range_and_weights():
    rng = np.random.default_rng(0)
    ind = rng.random((200, 5))
    s = risk_score(ind)
    assert ((s >= 0) & (s <= 100)).all()
    assert risk_score(np.ones((1, 5)))[0] == 100 and risk_score(np.zeros((1, 5)))[0] == 0
    assert risk_score(np.array([[1, 0, 0, 0, 0]]), (1, 0, 0, 0, 0))[0] == 100
    with pytest.raises(ValueError):
        risk_score(ind, (0, 0, 0, 0, 0))


def test_levels():
    assert [warning.level(x) for x in (0, 30, 31, 60, 61, 80, 81, 100)] == \
        ["LOW", "LOW", "MEDIUM", "MEDIUM", "HIGH", "HIGH", "CRITICAL", "CRITICAL"]


def test_E1_score_hovering_needs_k_consecutive_steps():
    score = np.array([60, 40, 60, 60, 40, 60, 60, 60, 40], float)
    assert alarm_onsets(score, 50, k=1, refractory=0).tolist() == [0, 2, 3, 5, 6, 7]
    assert alarm_onsets(score, 50, k=2, refractory=0).tolist() == [3, 6, 7]
    assert alarm_onsets(score, 50, k=3, refractory=0).tolist() == [7]


def test_E2_long_high_stretch_one_alarm_per_refractory_period():
    score = np.full(100, 90.0)
    onsets = alarm_onsets(score, 50, k=1, refractory=20)
    assert onsets.tolist() == [0, 21, 42, 63, 84]
    assert np.diff(onsets).min() > 20


def test_A3_mask_suppresses_and_resets_counter():
    score = np.full(12, 90.0)
    mask = np.zeros(12, bool)
    mask[3:6] = True
    # k=2: run 0-2 fires at 1; mask breaks the run; new run from 6 fires at 7 (R=0)
    assert alarm_onsets(score, 50, k=2, refractory=0, mask=mask).tolist() == [1, 2, 7, 8, 9, 10, 11]
    # masked steps never start a refractory period: an alarm can fire right after
    assert alarm_onsets(score, 50, k=1, refractory=20, mask=np.arange(12) < 6).tolist() == [6]


def test_random_onsets_respect_mask_and_refractory():
    rng = np.random.default_rng(0)
    mask = np.zeros(1000, bool)
    mask[500:600] = True
    on = random_onsets(1000, 0.2, 10, mask, rng)
    assert not mask[on].any() and np.diff(on).min() > 10


def test_method_scores():
    ind = np.array([[0.2, 0.4, 0.6, 0.8, 1.0]])
    assert warning.method_score("availability", ind)[0] == pytest.approx(20)   # = scarcity
    assert warning.method_score("contention", ind)[0] == pytest.approx(60)
    assert warning.method_score("combined", ind)[0] == pytest.approx(60)
    assert warning.method_score("lookahead", ind, np.array([np.nan]))[0] == 0
    with pytest.raises(ValueError):
        warning.method_score("lookahead", ind)


def test_weight_grid_has_equal_doubled_and_dropped():
    grid = dict(warning.weight_grid())
    assert len(grid) == 11 and grid["equal"] == (1,) * 5
    assert grid["drop_request_rate"][4] == 0 and grid["double_scarcity"][0] == 2
