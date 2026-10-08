"""One hand-built case per row of the Section 3.5 table (F1-F11) plus fixes A1, A5, A6."""

import numpy as np
import pandas as pd
import pytest

from pdw import metrics
from pdw.events import extract
from pdw.metrics import evaluate_sequence as ev
from pdw.warning import alarm_onsets

H = dict(H_min=1, H_max=20)


def test_F1_alarm_in_window_is_true_and_captures():
    r = ev([40], [50], T=200, end_reason="deadlock", **H)
    assert (r["true"], r["false"], r["captured"], r["events"]) == (1, 0, 1, 1)
    assert r["leads"] == {50: 10}


def test_F2_lead_zero_is_a_miss():
    r = ev([50], [50], T=200, end_reason="deadlock", **H)
    assert r["captured"] == 0 and r["true"] == 0
    # and in practice the alarm never fires: the unsafe step is masked (A3)
    unsafe = np.zeros(200, bool)
    unsafe[50:60] = True
    score = np.where(np.arange(200) >= 50, 90.0, 10.0)
    assert alarm_onsets(score, 50, k=1, refractory=20, mask=extract(unsafe, unsafe & False, "max_steps").mask).tolist() == [60, 81, 102, 123, 144, 165, 186]


def test_F3_alarm_during_episode_ignored_event_missed():
    unsafe = np.zeros(100, bool)
    unsafe[30:50] = True
    e = extract(unsafe, np.zeros(100, bool), "all_finished")
    score = np.zeros(100)
    score[35:45] = 90  # only inside the episode
    alarms = alarm_onsets(score, 50, k=1, refractory=20, mask=e.mask)
    assert alarms.size == 0
    r = ev(alarms, e.unsafe_events, T=100, end_reason="all_finished", **H)
    assert r["captured"] == 0 and r["events"] == 1 and r["alarms"] == 0


def test_F4_alarm_without_onset_in_horizon_is_false():
    r = ev([10], [60], T=200, end_reason="deadlock", **H)
    assert (r["true"], r["false"], r["captured"]) == (0, 1, 0)


def test_F5_unalarmed_event_missed():
    r = ev([], [60], T=200, end_reason="deadlock", **H)
    assert (r["events"], r["captured"]) == (1, 0)


def test_F6_several_alarms_first_valid_gives_lead():
    r = ev([42, 50, 55], [60], T=200, end_reason="deadlock", **H)
    assert r["leads"] == {60: 18}      # earliest alarm in [40, 59]
    assert r["captured"] == 1 and r["events"] == 1
    assert r["true"] == 3              # all followed by an onset within H (glossary definition)


def test_F7_one_alarm_counts_for_first_event_only():
    r = ev([40], [45, 55], T=200, end_reason="deadlock", **H)
    assert r["captured"] == 1 and r["leads"] == {45: 5}


def test_F8_long_high_stretch_no_event_one_false_per_refractory():
    alarms = alarm_onsets(np.full(100, 90.0), 50, k=1, refractory=20)
    r = ev(alarms, [], T=100, end_reason="all_finished", **H)
    assert r["false"] == len(alarms) == 5


def test_F9a_tail_alarm_step_capped_no_event_censored():
    r = ev([190], [], T=200, end_reason="max_steps", **H)
    assert (r["censored"], r["false"], r["true"]) == (1, 0, 0)


def test_F9b_tail_alarm_followed_by_onset_is_true():
    r = ev([185], [195], T=200, end_reason="max_steps", **H)
    assert (r["true"], r["censored"], r["captured"]) == (1, 0, 1)


def test_F9c_tail_alarm_known_future_is_false():
    for reason in ("deadlock", "all_finished"):
        r = ev([190], [], T=200, end_reason=reason, **H)
        assert (r["false"], r["censored"]) == (1, 0)


def test_F10_quiet_sequence():
    r = ev([], [], T=200, end_reason="all_finished", **H)
    assert r["quiet"] and r["alarms"] == r["events"] == 0
    agg = metrics.aggregate([r, ev([40], [50], T=200, end_reason="deadlock", **H)])
    assert agg["quiet_sequences"] == 1 and agg["precision"] == 1.0 and agg["recall"] == 1.0


def test_F11_paired_leads_only_on_events_both_caught():
    a = [{10: 5, 30: 3}, {7: 2}]
    b = [{10: 8}, {7: 1, 50: 9}]
    la, lb = metrics.paired_leads(a, b)
    assert sorted(zip(la.tolist(), lb.tolist())) == [(2, 1), (5, 8)]


def test_A5_uncatchable_early_events_excluded_from_recall():
    r = ev([], [1, 50], T=200, end_reason="deadlock", **H)
    assert (r["uncatchable"], r["events"]) == (1, 1)


def test_A6_no_alarms_gives_nan_precision_and_zero_f1():
    agg = metrics.aggregate([ev([], [50], T=200, end_reason="deadlock", **H)])
    assert np.isnan(agg["precision"]) and agg["recall"] == 0 and agg["f1"] == 0
    agg = metrics.aggregate([ev([], [], T=200, end_reason="all_finished", **H)])
    assert np.isnan(agg["recall"])


def test_A6_micro_average_not_mean_of_ratios():
    rows = [ev([40], [50], T=100, end_reason="deadlock", **H),           # 1 true
            ev([10, 50, 90], [], T=100, end_reason="all_finished", **H)]  # 3 false
    agg = metrics.aggregate(rows)
    assert agg["precision"] == pytest.approx(0.25)
    assert agg["fa_per_1000"] == pytest.approx(15.0)


def test_lead_stats():
    s = metrics.lead_stats([1, 3, 5, 10])
    assert s["lead_median"] == 4 and s["lead_ge_5"] == 0.5 and s["lead_ge_1"] == 1.0


def test_A7_bootstrap_stratified_ci_contains_point_estimate():
    rng = np.random.default_rng(0)
    rows = []
    for scen in ("a", "b"):
        for _ in range(100):
            ev_ = [50] if rng.random() < 0.5 else []
            al = [45] if rng.random() < 0.6 else []
            r = ev(al, ev_, T=100, end_reason="deadlock", **H)
            r.update(scenario=scen, n=10)
            rows.append(r)
    df = pd.DataFrame(rows)
    point = metrics.aggregate(df)
    ci = metrics.bootstrap_ci(df, B=500)
    for k in ("precision", "recall", "f1"):
        lo, hi = ci[k]
        assert lo <= point[k] <= hi and lo < hi
