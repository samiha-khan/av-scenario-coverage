import random

import pytest

import failure_model
import prioritization
from prioritization import (
    rarity,
    historical_failure_rate,
    priority_score,
    prioritize,
    thompson_prioritize,
)


def test_rarity_is_maximal_when_existing_set_is_empty(make_scenario):
    scenario = make_scenario()
    assert rarity(scenario, []) == 1.0


def test_rarity_drops_as_a_scenarios_pairwise_combinations_recur(make_scenario):
    scenario = make_scenario()
    rarity_unseen = rarity(scenario, [])
    rarity_seen_once = rarity(scenario, [scenario])
    rarity_seen_twice = rarity(scenario, [scenario, scenario])
    assert rarity_unseen > rarity_seen_once > rarity_seen_twice


def test_rarity_is_bounded_by_the_least_seen_pairwise_combination(make_scenario):
    scenario = make_scenario()
    # Overlaps some but not all of scenario's pairwise combinations, by
    # changing road_type across the existing set, so scenario's pairs
    # involving road_type stay unseen while the rest recur.
    partially_overlapping = [make_scenario(road_type="highway") for _ in range(5)]
    partial_rarity = rarity(scenario, partially_overlapping)
    fully_matching = [scenario for _ in range(5)]
    full_rarity = rarity(scenario, fully_matching)
    assert partial_rarity > full_rarity


def test_historical_failure_rate_is_the_declared_prior_when_no_history(make_scenario):
    scenario = make_scenario()
    assert historical_failure_rate(scenario, []) == pytest.approx(prioritization.PRIOR_FAILURE_RATE)


def test_historical_failure_rate_never_consults_the_ground_truth_model(make_scenario, monkeypatch):
    def forbidden(_scenario):
        raise AssertionError("prioritization must not read the synthetic ground truth")

    monkeypatch.setattr(failure_model, "base_failure_probability", forbidden)
    hard = make_scenario(lighting="night", agent_mix="high_cyclist")
    historical_failure_rate(hard, [])
    prioritize([hard], [], [])
    thompson_prioritize([hard], [], random.Random(0))


def test_historical_failure_rate_reflects_recorded_outcomes_for_matching_scenarios(
    make_scenario,
):
    scenario = make_scenario()
    run_records = [
        (scenario, False),
        (scenario, False),
        (scenario, True),
        (scenario, False),
    ]
    # Beta(0.5, 4.5) prior updated with 3 failures in 4 runs, identical for
    # every one of the scenario's pairwise combinations.
    alpha = prioritization.PRIOR_FAILURE_RATE * prioritization.PRIOR_STRENGTH + 3
    beta = (1 - prioritization.PRIOR_FAILURE_RATE) * prioritization.PRIOR_STRENGTH + 1
    assert historical_failure_rate(scenario, run_records) == pytest.approx(alpha / (alpha + beta))


def test_historical_failure_rate_converges_to_observed_rate_with_more_history(make_scenario):
    scenario = make_scenario()
    run_records = [(scenario, False)] * 300 + [(scenario, True)] * 100
    assert historical_failure_rate(scenario, run_records) == pytest.approx(0.75, abs=0.01)


def test_historical_failure_rate_ignores_unrelated_run_records(make_scenario):
    scenario = make_scenario()
    unrelated = make_scenario(
        weather="snow",
        lighting="night",
        agent_mix="high_cyclist",
        maneuver_type="merge",
        road_type="highway",
        ego_speed_bucket="high",
    )
    run_records = [(unrelated, False), (unrelated, False), (unrelated, False)]
    # Every field differs from scenario's defaults, so no pairwise
    # combination overlaps and this should stay at the prior rather than
    # picking up unrelated's high failure rate.
    assert historical_failure_rate(scenario, run_records) == pytest.approx(
        prioritization.PRIOR_FAILURE_RATE
    )


def test_priority_score_is_product_of_rarity_and_historical_failure_rate(make_scenario):
    scenario = make_scenario()
    existing = [make_scenario(road_type="highway")]
    run_records = [(scenario, False), (scenario, True)]
    expected = rarity(scenario, existing) * historical_failure_rate(scenario, run_records)
    assert priority_score(scenario, existing, run_records) == expected


def test_prioritize_orders_candidates_by_descending_score(make_scenario):
    common = make_scenario()
    rare = make_scenario(
        weather="snow", lighting="night", agent_mix="high_cyclist", maneuver_type="merge"
    )
    existing = [common] * 10
    run_records = [(common, False)] * 5 + [(common, True)] * 5
    ranked = prioritize([common, rare], existing, run_records)
    assert [candidate for candidate, _ in ranked] == [rare, common]
    scores = [score for _, score in ranked]
    assert scores == sorted(scores, reverse=True)


def test_prioritize_returns_all_candidates(make_scenario):
    candidates = [make_scenario(), make_scenario(weather="rain")]
    ranked = prioritize(candidates, [], [])
    assert {candidate for candidate, _ in ranked} == set(candidates)


def test_thompson_prioritize_returns_all_candidates_sorted(make_scenario):
    candidates = [make_scenario(), make_scenario(weather="rain"), make_scenario(weather="fog")]
    ranked = thompson_prioritize(candidates, [], random.Random(1))
    assert {candidate for candidate, _ in ranked} == set(candidates)
    scores = [score for _, score in ranked]
    assert scores == sorted(scores, reverse=True)


def test_thompson_prioritize_is_reproducible_for_a_given_seed(make_scenario):
    candidates = [make_scenario(weather=w) for w in ("clear", "rain", "fog", "snow")]
    first = thompson_prioritize(candidates, [], random.Random(42))
    second = thompson_prioritize(candidates, [], random.Random(42))
    assert first == second


def test_thompson_prioritize_favours_combinations_with_failure_history(make_scenario):
    failing = make_scenario(lighting="night", agent_mix="high_cyclist")
    passing = make_scenario()
    run_records = [(failing, False)] * 20 + [(passing, True)] * 20
    rng = random.Random(0)
    wins = sum(
        thompson_prioritize([failing, passing], run_records, rng)[0][0] == failing
        for _ in range(200)
    )
    assert wins > 190


def test_thompson_prioritize_still_explores_unseen_combinations(make_scenario):
    tested = make_scenario()
    unseen = make_scenario(
        weather="snow", lighting="night", agent_mix="high_pedestrian",
        maneuver_type="merge", road_type="highway", ego_speed_bucket="high",
    )
    # tested has a modest 10% failure rate, the same as the prior mean, so
    # the unseen candidate's wider posterior should win a fair share of draws.
    run_records = [(tested, False)] * 10 + [(tested, True)] * 90
    rng = random.Random(0)
    unseen_wins = sum(
        thompson_prioritize([tested, unseen], run_records, rng)[0][0] == unseen
        for _ in range(400)
    )
    assert 40 < unseen_wins < 360
