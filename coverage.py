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


# --- t-way coverage -------------------------------------------------------
#
# Pairwise coverage alone can hide higher-order gaps: a set can contain
# night + fog, fog + merge and night + merge without ever containing
# night + fog + merge. Field-interaction failures in practice involve a
# small number of factors, so 3-way coverage closes most of that gap at a
# modest cost in scenarios. Keys are (fields, values) tuples so any strength
# shares one representation.


def field_combinations(strength):
    if not 1 <= strength <= len(SCHEMA_FIELDS):
        raise ValueError(f"strength must be between 1 and {len(SCHEMA_FIELDS)}, got {strength}")
    return list(combinations(SCHEMA_FIELDS, strength))


def all_tway_combinations(strength):
    combos = []
    for fields in field_combinations(strength):
        value_lists = [[member.value for member in FIELD_ENUMS[field]] for field in fields]
        for values in product(*value_lists):
            combos.append((fields, values))
    return combos


def _tway_keys(data, field_groups):
    return [(fields, tuple(data[field] for field in fields)) for fields in field_groups]


def tway_counts(scenarios, strength):
    field_groups = field_combinations(strength)
    counts = Counter()
    for scenario in scenarios:
        counts.update(_tway_keys(scenario.as_dict(), field_groups))
    return counts


def tway_coverage_report(scenarios, strength, low_threshold=LOW_COVERAGE_THRESHOLD):
    combos = all_tway_combinations(strength)
    counts = tway_counts(scenarios, strength)
    zero_coverage = [combo for combo in combos if counts.get(combo, 0) == 0]
    low_coverage = [
        (combo, counts[combo]) for combo in combos if 0 < counts.get(combo, 0) < low_threshold
    ]
    covered = len(combos) - len(zero_coverage)
    return {
        "strength": strength,
        "total_combinations": len(combos),
        "covered_combinations": covered,
        "coverage_percentage": 100.0 * covered / len(combos),
        "zero_coverage": zero_coverage,
        "low_coverage": low_coverage,
    }


def tway_coverage_percentage(scenarios, strength):
    return tway_coverage_report(scenarios, strength)["coverage_percentage"]


def fuzz_toward_tway_gaps(scenarios, rng: random.Random, strength, n=10, low_threshold=LOW_COVERAGE_THRESHOLD):
    """Like fuzz_toward_underrepresented, but targets uncovered t-way combinations."""
    if not scenarios:
        return []
    report = tway_coverage_report(scenarios, strength, low_threshold)
    targets = report["zero_coverage"] + [combo for combo, _ in report["low_coverage"]]
    if not targets:
        return []
    candidates = []
    for _ in range(n):
        fields, values = rng.choice(targets)
        data = rng.choice(scenarios).as_dict()
        data.update(zip(fields, values))
        candidates.append(Scenario.from_values(data))
    return candidates


def greedy_covering_array(strength, rng: random.Random, existing=(), candidates_per_step=50):
    """Return new scenarios that, added to existing, cover every t-way combination.

    Greedy construction in the style of AETG: each step seeds a candidate
    with one still-uncovered combination, fills the remaining fields at
    random, and keeps whichever of candidates_per_step candidates covers the
    most uncovered combinations. Not minimal, but close to the lower bound
    in practice and far smaller than the full factorial.
    """
    field_groups = field_combinations(strength)
    uncovered = set(all_tway_combinations(strength)) - set(tway_counts(existing, strength))
    field_values = {field: [member.value for member in FIELD_ENUMS[field]] for field in SCHEMA_FIELDS}
    added = []
    while uncovered:
        ordered_uncovered = sorted(uncovered)
        best_data, best_gain = None, -1
        for _ in range(candidates_per_step):
            fields, values = rng.choice(ordered_uncovered)
            data = {field: rng.choice(field_values[field]) for field in SCHEMA_FIELDS}
            data.update(zip(fields, values))
            gain = sum(key in uncovered for key in _tway_keys(data, field_groups))
            if gain > best_gain:
                best_data, best_gain = data, gain
        uncovered.difference_update(_tway_keys(best_data, field_groups))
        added.append(Scenario.from_values(best_data))
    return added
