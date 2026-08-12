import random

import pytest

from models import FIELD_ENUMS
from generator import generate_scenario, generate_scenarios


def test_generate_scenarios_returns_requested_count():
    scenarios = generate_scenarios(50, seed=1)
    assert len(scenarios) == 50


def test_generate_scenarios_is_reproducible_with_same_seed():
    first = generate_scenarios(30, seed=42)
    second = generate_scenarios(30, seed=42)
    assert first == second


def test_uniform_sampling_covers_all_field_values():
    scenarios = generate_scenarios(500, seed=7)
    seen = {s.weather.value for s in scenarios}
    assert seen == {member.value for member in FIELD_ENUMS["weather"]}


def test_weighted_sampling_skews_toward_heavy_weight():
    weights = {"weather": {"fog": 1000.0, "clear": 1.0, "rain": 1.0, "snow": 1.0}}
    scenarios = generate_scenarios(300, seed=3, weights=weights)
    fog_share = sum(1 for s in scenarios if s.weather.value == "fog") / len(scenarios)
    assert fog_share > 0.9


def test_partial_weights_default_unspecified_values_to_one():
    weights = {"lighting": {"night": 5.0}}
    scenarios = generate_scenarios(200, seed=11, weights=weights)
    seen = {s.lighting.value for s in scenarios}
    assert "day" in seen
    assert "dusk" in seen


def test_unknown_field_in_weights_raises():
    with pytest.raises(ValueError):
        generate_scenarios(5, weights={"not_a_field": {"x": 1.0}})


def test_unknown_value_in_weights_raises():
    with pytest.raises(ValueError):
        generate_scenarios(5, weights={"weather": {"hurricane": 1.0}})


def test_generate_scenario_is_deterministic_given_equal_rng_state():
    rng_a = random.Random(99)
    rng_b = random.Random(99)
    assert generate_scenario(rng_a) == generate_scenario(rng_b)
