import random

from coverage import field_pairs, pairwise_counts
from models import Scenario

# Declared prior belief about the failure rate of any pairwise parameter
# combination before it has been run: a Beta distribution with mean
# PRIOR_FAILURE_RATE, worth PRIOR_STRENGTH pseudo-runs of evidence. This is
# an explicit, tunable assumption that real run history quickly overrides.
# It deliberately does not consult failure_model, which is the synthetic
# ground truth the prioritizer is evaluated against and would not exist for
# a real system.
PRIOR_FAILURE_RATE = 0.1
PRIOR_STRENGTH = 5.0


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


def _pair_posteriors(scenario: Scenario, historical_stats):
    # Beta posterior (alpha, beta) over the failure rate of each of the
    # scenario's pairwise combinations. Unseen combinations get the prior.
    prior_alpha = PRIOR_FAILURE_RATE * PRIOR_STRENGTH
    prior_beta = (1.0 - PRIOR_FAILURE_RATE) * PRIOR_STRENGTH
    data = scenario.as_dict()
    posteriors = []
    for field_a, field_b in field_pairs():
        total, failures = historical_stats.get((field_a, field_b, data[field_a], data[field_b]), (0, 0))
        posteriors.append((prior_alpha + failures, prior_beta + total - failures))
    return posteriors


def _historical_failure_rate(scenario: Scenario, historical_stats) -> float:
    posteriors = _pair_posteriors(scenario, historical_stats)
    return sum(alpha / (alpha + beta) for alpha, beta in posteriors) / len(posteriors)


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


def thompson_prioritize(candidates, run_records, rng: random.Random):
    """Rank candidates by a Thompson sample of their failure rate.

    For each candidate, draw one failure rate from the Beta posterior of
    each of its pairwise combinations and average them. Combinations with
    little history have wide posteriors, so they occasionally draw high and
    get explored; combinations with a well-established high failure rate
    draw high consistently and get exploited. Re-rank after every batch of
    runs so new results feed back in.

    This is the adaptive sampling approach used for rare-failure discovery
    in autonomous driving evaluation, e.g. Sinha et al., "Rate-Informed
    Discovery via Bayesian Adaptive Multifidelity Sampling" (CoRL 2024) and
    Parashar et al., "Cost-aware Discovery of Contextual Failures using
    Bayesian Active Learning" (CoRL 2025), reduced to a pairwise Beta model.
    """
    historical_stats = _historical_pairwise_stats(run_records)
    scored = []
    for candidate in candidates:
        posteriors = _pair_posteriors(candidate, historical_stats)
        sampled = sum(rng.betavariate(alpha, beta) for alpha, beta in posteriors) / len(posteriors)
        scored.append((candidate, sampled))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored
