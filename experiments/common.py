"""Shared experiment helpers: config loading, seed splits, worker count."""

from __future__ import annotations

import hashlib
import json
import os

import yaml

TUNING_SEEDS = range(0, 100_000)
TEST_SEEDS_START = 100_000
TEST_SEEDS = range(TEST_SEEDS_START, 1_000_000)
assert TUNING_SEEDS.stop <= TEST_SEEDS.start, "tuning and test seeds must never overlap"


def load_config(path: str) -> dict:
    with open(path) as f:
        cfg = yaml.safe_load(f)
    cfg.setdefault("indicator_window", 10)
    cfg.setdefault("min_safe_gap", 5)
    cfg.setdefault("workers", "auto")
    return cfg


def n_workers(cfg: dict) -> int:
    w = cfg.get("workers", "auto")
    return (os.cpu_count() or 1) if w == "auto" else int(w)


def seed_range(cfg: dict) -> range:
    """Seeds for this run, asserting they stay inside their split (fix G2)."""
    seeds = range(cfg["seeds"]["start"], cfg["seeds"]["start"] + cfg["seeds"]["count"])
    split = cfg.get("split")
    if split == "tuning":
        assert seeds.start >= TUNING_SEEDS.start and seeds.stop <= TUNING_SEEDS.stop, "tuning seeds out of range"
    elif split == "test":
        assert seeds.start >= TEST_SEEDS.start and seeds.stop <= TEST_SEEDS.stop, "test seeds out of range"
    elif split is not None:
        raise ValueError(f"unknown split {split!r}")
    return seeds


def config_hash(cfg: dict) -> str:
    """Hash of everything that affects simulation output (not workers / run_name)."""
    keys = ("split", "seeds", "scenarios", "sizes", "steps", "indicator_window",
            "scenario_params", "lookahead", "extras")
    blob = json.dumps({k: cfg.get(k) for k in keys}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]
