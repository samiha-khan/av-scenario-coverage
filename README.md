# av-scenario-coverage

A checklist for self-driving tests.

A car can meet rain, night, a highway, a cyclist, and a merge in thousands of combinations. Testing rain on its own, and night on its own, still leaves rain at night untested. This project keeps that checklist and answers four questions:

1. Which situations have we already tried?
2. Which combinations did we skip?
3. Which skipped test is the risky one to run next?
4. Which tests used to pass and now fail?

Each test is six plain facts, not a video and not a drive in a simulator. That is why it runs on a laptop in about a second.

| Fact | Choices |
| --- | --- |
| Weather | clear, rain, fog, snow |
| Light | day, dusk, night |
| Who else is on the road | mostly cars, a mix of people and bikes, lots of cyclists, lots of pedestrians, an emergency vehicle |
| What the car is doing | change lanes, turn, merge, stop |
| Where | highway, city street, residential street |
| Speed | low, medium, high |

Six facts produce 200 pairs, such as "fog + night" or "snow + highway." The checklist counts pairs, because a pair is where the hole usually hides.

## Try the checklist

```bash
python3 - <<'PY'
from coverage import coverage_report
from generator import generate_scenarios

scenarios = generate_scenarios(80, seed=7)
report = coverage_report(scenarios)
print(
    f"{report['covered_combinations']} of {report['total_combinations']} pairs covered"
)
print("missing:", report["zero_coverage"])
PY
```

With seed 7, 80 random situations cover 197 of 200 pairs. Three pairs never appear, including fog with lots of pedestrians, and snow during a lane change.

Ask for 20 new situations aimed at those holes and the list closes to 200 of 200. The same 80 situations, run twice, produce 10 that passed the first time and failed the second. Those 10 are the ones to look at before trusting a new version of the software.

```bash
pytest
python3 check_coverage.py
```

`pytest` runs 69 tests. `check_coverage.py` checks a fixed set of 50 situations (seed 1234). That set covers 95.5% of the pairs. The check fails if a code change drops that number.

## Where pass and fail come from

This repository does not include a camera model. Pass and fail come from a short written list of hard situations: night and fog with many cyclists merging, snow on a highway at high speed, and four others. Hard situations fail more often. Everything else fails about 2% of the time, with a little randomness, so the same test can flip between runs.

The checklist can then be tested against known answers. A separate project holds the perception model.

## How the four questions are scored

**Coverage.** Every pair of facts is counted. A pair seen fewer than 2 times is thin. A pair seen 0 times is a hole.

**Fill the holes.** New tests are built by copying a situation you already have and rewriting the two facts that were missing.

**What to run next.** Score = how rare the pair is × how often similar tests have failed. A rare situation with no history yet uses the written failure rate, so a brand-new hard case is not treated as safe.

**Regressions.** Every result is saved in a small SQLite database, one row per run. A regression is a test that passed at least once and failed later. The stricter list is tests whose latest run failed after an earlier pass. That stricter list is what a release check would block on.

## Files

| File | Role |
| --- | --- |
| `models.py` | The six facts, and a fingerprint for each situation |
| `generator.py` | Builds situations, evenly or with weights |
| `coverage.py` | Counts pairs and fills holes |
| `failure_model.py` | The written pass/fail table |
| `prioritization.py` | Ranks the next tests |
| `regression.py` | Saves runs and finds tests that used to pass |
| `check_coverage.py` | Fails the build if pair coverage drops |
| `coverage_baseline.json` | The 95.5% line the check compares against |
