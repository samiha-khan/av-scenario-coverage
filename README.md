# av-scenario-coverage

Synthetic driving scenario generation and test coverage analysis for autonomy validation.

Scenarios are represented as structured parameter vectors, not images or simulation runs, so the tool builds and runs fast with no dataset dependency. It covers the parts of validation that sit downstream of a model: given a set of test scenarios, which parameter combinations are undertested, which untested scenarios are worth running next, and which scenarios that used to pass have started failing.

## What it does

- Generates scenario vectors from a fixed schema (weather, lighting, agent mix, maneuver type, road type, ego speed)
- Measures combinatorial pairwise coverage across the scenario set
- Generates new candidate scenarios targeted at undercovered parameter combinations (fuzzing)
- Scores untested scenarios by rarity and historical failure rate, to prioritize what to run next
- Tracks pass/fail outcomes per scenario over time in SQLite, and flags scenarios that regressed
- Gates CI on a pairwise coverage baseline

## Schema

weather           clear, rain, fog, snow
lighting          day, dusk, night
agent_mix         mostly_vehicles, mixed_vru, high_cyclist, high_pedestrian, emergency_vehicle_present
maneuver_type     lane_change, turn, merge, stop
road_type         highway, urban, residential
ego_speed_bucket  low, medium, high

6 fields, 200 pairwise value combinations total.

## Failure model

There's no real classifier behind this project, on purpose, it's decoupled from perception-validation-suite so the coverage and prioritization logic can be tested against known ground truth instead of a black box.

Failure is a synthetic function: a fixed table of parameter combinations flagged as inherently hard (night + fog + high_cyclist + merge, snow + highway + high speed, and four others), each with a base failure probability, plus gaussian noise so outcomes aren't deterministic. Scenarios that don't match any hard combination default to a 2% baseline failure rate.

## Coverage and fuzzing

Coverage is measured pairwise across all 15 field pairs (C(6,2)), not per field, since single-field coverage hides gaps like "we've tested night driving and we've tested fog driving, but never night and fog together."

Running the full pipeline on 80 randomly generated scenarios: 199/200 pairwise combinations covered (99.5%), 1 combination completely untested, 6 undertested. Fuzzing against the gaps generated 20 candidate scenarios and closed coverage to 100%.

CI gates on a fixed reference set of 50 scenarios (seed 1234), which lands at 95.5% pairwise coverage, a build fails if a change drops that number.

## Prioritization

Score = rarity of the scenario's parameter combination in the existing set x historical failure rate for scenarios sharing those combinations. No learned model, this is a heuristic baseline that stays explainable.

If a scenario's combination has no run history yet, historical failure rate falls back to the synthetic model's base probability rather than assuming 0.

## Regression tracking

Every run of every scenario gets a row in SQLite, keyed on a hash of the scenario vector.

Scenarios fail at a nonzero rate even when nothing about the system changes, so a single pass followed by a single fail is not evidence of a regression. Running the same 80 scenarios twice with no change at all produces about 6.5 pass to fail flips on average. Simply ignoring noisy scenarios is not the answer either, because the inherently hard scenarios are exactly the noisy ones, and in practice that is where real regressions hide (Haben et al., "The Importance of Discerning Flaky from Fault-triggering Test Failures: A Case Study on the Chromium CI", 2023, found that ignoring failures of flaky tests would have missed about 76% of regression faults).

So detection compares failure rates instead of individual outcomes. Runs are split at a cutoff timestamp (for example, when a new build was deployed):

- significant_regressions: per scenario, one-sided Fisher exact test of whether the failure rate after the cutoff is higher than before it, with Benjamini-Hochberg correction across scenarios so that a large suite does not flag noise on every build
- significant_combination_regressions: the same test, but pooling all runs of all scenarios that share a pairwise parameter combination. Regressions usually follow operating conditions rather than one exact scenario vector, so pooling gives much more statistical power

Simulated on 80 scenarios over 20 seeds, with a +30 point failure rate increase injected into every rain scenario:

| runs per scenario per window | old most_recent_regressions false flags per build | per-scenario test detects | pooled test flags rain | pooled false flags when nothing changed |
|---|---|---|---|---|
| 5  | 13.8 | 0%  | 40% of builds | 0 |
| 10 | 18.1 | 0%  | 90% of builds | 0 |
| 30 | 32.8 | 42% | n/a | n/a |

When the pooled test fires, the top-ranked combination involves rain in 18 of 20 builds. Combinations that merely share scenarios with the rain set (for example urban + low speed) can also be flagged, since their pooled rate genuinely rose; read results from the top.

The original flip queries are kept as an audit trail:

- find_regressions: any scenario that passed at some point and later failed
- most_recent_regressions: only scenarios whose latest run failed with at least one earlier pass on record

## Tests

82 tests across models, generator, coverage, failure model, prioritization, regression, and the CI coverage check. Run with:

pytest

## Structure

models.py           scenario schema and hashing
generator.py         scenario generation, weighted or uniform sampling
coverage.py          pairwise coverage measurement and fuzzing
failure_model.py      synthetic ground truth failure function
prioritization.py     rarity x failure rate scoring
regression.py        SQLite run tracking and regression queries
check_coverage.py     CI coverage gate against a tracked baseline
