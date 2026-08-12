import random
from collections import Counter
from itertools import combinations, product

from models import SCHEMA_FIELDS, FIELD_ENUMS, Scenario

# A pairwise combination below this occurrence count is flagged as low
# coverage. Combinations at or above this count are considered adequately
# exercised by the current scenario set.
LOW_COVERAGE_THRESHOLD = 2


def field_pairs():
    return list(combinations(SCHEMA_FIELDS, 2))


def all_pairwise_combinations():
    combos = []
    for field_a, field_b in field_pairs():
        values_a = [member.value for member in FIELD_ENUMS[field_a]]
        values_b = [member.value for member in FIELD_ENUMS[field_b]]
        for value_a, value_b in product(values_a, values_b):
            combos.append((field_a, field_b, value_a, value_b))
    return combos


def pairwise_counts(scenarios):
    counts = Counter()
    for scenario in scenarios:
        data = scenario.as_dict()
        for field_a, field_b in field_pairs():
            counts[(field_a, field_b, data[field_a], data[field_b])] += 1
    return counts


def coverage_report(scenarios, low_threshold=LOW_COVERAGE_THRESHOLD):
    combos = all_pairwise_combinations()
    counts = pairwise_counts(scenarios)
    zero_coverage = []
    low_coverage = []
    covered = 0
    for combo in combos:
        count = counts.get(combo, 0)
        if count == 0:
            zero_coverage.append(combo)
        else:
            covered += 1
            if count < low_threshold:
                low_coverage.append((combo, count))
    return {
        "total_combinations": len(combos),
        "covered_combinations": covered,
        "coverage_percentage": 100.0 * covered / len(combos),
        "zero_coverage": zero_coverage,
        "low_coverage": low_coverage,
    }


def coverage_percentage(scenarios, low_threshold=LOW_COVERAGE_THRESHOLD):
    return coverage_report(scenarios, low_threshold)["coverage_percentage"]


def fuzz_toward_underrepresented(scenarios, rng: random.Random, n=10, low_threshold=LOW_COVERAGE_THRESHOLD):
    if not scenarios:
        return []
    report = coverage_report(scenarios, low_threshold)
    targets = report["zero_coverage"] + [combo for combo, _ in report["low_coverage"]]
    if not targets:
        return []
    candidates = []
    for _ in range(n):
        field_a, field_b, value_a, value_b = rng.choice(targets)
        base = rng.choice(scenarios)
        data = base.as_dict()
        data[field_a] = value_a
        data[field_b] = value_b
        candidates.append(Scenario.from_values(data))
    return candidates
