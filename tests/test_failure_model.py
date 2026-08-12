import random

from models import FIELD_ENUMS
from failure_model import (
    HARD_COMBINATIONS,
    BASELINE_FAILURE_PROBABILITY,
    base_failure_probability,
    evaluate_scenario,
)


def test_baseline_probability_applies_when_no_hard_combination_matches(make_scenario):
    scenario = make_scenario()
    assert base_failure_probability(scenario) == BASELINE_FAILURE_PROBABILITY


def test_matching_a_hard_combination_returns_its_base_probability(make_scenario):
    conditions = {
        "lighting": "night",
        "weather": "fog",
        "agent_mix": "high_cyclist",
        "maneuver_type": "merge",
    }
    scenario = make_scenario(**conditions)
    expected = next(
        entry["base_failure_probability"]
        for entry in HARD_COMBINATIONS
        if entry["conditions"] == conditions
    )
    assert base_failure_probability(scenario) == expected


def test_matching_multiple_hard_combinations_takes_the_maximum(make_scenario):
    scenario = make_scenario(
        lighting="night",
        weather="fog",
        agent_mix="high_cyclist",
        maneuver_type="merge",
    )
    values = scenario.as_dict()
    matched = [
        entry["base_failure_probability"]
        for entry in HARD_COMBINATIONS
        if all(values[field] == value for field, value in entry["conditions"].items())
    ]
    assert len(matched) > 1
    assert base_failure_probability(scenario) == max(matched)


def test_evaluate_scenario_fails_often_for_a_hard_combo(make_scenario):
    scenario = make_scenario(
        lighting="night",
        weather="fog",
        agent_mix="high_cyclist",
        maneuver_type="merge",
    )
    rng = random.Random(0)
    outcomes = [evaluate_scenario(scenario, rng) for _ in range(500)]
    fail_rate = outcomes.count(False) / len(outcomes)
    assert fail_rate > 0.6


def test_evaluate_scenario_passes_often_for_a_baseline_scenario(make_scenario):
    scenario = make_scenario()
    rng = random.Random(1)
    outcomes = [evaluate_scenario(scenario, rng) for _ in range(500)]
    pass_rate = outcomes.count(True) / len(outcomes)
    assert pass_rate > 0.8


def test_evaluate_scenario_outcomes_are_not_deterministic_for_a_hard_combo(make_scenario):
    scenario = make_scenario(
        lighting="night",
        weather="fog",
        agent_mix="high_cyclist",
        maneuver_type="merge",
    )
    rng = random.Random(2)
    outcomes = {evaluate_scenario(scenario, rng) for _ in range(200)}
    assert outcomes == {True, False}


def test_evaluate_scenario_is_reproducible_given_equal_rng_state(make_scenario):
    scenario = make_scenario(
        weather="snow", road_type="highway", ego_speed_bucket="high"
    )
    results_a = [evaluate_scenario(scenario, random.Random(7)) for _ in range(20)]
    results_b = [evaluate_scenario(scenario, random.Random(7)) for _ in range(20)]
    assert results_a == results_b


def test_hard_combination_conditions_reference_valid_schema_fields_and_values():
    for entry in HARD_COMBINATIONS:
        for field, value in entry["conditions"].items():
            assert field in FIELD_ENUMS
            assert value in {member.value for member in FIELD_ENUMS[field]}
        assert 0.0 < entry["base_failure_probability"] <= 1.0
