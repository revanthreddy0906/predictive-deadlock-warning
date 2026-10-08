"""Event extraction: unsafe onsets, flicker-merged episodes, deadlock onset.

Definitions (PLAN_FIXES A2, A4):
  raw onset      t with b[t] and not b[t-1] (b[-1] = False; sequences start safe)
  primary event  the first raw onset, or a raw onset preceded by >= G safe steps.
                 Re-onsets after a shorter safe gap are merged into the episode before.
  merged mask    True on every step of every merged episode, including the short safe
                 gaps inside it. Alarms are suppressed on this mask (A3).
  episode        (start, end_exclusive, outcome), outcome in
                 {"recovered", "deadlocked", "censored"}
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def onsets(b: np.ndarray) -> np.ndarray:
    b = np.asarray(b, dtype=bool)
    if b.size == 0:
        return np.zeros(0, np.int64)
    prev = np.concatenate(([False], b[:-1]))
    return np.flatnonzero(b & ~prev)


def _runs(b: np.ndarray) -> list[tuple[int, int]]:
    """Maximal True runs as (start, end_exclusive)."""
    b = np.asarray(b, dtype=bool)
    if b.size == 0:
        return []
    d = np.diff(np.concatenate(([0], b.astype(np.int8), [0])))
    return list(zip(np.flatnonzero(d == 1).tolist(), np.flatnonzero(d == -1).tolist()))


def merged_runs(unsafe: np.ndarray, gap: int) -> list[tuple[int, int]]:
    """Unsafe runs with safe gaps shorter than `gap` merged (A4)."""
    merged: list[list[int]] = []
    for s, e in _runs(unsafe):
        if merged and s - merged[-1][1] < gap:
            merged[-1][1] = e
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


@dataclass
class SequenceEvents:
    unsafe_events: np.ndarray      # primary unsafe onsets
    first_onset: np.ndarray        # first raw unsafe onset (0 or 1 element)
    deadlock_events: np.ndarray    # deadlock onset (0 or 1 element)
    mask: np.ndarray               # merged-episode mask (alarm suppression)
    episodes: list                 # (start, end_exclusive, outcome)
    n_raw_onsets: int


def extract(unsafe: np.ndarray, deadlocked: np.ndarray, end_reason: str, gap: int = 5) -> SequenceEvents:
    unsafe = np.asarray(unsafe, dtype=bool)
    T = unsafe.size
    runs = merged_runs(unsafe, gap)
    mask = np.zeros(T, bool)
    episodes = []
    for s, e in runs:
        mask[s:e] = True
        if e < T:
            outcome = "recovered"
        elif end_reason == "deadlock":
            outcome = "deadlocked"
        elif end_reason == "max_steps":
            outcome = "censored"
        else:  # all_finished leaves a safe state, so an episode cannot reach T
            outcome = "recovered"
        episodes.append((s, e, outcome))
    raw = onsets(unsafe)
    return SequenceEvents(
        unsafe_events=np.array([s for s, _ in runs], np.int64),
        first_onset=raw[:1],
        deadlock_events=onsets(deadlocked)[:1],
        mask=mask,
        episodes=episodes,
        n_raw_onsets=int(raw.size),
    )
