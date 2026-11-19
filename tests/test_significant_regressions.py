import random

import pytest

import failure_model
import regression
from generator import generate_scenarios

BEFORE = "2026-01-01T00:00:00+00:00"
CUTOFF = "2026-02-01T00:00:00+00:00"
AFTER = "2026-02-02T00:00:00+00:00"


def _record(conn, scenario, outcomes, timestamp):
    for passed in outcomes:
        regression.record_run(conn, scenario, passed, timestamp=timestamp)


def test_fisher_exact_matches_known_value():
    # 1/10 failures before, 8/10 after: reference one-sided p-value.
    assert regression.fisher_exact_greater(1, 10, 8, 10) == pytest.approx(0.0027387, rel=1e-4)


def test_fisher_exact_is_one_when_after_rate_is_not_higher():
    assert regression.fisher_exact_greater(5, 10, 0, 10) == pytest.approx(1.0)


def test_benjamini_hochberg_rejects_only_small_p_values():
    assert regression.benjamini_hochberg([0.001, 0.8, 0.02, 0.9], 0.05) == {0, 2}


def test_benjamini_hochberg_rejects_nothing_when_all_large():
    assert regression.benjamini_hochberg([0.2, 0.5, 0.9], 0.05) == set()


def test_single_flip_is_not_a_significant_regression(make_scenario):
    conn = regression.connect(":memory:")
    scenario = make_scenario()
    _record(conn, scenario, [True], BEFORE)
    _record(conn, scenario, [False], AFTER)
    assert regression.find_regressions(conn) != []
    assert regression.significant_regressions(conn, CUTOFF) == []


def test_clear_rate_increase_is_flagged(make_scenario):
    conn = regression.connect(":memory:")
    scenario = make_scenario()
    _record(conn, scenario, [True] * 19 + [False], BEFORE)
    _record(conn, scenario, [False] * 12 + [True] * 8, AFTER)
    flagged = regression.significant_regressions(conn, CUTOFF)
    assert len(flagged) == 1
    assert flagged[0].scenario == scenario
    assert flagged[0].before_failure_rate == 0.05
    assert flagged[0].after_failure_rate == 0.6


def test_noisy_but_unchanged_hard_scenario_is_not_flagged(make_scenario):
    conn = regression.connect(":memory:")
    scenario = make_scenario()
    _record(conn, scenario, [False] * 10 + [True] * 10, BEFORE)
    _record(conn, scenario, [False] * 11 + [True] * 9, AFTER)
    assert regression.significant_regressions(conn, CUTOFF) == []


def test_scenarios_without_runs_on_both_sides_are_skipped(make_scenario):
    conn = regression.connect(":memory:")
    _record(conn, make_scenario(), [False] * 10, AFTER)
    _record(conn, make_scenario(weather="rain"), [True] * 10, BEFORE)
    assert regression.significant_regressions(conn, CUTOFF) == []


def _simulate(conn, scenarios, runs_per_window, rng, after_probability=None):
    for scenario in scenarios:
        _record(
            conn,
            scenario,
            [failure_model.evaluate_scenario(scenario, rng) for _ in range(runs_per_window)],
            BEFORE,
        )
        if after_probability is None:
            outcomes = [failure_model.evaluate_scenario(scenario, rng) for _ in range(runs_per_window)]
        else:
            outcomes = [rng.random() >= after_probability(scenario) for _ in range(runs_per_window)]
        _record(conn, scenario, outcomes, AFTER)


def test_unchanged_system_produces_many_raw_flips_but_no_significant_regressions():
    rng = random.Random(7)
    scenarios = list(dict.fromkeys(generate_scenarios(80, seed=7)))
    conn = regression.connect(":memory:")
    _simulate(conn, scenarios, 10, rng)
    assert len(regression.find_regressions(conn)) > 5
    assert regression.significant_regressions(conn, CUTOFF) == []


def _rain_degradation(amount):
    def after_probability(scenario):
        base = failure_model.base_failure_probability(scenario)
        return min(1.0, base + amount) if scenario.weather.value == "rain" else base

    return after_probability


def test_injected_per_scenario_degradation_is_detected_with_enough_runs():
    rng = random.Random(11)
    scenarios = list(dict.fromkeys(generate_scenarios(80, seed=11)))
    degraded = {s for s in scenarios if s.weather.value == "rain"}
    assert degraded
    conn = regression.connect(":memory:")
    _simulate(conn, scenarios, 30, rng, _rain_degradation(0.6))
    flagged = {r.scenario for r in regression.significant_regressions(conn, CUTOFF)}
    assert flagged <= degraded
    assert len(flagged) >= len(degraded) // 2


def test_combination_regressions_find_nothing_when_system_is_unchanged():
    rng = random.Random(3)
    scenarios = list(dict.fromkeys(generate_scenarios(80, seed=3)))
    conn = regression.connect(":memory:")
    _simulate(conn, scenarios, 10, rng)
    assert regression.significant_combination_regressions(conn, CUTOFF) == []


def test_combination_regressions_rank_the_degraded_condition_first():
    rng = random.Random(5)
    scenarios = list(dict.fromkeys(generate_scenarios(80, seed=5)))
    conn = regression.connect(":memory:")
    _simulate(conn, scenarios, 10, rng, _rain_degradation(0.3))
    flagged = regression.significant_combination_regressions(conn, CUTOFF)
    assert flagged
    assert "rain" in (flagged[0].value_a, flagged[0].value_b)
    # The same 10 runs per scenario are not enough to flag any single
    # scenario after correction; pooling is what makes the shift visible.
    assert len(regression.significant_regressions(conn, CUTOFF)) < len(flagged)


def test_combination_regressions_pool_counts_across_scenarios(make_scenario):
    conn = regression.connect(":memory:")
    first = make_scenario(weather="rain", road_type="urban", lighting="day")
    second = make_scenario(weather="rain", road_type="urban", lighting="night")
    for scenario in (first, second):
        _record(conn, scenario, [True] * 10, BEFORE)
        _record(conn, scenario, [False] * 5 + [True] * 5, AFTER)
    pooled = {
        (c.field_a, c.field_b, c.value_a, c.value_b): c
        for c in regression.significant_combination_regressions(conn, CUTOFF)
    }
    rain_urban = pooled[("weather", "road_type", "rain", "urban")]
    assert rain_urban.scenario_count == 2
    assert (rain_urban.before_runs, rain_urban.before_failures) == (20, 0)
    assert (rain_urban.after_runs, rain_urban.after_failures) == (20, 10)
