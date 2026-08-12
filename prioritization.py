import failure_model
from coverage import field_pairs, pairwise_counts
from models import Scenario


def _combination_rarity(scenario: Scenario, coverage_counts) -> float:
    # Rarity is bounded by the scenario's least-seen pairwise combination,
    # not an average, so a scenario with even one unseen pair is treated as
    # rare overall rather than diluted by its more common pairs.
    data = scenario.as_dict()
    occurrences = [
        coverage_counts.get((field_a, field_b, data[field_a], data[field_b]), 0)
        for field_a, field_b in field_pairs()
    ]
    rarest_count = min(occurrences)
    return 1.0 / (1.0 + rarest_count)


def _historical_pairwise_stats(run_records):
    stats = {}
    for scenario, passed in run_records:
        data = scenario.as_dict()
        for field_a, field_b in field_pairs():
            key = (field_a, field_b, data[field_a], data[field_b])
            total, failures = stats.get(key, (0, 0))
            stats[key] = (total + 1, failures + (0 if passed else 1))
    return stats


def _historical_failure_rate(scenario: Scenario, historical_stats) -> float:
    data = scenario.as_dict()
    rates = []
    for field_a, field_b in field_pairs():
        key = (field_a, field_b, data[field_a], data[field_b])
        total, failures = historical_stats.get(key, (0, 0))
        if total:
            rates.append(failures / total)
    if not rates:
        # No run history touches any of this scenario's pairwise
        # combinations yet, so fall back to the synthetic ground truth
        # model's base probability as a prior instead of guessing.
        return failure_model.base_failure_probability(scenario)
    return sum(rates) / len(rates)


def rarity(scenario: Scenario, existing_scenarios) -> float:
    return _combination_rarity(scenario, pairwise_counts(existing_scenarios))


def historical_failure_rate(scenario: Scenario, run_records) -> float:
    return _historical_failure_rate(scenario, _historical_pairwise_stats(run_records))


def priority_score(scenario: Scenario, existing_scenarios, run_records) -> float:
    coverage_counts = pairwise_counts(existing_scenarios)
    historical_stats = _historical_pairwise_stats(run_records)
    return _combination_rarity(scenario, coverage_counts) * _historical_failure_rate(
        scenario, historical_stats
    )


def prioritize(candidates, existing_scenarios, run_records):
    coverage_counts = pairwise_counts(existing_scenarios)
    historical_stats = _historical_pairwise_stats(run_records)
    scored = [
        (
            candidate,
            _combination_rarity(candidate, coverage_counts)
            * _historical_failure_rate(candidate, historical_stats),
        )
        for candidate in candidates
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored
