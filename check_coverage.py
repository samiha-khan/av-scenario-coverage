import json
import sys
from pathlib import Path

from coverage import coverage_percentage
from generator import generate_scenarios

BASELINE_PATH = Path(__file__).resolve().parent / "coverage_baseline.json"

# Fixed seed and size for the reference scenario set CI measures coverage
# against. Deterministic so the reported percentage is reproducible run to
# run rather than drifting with unrelated random noise. 50 scenarios at this
# seed covers 95.5% of the pairwise space, leaving headroom for a real
# regression to actually move the number instead of the gate always sitting
# at a saturated 100%.
REFERENCE_SEED = 1234
REFERENCE_SCENARIO_COUNT = 50


def load_baseline(baseline_path=BASELINE_PATH):
    path = Path(baseline_path)
    if not path.exists():
        return None
    return json.loads(path.read_text())["coverage_percentage"]


def write_baseline(percentage, baseline_path=BASELINE_PATH):
    Path(baseline_path).write_text(json.dumps({"coverage_percentage": percentage}, indent=2) + "\n")


def check_coverage(baseline_path=BASELINE_PATH, seed=REFERENCE_SEED, count=REFERENCE_SCENARIO_COUNT):
    scenarios = generate_scenarios(count, seed=seed)
    current = coverage_percentage(scenarios)
    baseline = load_baseline(baseline_path)

    if baseline is None:
        # First run with no tracked baseline yet: record one instead of
        # failing, since there's nothing to regress against.
        write_baseline(current, baseline_path)
        return 0, f"No baseline found. Recorded initial coverage baseline: {current:.2f}%"

    if current < baseline:
        return 1, (
            f"Coverage regression: current coverage {current:.2f}% is below "
            f"recorded baseline {baseline:.2f}%."
        )

    return 0, f"Coverage check passed: current coverage {current:.2f}% (baseline {baseline:.2f}%)."


def main():
    exit_code, message = check_coverage()
    print(message)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
