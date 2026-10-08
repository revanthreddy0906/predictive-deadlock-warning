"""Workload scenarios: which process requests what at each step.

A scenario is built per sequence with `make_scenario(name, cfg, n, m, rng)` and asked
for one request per step via `scenario.request(state, need, t, rng)`. It only picks
active, non-waiting processes and always returns a non-zero request <= need (B1, B2,
B5, B6). It returns None when no process can request (B8).

Request sizes are fractions of the remaining need, so scenarios behave the same way
across system sizes.

    normal          small single-resource requests, frequent completions,
                    occasional voluntary partial releases
    spike           `normal`, then a burst of large multi-resource requests from a
                    subset of processes; burst requests hold back one unit of need,
                    so bursters keep what they grab instead of finishing
    deadlock_prone  process i prefers resource (i+1) mod m, moderate requests,
                    completions mostly held back (gradual build-up)
"""

from __future__ import annotations

import math

import numpy as np

SCENARIOS = ("normal", "spike", "deadlock_prone")

# Frozen after Phase 8 calibration on tuning seeds (see configs/calibrate.yaml).
DEFAULTS = {
    "normal": {
        "state": {"tightness": (1.5, 1.9), "init_alloc_frac": (0.0, 0.3)},
        "small_frac": 0.5,       # request at most this fraction of need[i, j]
        "release_prob": 0.05,    # per step: one running process releases part of its allocation
        "release_frac": 0.5,
    },
    "spike": {
        "state": {"tightness": (1.6, 2.1), "init_alloc_frac": (0.0, 0.3)},
        "small_frac": 0.5,
        "release_prob": 0.0,
        "release_frac": 0.5,
        "spike_progress": (0.2, 0.6),  # burst begins once this fraction of the initial
                                       # total need has been requested (size-invariant)
        "spike_len_per_proc": 1.0,     # burst lasts max(20, round(this * n)) steps
        "spike_procs_frac": 0.8,       # fraction of processes that burst
        "large_frac": (0.3, 0.6),      # burst requests take this fraction of need per resource
    },
    "deadlock_prone": {
        "state": {"tightness": (1.3, 2.2), "init_alloc_frac": (0.0, 0.3)},
        "small_frac": 0.4,
        "release_prob": 0.0,
        "release_frac": 0.5,
        "pref_prob": 0.8,           # request the preferred resource (i+1) mod m
        "finish_prob": 0.3,         # chance a request may take the last unit of need
    },
}


def scenario_cfg(name: str, overrides: dict | None = None) -> dict:
    if name not in DEFAULTS:
        raise ValueError(f"unknown scenario {name!r}; choose from {SCENARIOS}")
    cfg = {**DEFAULTS[name], **(overrides or {})}
    cfg["state"] = {**DEFAULTS[name]["state"], **((overrides or {}).get("state") or {})}
    return cfg


def _small_request(need_i: np.ndarray, j: int, frac: float, rng) -> np.ndarray:
    req = np.zeros_like(need_i)
    cap = max(1, math.ceil(frac * need_i[j]))
    req[j] = rng.integers(1, cap + 1)
    return req


class Scenario:
    name = "base"

    def __init__(self, cfg: dict, n: int, m: int, rng: np.random.Generator):
        self.cfg = cfg
        self.n, self.m = n, m
        self.release_prob = float(cfg.get("release_prob", 0.0))
        self.release_frac = float(cfg.get("release_frac", 0.5))

    @staticmethod
    def eligible(state, need) -> np.ndarray:
        return np.flatnonzero(state.active & ~state.waiting & (need.sum(axis=1) > 0))

    def request(self, state, need, t: int, rng):
        elig = self.eligible(state, need)
        if elig.size == 0:
            return None
        pid = int(rng.choice(elig))
        return pid, self._make(pid, need[pid], t, rng)

    def _make(self, pid, need_i, t, rng) -> np.ndarray:
        j = int(rng.choice(np.flatnonzero(need_i)))
        return _small_request(need_i, j, self.cfg["small_frac"], rng)

    def in_spike(self, t: int) -> bool:
        return False


class Normal(Scenario):
    name = "normal"


class Spike(Scenario):
    name = "spike"

    def __init__(self, cfg, n, m, rng):
        super().__init__(cfg, n, m, rng)
        self.progress_at = rng.uniform(*cfg["spike_progress"])
        self.length = max(20, round(cfg["spike_len_per_proc"] * n))
        k = max(1, round(cfg["spike_procs_frac"] * n))
        self.bursters = np.sort(rng.choice(n, size=k, replace=False))
        self.start = None          # step at which the burst began
        self.requested = 0         # units requested so far
        self.initial_need = None

    def in_spike(self, t):
        return self.start is not None and self.start <= t < self.start + self.length

    def request(self, state, need, t, rng):
        if self.initial_need is None:
            self.initial_need = max(1, int(need.sum()))
        if self.start is None and self.requested >= self.progress_at * self.initial_need:
            self.start = t
        out = self._request(state, need, t, rng)
        if out is not None:
            self.requested += int(out[1].sum())
        return out

    def _request(self, state, need, t, rng):
        if self.in_spike(t):
            elig = np.intersect1d(self.eligible(state, need), self.bursters)
            if elig.size:
                pid = int(rng.choice(elig))
                lo, hi = self.cfg["large_frac"]
                frac = rng.uniform(lo, hi, size=self.m)
                # Grab what is there: capped by available, so bursts are granted, not blocked.
                req = np.minimum(np.ceil(frac * need[pid]).astype(np.int64),
                                 np.minimum(need[pid], state.available))
                # A burst grabs and holds: leave one unit of need so the process keeps
                # its allocation instead of finishing (unless only one unit remains).
                if (req == need[pid]).all() and req.sum() > 1:
                    req[int(np.argmax(req))] -= 1
                if req.any():
                    return pid, req
        return super().request(state, need, t, rng)


class DeadlockProne(Scenario):
    name = "deadlock_prone"

    def _make(self, pid, need_i, t, rng):
        pref = (pid + 1) % self.m
        if need_i[pref] > 0 and rng.random() < self.cfg["pref_prob"]:
            j = pref
        else:
            j = int(rng.choice(np.flatnonzero(need_i)))
        req = _small_request(need_i, j, self.cfg["small_frac"], rng)
        # Hold back completions: avoid taking the very last unit of need, mostly.
        if (req == need_i).all() and req[j] > 1 and rng.random() >= self.cfg["finish_prob"]:
            req[j] -= 1
        return req


_CLASSES = {"normal": Normal, "spike": Spike, "deadlock_prone": DeadlockProne}


def make_scenario(name: str, cfg: dict, n: int, m: int, rng: np.random.Generator) -> Scenario:
    return _CLASSES[name](cfg, n, m, rng)
