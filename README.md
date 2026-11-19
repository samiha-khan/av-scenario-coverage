# av-scenario-coverage

Synthetic driving scenario generation and test coverage analysis for autonomy validation.

Scenarios are represented as structured parameter vectors, not images or simulation runs, so the tool builds and runs fast with no dataset dependency. It covers the parts of validation that sit downstream of a model: given a set of test scenarios, which parameter combinations are undertested, which untested scenarios are worth running next, and which scenarios that used to pass have started failing.

## What it does

- Generates scenario vectors from a fixed schema (weather, lighting, agent mix, maneuver type, road type, ego speed)
- Measures combinatorial pairwise and 3-way coverage across the scenario set
- Generates new candidate scenarios targeted at undercovered parameter combinations (fuzzing), or builds a full t-way covering array
- Ranks untested scenarios with a Bayesian failure-rate model (deterministic rarity score, or Thompson sampling for adaptive testing), to prioritize what to run next
- Tracks pass/fail outcomes per scenario over time in SQLite, and flags statistically significant failure-rate regressions per scenario and per parameter combination
- Gates CI on the pairwise and 3-way coverage of a committed scenario suite

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

One caveat applies to every benchmark in this README: the failure model defines hard cases as combinations of two to four parameter values, which is exactly the structure that combinatorial coverage and pairwise failure-rate models are built around. The benchmarks show the methods behave as designed against a known ground truth; they are not evidence of the same gains on a real driving stack, where failures can depend on continuous parameters and interactions this schema does not capture.

## Coverage and fuzzing

Coverage is measured pairwise across all 15 field pairs (C(6,2)), not per field, since single-field coverage hides gaps like "we've tested night driving and we've tested fog driving, but never night and fog together."

Pairwise coverage has the same blind spot one level up. Four of the six hard combinations in the failure model involve three or four fields, and a set can cover every pair without ever containing night + high_pedestrian + residential. So coverage is also measured 3-way, across all 20 field triples (962 combinations).

Running the full pipeline on 80 randomly generated scenarios: 199/200 pairwise combinations covered (99.5%), 1 combination completely untested, 6 undertested. Fuzzing against the gaps generated 20 candidate scenarios and closed pairwise coverage to 100%.

For building a test set from scratch, greedy_covering_array constructs a set that covers every t-way combination (AETG-style greedy: each step seeds candidates from uncovered combinations and keeps the one covering the most). It needs about 24 scenarios for full pairwise coverage and about 99 for full 3-way coverage, against lower bounds of 20 and 80 and a full factorial of 2,160. It can also top up an existing set, adding only what that set is missing. Combinatorial t-way testing of this kind has been applied to automated driving before, e.g. ComOpT (arXiv 2110.00761, 2021) and the work surveyed in Tang et al., "A Survey on Automated Driving System Testing: Landscapes and Trends" (ACM TOSEM, 2023).

Comparison at roughly equal size, 30 seeds (python benchmark.py):

| strategy | size | pairwise | 3-way | all four hard combos of up to 3 factors tested |
|---|---|---|---|---|
| random | 100 | 99.7% | 86.1% | 28 / 30 seeds |
| random + pairwise fuzz | 100 | 100.0% | 86.3% | 24 / 30 seeds |
| 3-way covering array | 98.4 | 100.0% | 100.0% | 30 / 30 seeds |

Fuzzing to 100% pairwise coverage does not help with 3-way gaps and, in this benchmark, made them slightly more likely. The covering array guarantees every combination of up to three factors at the same budget. The two hard combinations that need four specific fields (for example night + fog + high_cyclist + merge) are still only hit by chance; guaranteeing those takes a 4-way covering array of about 320 scenarios.

## CI coverage gate

The suite CI measures is a committed file, scenarios/reference_suite.json, standing in for the set of scenarios a team actually runs. It currently holds 50 scenarios and covers 95.5% pairwise and 62.9% 3-way, with 357 three-way combinations untested. A build fails if a change to the suite, such as removing or editing scenarios, drops either number below the tracked baseline in coverage_baseline.json, and the failure message names untested combinations so the gap is actionable.

To see what it would take to close the gaps:

python check_coverage.py --suggest 3

prints the scenarios (as JSON) that would bring the suite to full 3-way coverage; for the current suite that is 60 more. After adding scenarios on purpose, delete coverage_baseline.json and rerun check_coverage.py to record the higher baseline.

## Prioritization

Each pairwise parameter combination gets a Beta posterior over its failure rate. The prior is a declared assumption (mean 10%, worth 5 runs of evidence, set in prioritization.py) that run history quickly overrides. The prioritizer never reads failure_model: that is the ground truth the prioritizer is scored against, and a real system would not have it.

Two rankings are available:

- prioritize: deterministic score = rarity of the scenario's least-seen pairwise combination x mean posterior failure rate across its pairs. Explainable, good for a fixed review list.
- thompson_prioritize: draws one failure rate from each pair's posterior and ranks by the average draw. Poorly tested combinations have wide posteriors and get explored; combinations with an established high failure rate get exploited. Re-rank after every batch of runs. This is the adaptive sampling idea behind recent rare-failure discovery work for autonomous driving (Sinha et al., "Rate-Informed Discovery via Bayesian Adaptive Multifidelity Sampling", CoRL 2024; Parashar et al., "Cost-aware Discovery of Contextual Failures using Bayesian Active Learning", CoRL 2025), reduced to a pairwise Beta model.

Benchmark: 300 runs in batches of 20, re-ranking a fresh pool of 400 candidates after each batch, mean of 12 seeds (python benchmark.py):

| strategy | failures found | distinct failing scenarios | pairwise combinations among failures |
|---|---|---|---|
| random | 38.6 | 37.3 | 169.4 / 200 |
| rarity x failure rate | 66.1 | 61.9 | 173.8 / 200 |
| thompson sampling | 109.0 | 72.0 | 137.8 / 200 |

Thompson sampling finds about 1.6x the failures of the deterministic score and 2.8x random. The trade-off is that it concentrates on the conditions where failures occur, so its failures span fewer pairwise combinations; use the deterministic score, or mix in random candidates, when breadth matters more than failure yield.

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
| 30 | 32.8 | 42% | 100% of builds | 0 |

When the pooled test fires, the top-ranked combination involves rain in 18 of 20 builds. Combinations that merely share scenarios with the rain set (for example urban + low speed) can also be flagged, since their pooled rate genuinely rose; read results from the top.

The original flip queries are kept as an audit trail:

- find_regressions: any scenario that passed at some point and later failed
- most_recent_regressions: only scenarios whose latest run failed with at least one earlier pass on record

## Tests

120 tests across models, generator, coverage, failure model, prioritization, regression, and the CI coverage check. Run with:

pytest

The numbers in the coverage, prioritization and regression sections come from:

python benchmark.py

## Structure

models.py           scenario schema and hashing
generator.py         scenario generation, weighted or uniform sampling
coverage.py          pairwise and t-way coverage, fuzzing, covering arrays
failure_model.py      synthetic ground truth failure function
prioritization.py     Bayesian rarity x failure rate scoring and Thompson sampling
regression.py        SQLite run tracking and regression queries
check_coverage.py     CI coverage gate on the committed suite, plus --suggest to close gaps
suite.py              load and save scenario suites as JSON
scenarios/            the committed reference suite CI gates on
benchmark.py          reproducible benchmarks behind the README numbers
