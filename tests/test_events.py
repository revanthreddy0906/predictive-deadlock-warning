import numpy as np

from pdw import events


def b(s: str) -> np.ndarray:
    """'SSUUS' -> [F, F, T, T, F]"""
    return np.array([c == "U" for c in s])


def test_onsets():
    assert events.onsets(b("SUUSUS")).tolist() == [1, 4]
    assert events.onsets(b("UUS")).tolist() == [0]
    assert events.onsets(b("")).tolist() == []


def test_A4_flicker_merged_with_min_safe_gap():
    u = b("SSUSUSSSSSSU")
    ev = events.extract(u, np.zeros(len(u), bool), "max_steps", gap=5)
    assert ev.unsafe_events.tolist() == [2, 11]
    assert ev.n_raw_onsets == 3
    assert ev.first_onset.tolist() == [2]
    # mask covers the merged episode, including the 1-step safe gap at 3
    assert ev.mask.tolist() == [c == "U" for c in "SSUUUSSSSSSU"]


def test_A2_episode_outcomes_including_censored():
    u = b("SUUSSSSSSUU")
    ev = events.extract(u, np.zeros(len(u), bool), "max_steps", gap=5)
    assert [e[2] for e in ev.episodes] == ["recovered", "censored"]
    d = np.zeros(len(u), bool)
    d[-1] = True
    ev = events.extract(u, d, "deadlock", gap=5)
    assert [e[2] for e in ev.episodes] == ["recovered", "deadlocked"]
    assert ev.deadlock_events.tolist() == [len(u) - 1]


def test_C3_multiple_episodes_supported():
    u = b("SUUSSSSSSUUSSSSSSU")
    ev = events.extract(u, np.zeros(len(u), bool), "max_steps", gap=5)
    assert ev.unsafe_events.tolist() == [1, 9, 17]
