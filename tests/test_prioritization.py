import failure_model
from prioritization import (
    rarity,
    historical_failure_rate,
    priority_score,
    prioritize,
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


def test_historical_failure_rate_falls_back_to_failure_model_when_no_history(make_scenario):
    scenario = make_scenario()
    assert historical_failure_rate(scenario, []) == failure_model.base_failure_probability(
        scenario
    )


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
    assert historical_failure_rate(scenario, run_records) == 0.75


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
    # combination overlaps and this should fall back to the synthetic
    # baseline rather than picking up unrelated's high failure rate.
    assert historical_failure_rate(scenario, run_records) == failure_model.base_failure_probability(
        scenario
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
