"""Reproducible benchmarks behind the numbers in the README.

Because failure_model is synthetic ground truth, each strategy can be scored
exactly. Run with: python benchmark.py
"""
import random
import statistics
from itertools import product

import failure_model
import regression
from coverage import field_pairs
from generator import generate_scenarios
from models import FIELD_ENUMS, SCHEMA_FIELDS, Scenario
from prioritization import prioritize, thompson_prioritize

SEEDS = range(12)
RUN_BUDGET = 300
BATCH_SIZE = 20
CANDIDATES_PER_BATCH = 400

ALL_SCENARIOS = [
    Scenario.from_values(dict(zip(SCHEMA_FIELDS, values)))
    for values in product(*[[m.value for m in FIELD_ENUMS[f]] for f in SCHEMA_FIELDS])
]


def _random_strategy(candidates, existing, run_records, rng):
    shuffled = list(candidates)
    rng.shuffle(shuffled)
    return shuffled


def _rarity_strategy(candidates, existing, run_records, rng):
    return [c for c, _ in prioritize(candidates, existing, run_records)]


def _thompson_strategy(candidates, existing, run_records, rng):
    return [c for c, _ in thompson_prioritize(candidates, run_records, rng)]


STRATEGIES = {
    "random": _random_strategy,
    "rarity x failure rate": _rarity_strategy,
    "thompson sampling": _thompson_strategy,
}


def run_discovery(strategy, seed):
    """Run RUN_BUDGET scenarios in batches, re-ranking after every batch."""
    rng = random.Random(seed)
    evaluation_rng = random.Random(seed + 10_000)
    run_records, existing = [], []
    failing = set()
    failures = 0
    while len(run_records) < RUN_BUDGET:
        candidates = rng.sample(ALL_SCENARIOS, CANDIDATES_PER_BATCH)
        for scenario in strategy(candidates, existing, run_records, rng)[:BATCH_SIZE]:
            passed = failure_model.evaluate_scenario(scenario, evaluation_rng)
            run_records.append((scenario, passed))
            existing.append(scenario)
            if not passed:
                failures += 1
                failing.add(scenario)
    failing_pairs = {
        (a, b, s.as_dict()[a], s.as_dict()[b]) for s in failing for a, b in field_pairs()
    }
    return failures, len(failing), len(failing_pairs)


def discovery_benchmark():
    print(f"Failure discovery: {RUN_BUDGET} runs, batches of {BATCH_SIZE}, mean of {len(SEEDS)} seeds")
    print(f"{'strategy':24s} {'failures':>9s} {'distinct failing':>17s} {'pairs among failures':>21s}")
    for name, strategy in STRATEGIES.items():
        results = [run_discovery(strategy, seed) for seed in SEEDS]
        means = [statistics.fmean(r[i] for r in results) for i in range(3)]
        print(f"{name:24s} {means[0]:9.1f} {means[1]:17.1f} {means[2]:17.1f}/200")


BEFORE, CUTOFF, AFTER = "2026-01-01", "2026-02-01", "2026-02-02"


def _simulate_build(seed, runs_per_window, degradation):
    rng = random.Random(seed)
    scenarios = list(dict.fromkeys(generate_scenarios(80, seed=seed)))
    conn = regression.connect(":memory:")
    for scenario in scenarios:
        for _ in range(runs_per_window):
            regression.record_run(conn, scenario, failure_model.evaluate_scenario(scenario, rng), BEFORE)
        probability = failure_model.base_failure_probability(scenario)
        if scenario.weather.value == "rain":
            probability = min(1.0, probability + degradation)
        for _ in range(runs_per_window):
            regression.record_run(conn, scenario, rng.random() >= probability, AFTER)
    return conn, {s for s in scenarios if s.weather.value == "rain"}


def regression_benchmark(seeds=range(20)):
    print("\nRegression detection: 80 scenarios, +30 point failure rate on every rain scenario")
    print(f"{'runs/window':>11s} {'old flip false flags':>21s} {'per-scenario detects':>21s} "
          f"{'pooled flags rain':>18s} {'pooled false flags, no change':>30s}")
    for runs in (5, 10, 30):
        old_false = detected = degraded_total = pooled_hits = null_flags = 0
        for seed in seeds:
            conn, degraded = _simulate_build(seed, runs, 0.3)
            old_false += len({r.scenario for r in regression.most_recent_regressions(conn)} - degraded)
            flagged = {r.scenario for r in regression.significant_regressions(conn, CUTOFF)}
            detected += len(flagged & degraded)
            degraded_total += len(degraded)
            pooled = regression.significant_combination_regressions(conn, CUTOFF)
            pooled_hits += bool(pooled) and "rain" in (pooled[0].value_a, pooled[0].value_b)
            null_conn, _ = _simulate_build(seed, runs, 0.0)
            null_flags += len(regression.significant_combination_regressions(null_conn, CUTOFF))
        n = len(seeds)
        print(f"{runs:11d} {old_false / n:21.1f} {detected / degraded_total:21.0%} "
              f"{pooled_hits / n:18.0%} {null_flags / n:30.2f}")


if __name__ == "__main__":
    discovery_benchmark()
    regression_benchmark()
