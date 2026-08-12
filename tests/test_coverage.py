import math
import random
from itertools import combinations, product

import pytest

from models import SCHEMA_FIELDS, FIELD_ENUMS, Scenario
from coverage import (
    field_pairs,
    all_pairwise_combinations,
    pairwise_counts,
    coverage_report,
    coverage_percentage,
    fuzz_toward_underrepresented,
)


def _full_factorial():
    field_values = [list(FIELD_ENUMS[field]) for field in SCHEMA_FIELDS]
    return [Scenario(**dict(zip(SCHEMA_FIELDS, combo))) for combo in product(*field_values)]


def test_field_pairs_matches_combinatorics_of_schema_fields():
    expected_pair_count = math.comb(len(SCHEMA_FIELDS), 2)
    pairs = field_pairs()
    assert len(pairs) == expected_pair_count
    assert len(set(pairs)) == expected_pair_count
    for field_a, field_b in pairs:
        assert field_a != field_b


def test_all_pairwise_combinations_count_matches_value_product_sum():
    expected = 0
    for field_a, field_b in combinations(SCHEMA_FIELDS, 2):
        expected += len(list(FIELD_ENUMS[field_a])) * len(list(FIELD_ENUMS[field_b]))
    assert len(all_pairwise_combinations()) == expected


def test_pairwise_counts_counts_each_pair_per_scenario(sample_scenario):
    counts = pairwise_counts([sample_scenario, sample_scenario])
    assert counts[("weather", "lighting", "clear", "day")] == 2
    assert ("weather", "lighting", "rain", "night") not in counts


def test_coverage_percentage_is_zero_for_empty_scenario_set():
    assert coverage_percentage([]) == 0.0


def test_coverage_percentage_is_partial_for_a_single_scenario(sample_scenario):
    percentage = coverage_percentage([sample_scenario])
    total_combos = len(all_pairwise_combinations())
    pairs_covered_by_one_scenario = len(field_pairs())
    assert percentage == pytest.approx(100.0 * pairs_covered_by_one_scenario / total_combos)


def test_coverage_percentage_reaches_full_for_full_factorial_set():
    assert coverage_percentage(_full_factorial()) == 100.0


def test_coverage_report_flags_unseen_combo_as_zero_coverage(sample_scenario):
    report = coverage_report([sample_scenario])
    assert ("weather", "lighting", "rain", "night") in report["zero_coverage"]


def test_coverage_report_low_coverage_respects_threshold(sample_scenario):
    report = coverage_report([sample_scenario, sample_scenario], low_threshold=3)
    assert (("weather", "lighting", "clear", "day"), 2) in report["low_coverage"]


def test_fuzz_returns_empty_list_for_empty_scenario_set():
    assert fuzz_toward_underrepresented([], random.Random(0)) == []


def test_fuzz_returns_empty_list_when_fully_covered():
    assert fuzz_toward_underrepresented(_full_factorial(), random.Random(0)) == []


def test_fuzz_generates_requested_candidate_count(sample_scenario):
    candidates = fuzz_toward_underrepresented([sample_scenario], random.Random(5), n=20)
    assert len(candidates) == 20
    assert all(isinstance(candidate, Scenario) for candidate in candidates)


def test_fuzz_candidates_each_hit_a_targeted_low_or_zero_combo(sample_scenario):
    report_before = coverage_report([sample_scenario])
    target_combos = set(report_before["zero_coverage"]) | {
        combo for combo, _ in report_before["low_coverage"]
    }
    candidates = fuzz_toward_underrepresented([sample_scenario], random.Random(5), n=20)
    for candidate in candidates:
        data = candidate.as_dict()
        hits = any(
            (field_a, field_b, data[field_a], data[field_b]) in target_combos
            for field_a, field_b in field_pairs()
        )
        assert hits
