import random
from itertools import combinations, product
from math import comb, prod

import pytest

from coverage import (
    all_pairwise_combinations,
    all_tway_combinations,
    coverage_percentage,
    field_combinations,
    fuzz_toward_tway_gaps,
    greedy_covering_array,
    pairwise_counts,
    tway_counts,
    tway_coverage_percentage,
    tway_coverage_report,
)
from generator import generate_scenarios
from models import FIELD_ENUMS, SCHEMA_FIELDS, Scenario


def _expected_total(strength):
    sizes = [len(FIELD_ENUMS[field]) for field in SCHEMA_FIELDS]
    return sum(prod(group) for group in combinations(sizes, strength))


def test_field_combinations_matches_binomial_count():
    for strength in range(1, len(SCHEMA_FIELDS) + 1):
        assert len(field_combinations(strength)) == comb(len(SCHEMA_FIELDS), strength)


@pytest.mark.parametrize("strength", [0, len(SCHEMA_FIELDS) + 1])
def test_field_combinations_rejects_invalid_strength(strength):
    with pytest.raises(ValueError):
        field_combinations(strength)


@pytest.mark.parametrize("strength", [1, 2, 3])
def test_all_tway_combinations_count(strength):
    assert len(all_tway_combinations(strength)) == _expected_total(strength)


def test_three_way_space_has_962_combinations():
    assert len(all_tway_combinations(3)) == 962


def test_two_way_agrees_with_pairwise_functions():
    scenarios = generate_scenarios(40, seed=3)
    assert len(all_tway_combinations(2)) == len(all_pairwise_combinations())
    assert tway_coverage_percentage(scenarios, 2) == pytest.approx(coverage_percentage(scenarios))
    pairwise = pairwise_counts(scenarios)
    for (fields, values), count in tway_counts(scenarios, 2).items():
        assert pairwise[(fields[0], fields[1], values[0], values[1])] == count


def test_single_scenario_covers_one_combo_per_field_group(sample_scenario):
    report = tway_coverage_report([sample_scenario], 3)
    assert report["covered_combinations"] == comb(len(SCHEMA_FIELDS), 3)


def test_full_factorial_reaches_full_three_way_coverage():
    every = [
        Scenario.from_values(dict(zip(SCHEMA_FIELDS, values)))
        for values in product(*[[m.value for m in FIELD_ENUMS[f]] for f in SCHEMA_FIELDS])
    ]
    assert tway_coverage_percentage(every, 3) == 100.0


def test_full_pairwise_coverage_does_not_imply_full_three_way_coverage():
    pairwise_array = greedy_covering_array(2, random.Random(0))
    assert coverage_percentage(pairwise_array) == 100.0
    assert tway_coverage_percentage(pairwise_array, 3) < 100.0


def test_three_way_report_lists_the_untested_hard_combination():
    report = tway_coverage_report(generate_scenarios(50, seed=1234), 3)
    untested = set(report["zero_coverage"])
    assert (("lighting", "agent_mix", "road_type"), ("night", "high_pedestrian", "residential")) in untested


@pytest.mark.parametrize("strength", [2, 3])
def test_greedy_covering_array_achieves_full_coverage(strength):
    array = greedy_covering_array(strength, random.Random(1))
    assert tway_coverage_percentage(array, strength) == 100.0


def test_greedy_covering_array_is_far_smaller_than_full_factorial():
    array = greedy_covering_array(3, random.Random(2))
    full_factorial = prod(len(FIELD_ENUMS[f]) for f in SCHEMA_FIELDS)
    lower_bound = 5 * 4 * 4  # product of the three largest domains
    assert lower_bound <= len(array) < 130 < full_factorial


def test_greedy_covering_array_only_adds_what_existing_scenarios_miss():
    existing = generate_scenarios(80, seed=4)
    added = greedy_covering_array(3, random.Random(4), existing=existing)
    assert tway_coverage_percentage(existing + added, 3) == 100.0
    assert len(added) < len(greedy_covering_array(3, random.Random(4)))


def test_greedy_covering_array_adds_nothing_when_already_covered():
    covered = greedy_covering_array(2, random.Random(5))
    assert greedy_covering_array(2, random.Random(5), existing=covered) == []


def test_greedy_covering_array_is_reproducible():
    assert greedy_covering_array(3, random.Random(9)) == greedy_covering_array(3, random.Random(9))


def test_fuzz_toward_tway_gaps_hits_targeted_combinations():
    scenarios = generate_scenarios(30, seed=6)
    report = tway_coverage_report(scenarios, 3)
    targets = set(report["zero_coverage"]) | {combo for combo, _ in report["low_coverage"]}
    candidates = fuzz_toward_tway_gaps(scenarios, random.Random(6), 3, n=25)
    assert len(candidates) == 25
    for candidate in candidates:
        data = candidate.as_dict()
        keys = {(fields, tuple(data[f] for f in fields)) for fields in field_combinations(3)}
        assert keys & targets


def test_fuzz_toward_tway_gaps_empty_inputs():
    assert fuzz_toward_tway_gaps([], random.Random(0), 3) == []
    full = greedy_covering_array(2, random.Random(0))
    assert fuzz_toward_tway_gaps(full * 2, random.Random(0), 2) == []
