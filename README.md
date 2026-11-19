# av-scenario-coverage

Synthetic driving scenario generation and test coverage analysis for autonomy validation. Given a set of test scenarios, it answers three questions: which parameter combinations are undertested, which untested scenarios are worth running next, and which scenarios that used to pass have started failing.

Scenarios are structured parameter vectors, not images or simulation runs, so everything runs in seconds with no dataset dependency.

## Highlights

- **Regression detection without false alarms:** naive pass-to-fail flip detection flags ~18 scenarios per build even when nothing changed. Rate-based detection with multiple-comparison correction flags 0, and still catches an injected degradation in 90% of builds.
- **Adaptive test prioritization:** Thompson sampling over Bayesian failure-rate estimates finds 2.8x more failures than random testing and 1.6x more than a rarity-based heuristic, on the same run budget.
- **Guaranteed 3-way coverage:** a greedy covering array tests every combination of any three parameters in ~99 scenarios, out of 2,160 possible.
- **Actionable CI gate:** CI fails if a change to the committed test suite reduces pairwise or 3-way coverage, and names the combinations left untested.

Numbers are reproducible with `python benchmark.py` and measured against a synthetic failure model (see caveat below).

## Quick start

Requires Python 3.11+ and pytest.

```bash
git clone https://github.com/samiha-khan/av-scenario-coverage.git
cd av-scenario-coverage
pip install pytest
pytest -q                              # 120 tests
python benchmark.py                    # reproduce the numbers
python check_coverage.py               # run the CI coverage gate
python check_coverage.py --suggest 3   # scenarios that would close every 3-way gap
```

## Structure

```
models.py            scenario schema and hashing
generator.py         scenario generation, weighted or uniform sampling
coverage.py          pairwise and t-way coverage, fuzzing, covering arrays
failure_model.py     synthetic ground truth failure function
prioritization.py    Bayesian failure-rate scoring and Thompson sampling
regression.py        SQLite run tracking and regression detection
check_coverage.py    CI coverage gate on the committed suite
suite.py             load and save scenario suites as JSON
scenarios/           the committed reference suite CI gates on
benchmark.py         reproducible benchmarks
```

## Details

<details>
<summary><b>Schema and failure model</b></summary>

```
weather           clear, rain, fog, snow
lighting          day, dusk, night
agent_mix         mostly_vehicles, mixed_vru, high_cyclist, high_pedestrian, emergency_vehicle_present
maneuver_type     lane_change, turn, merge, stop
road_type         highway, urban, residential
ego_speed_bucket  low, medium, high
```

6 fields, 2,160 possible scenarios, 200 pairwise and 962 three-way value combinations.

There's no real classifier behind this project, on purpose: it's decoupled from any perception model so the coverage and prioritization logic can be tested against known ground truth instead of a black box. Failure is a synthetic function: a fixed table of parameter combinations flagged as inherently hard (night + fog + high_cyclist + merge, snow + highway + high speed, and four others), each with a base failure probability, plus Gaussian noise. Scenarios that match no hard combination fail 2% of the time.

**Caveat:** the failure model defines hard cases as combinations of two to four parameter values, which is exactly the structure combinatorial coverage and pairwise failure-rate models are built around. The benchmarks show the methods behave as designed against a known ground truth; they are not evidence of the same gains on a real driving stack, where failures can depend on continuous parameters and interactions this schema does not capture.

</details>

<details>
<summary><b>Coverage, fuzzing and covering arrays</b></summary>

Coverage is measured pairwise across all 15 field pairs, since single-field coverage hides gaps like "we've tested night and we've tested fog, but never night and fog together." Pairwise has the same blind spot one level up: four of the six hard combinations involve three or four fields, and a set can cover every pair without ever containing night + high_pedestrian + residential. So coverage is also measured 3-way, across all 20 field triples (962 combinations).

`fuzz_toward_underrepresented` and `fuzz_toward_tway_gaps` mutate existing scenarios toward uncovered combinations. `greedy_covering_array` builds a set covering every t-way combination (AETG-style greedy), needing about 24 scenarios for full pairwise and about 99 for full 3-way coverage (lower bounds 20 and 80), and can top up an existing set. Combinatorial t-way testing has been applied to automated driving before, e.g. ComOpT (arXiv 2110.00761, 2021) and the work surveyed in Tang et al., "A Survey on Automated Driving System Testing: Landscapes and Trends" (ACM TOSEM, 2023).

| strategy (~100 scenarios, 30 seeds) | pairwise | 3-way | all ≤3-factor hard combos tested |
|---|---|---|---|
| random | 99.7% | 86.1% | 28 / 30 seeds |
| random + pairwise fuzz | 100.0% | 86.3% | 24 / 30 seeds |
| 3-way covering array | 100.0% | 100.0% | 30 / 30 seeds |

Fuzzing to 100% pairwise coverage doesn't help with 3-way gaps. The covering array guarantees every combination of up to three factors at the same budget; the two hard combinations needing four specific fields are still only hit by chance (guaranteeing those takes a 4-way array of ~320 scenarios).

</details>

<details>
<summary><b>CI coverage gate</b></summary>

CI measures a committed suite, `scenarios/reference_suite.json` (50 scenarios: 95.5% pairwise, 62.9% 3-way, 357 three-way combinations untested). A build fails if a change to the suite drops either number below the baseline in `coverage_baseline.json`, and the message names untested combinations. `python check_coverage.py --suggest 3` prints the 60 scenarios that would close every 3-way gap. After adding scenarios on purpose, delete `coverage_baseline.json` and rerun to record the new baseline.

</details>

<details>
<summary><b>Prioritization</b></summary>

Each pairwise combination gets a Beta posterior over its failure rate, starting from a declared prior (mean 10%, worth 5 runs). The prioritizer never reads `failure_model`, since a real system would have no ground truth.

- `prioritize`: deterministic score = rarity of the least-seen pairwise combination x mean posterior failure rate. Explainable, good for a fixed review list.
- `thompson_prioritize`: samples a failure rate from each pair's posterior and ranks by the average. Poorly tested combinations get explored, known failure-prone ones get exploited. The adaptive sampling idea behind recent rare-failure discovery work (Sinha et al., CoRL 2024; Parashar et al., CoRL 2025), reduced to a pairwise Beta model.

| strategy (300 runs, batches of 20, 12 seeds) | failures found | distinct failing scenarios | pairwise combos among failures |
|---|---|---|---|
| random | 38.6 | 37.3 | 169.4 / 200 |
| rarity x failure rate | 66.1 | 61.9 | 173.8 / 200 |
| Thompson sampling | 109.0 | 72.0 | 137.8 / 200 |

Trade-off: Thompson sampling concentrates where failures occur, so its failures span fewer combinations. Use the deterministic score when breadth matters more than yield.

</details>

<details>
<summary><b>Regression detection</b></summary>

Scenarios fail at a nonzero rate even when nothing changes: rerunning the same 80 scenarios produces ~6.5 pass-to-fail flips with no system change at all. Ignoring noisy scenarios isn't the answer either, since hard scenarios are the noisy ones and that's where real regressions hide (Haben et al., 2023, found ignoring flaky-test failures in Chromium CI would have missed ~76% of regression faults).

So detection compares failure rates before and after a cutoff (e.g. a deploy):

- `significant_regressions`: per scenario, one-sided Fisher exact test with Benjamini-Hochberg correction across scenarios
- `significant_combination_regressions`: same test, pooling all scenarios sharing a pairwise combination, since regressions usually follow conditions (e.g. rain), not one exact scenario

| runs per window (+30 pt degradation on rain, 20 seeds) | naive flip false flags / build | per-scenario detects | pooled flags rain | pooled false flags, no change |
|---|---|---|---|---|
| 5 | 13.8 | 0% | 40% | 0 |
| 10 | 18.1 | 0% | 90% | 0 |
| 30 | 32.8 | 42% | 100% | 0 |

The original flip queries (`find_regressions`, `most_recent_regressions`) are kept as an audit trail.

</details>
