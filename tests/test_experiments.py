import pytest

from experiments.common import TEST_SEEDS, TUNING_SEEDS, load_config, seed_range
from experiments.run_batch import lookahead_subsample


def test_G2_tuning_and_test_seed_ranges_never_overlap():
    assert TUNING_SEEDS.stop <= TEST_SEEDS.start


@pytest.mark.parametrize("path", ["configs/tuning.yaml", "configs/main.yaml", "configs/b_tuning.yaml",
                                  "configs/b_main.yaml", "configs/b_pilot.yaml", "configs/b_tuning_small.yaml",
                                  "configs/calibrate.yaml"])
def test_configs_use_seeds_inside_their_split(path):
    cfg = load_config(path)
    seeds = seed_range(cfg)
    split = TUNING_SEEDS if cfg["split"] == "tuning" else TEST_SEEDS
    assert seeds.start >= split.start and seeds.stop <= split.stop


def test_out_of_split_seeds_rejected():
    with pytest.raises(AssertionError):
        seed_range({"split": "tuning", "seeds": {"start": 99_990, "count": 20}})
    with pytest.raises(AssertionError):
        seed_range({"split": "test", "seeds": {"start": 50, "count": 20}})


def test_lookahead_subsample_per_size():
    look = {"max_n_all_seeds": 25, "subsample_seeds": 200, "subsample_by_n": {200: 50}}
    assert lookahead_subsample(look, 100) == 200
    assert lookahead_subsample(look, 200) == 50
    assert lookahead_subsample({}, 100) == 0
    assert lookahead_subsample({"subsample_by_n": {"200": 7}}, 200) == 7  # YAML keys may be strings
