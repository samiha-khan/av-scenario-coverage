import json
import sys
from pathlib import Path

from coverage import coverage_percentage, tway_coverage_report
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


# 3-way coverage is gated alongside pairwise because full pairwise coverage
# can still leave three-factor combinations such as night + high_pedestrian
# + residential completely untested.
THREE_WAY_KEY = "three_way_coverage_percentage"


def _read_baseline_file(baseline_path):
    path = Path(baseline_path)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def load_baseline(baseline_path=BASELINE_PATH):
    data = _read_baseline_file(baseline_path)
    return None if data is None else data["coverage_percentage"]


def load_three_way_baseline(baseline_path=BASELINE_PATH):
    data = _read_baseline_file(baseline_path)
    return None if data is None else data.get(THREE_WAY_KEY)


def write_baseline(percentage, baseline_path=BASELINE_PATH, three_way_percentage=None):
    data = {"coverage_percentage": percentage}
    if three_way_percentage is not None:
        data[THREE_WAY_KEY] = three_way_percentage
    Path(baseline_path).write_text(json.dumps(data, indent=2) + "\n")


def check_coverage(baseline_path=BASELINE_PATH, seed=REFERENCE_SEED, count=REFERENCE_SCENARIO_COUNT):
    scenarios = generate_scenarios(count, seed=seed)
    current = coverage_percentage(scenarios)
    three_way_report = tway_coverage_report(scenarios, 3)
    current_three_way = three_way_report["coverage_percentage"]
    untested_three_way = len(three_way_report["zero_coverage"])
    baseline = load_baseline(baseline_path)

    if baseline is None:
        # First run with no tracked baseline yet: record one instead of
        # failing, since there's nothing to regress against.
        write_baseline(current, baseline_path, current_three_way)
        return 0, (
            f"No baseline found. Recorded initial coverage baseline: {current:.2f}% pairwise, "
            f"{current_three_way:.2f}% 3-way."
        )

    three_way_baseline = load_three_way_baseline(baseline_path)
    if three_way_baseline is None:
        # Baseline predates 3-way gating: add the 3-way figure without
        # touching the tracked pairwise number.
        write_baseline(baseline, baseline_path, current_three_way)
        three_way_baseline = current_three_way

    failures = []
    if current < baseline:
        failures.append(f"pairwise coverage {current:.2f}% is below recorded baseline {baseline:.2f}%")
    if current_three_way < three_way_baseline:
        failures.append(
            f"3-way coverage {current_three_way:.2f}% is below recorded baseline {three_way_baseline:.2f}%"
        )
    if failures:
        return 1, "Coverage regression: " + "; ".join(failures) + "."

    return 0, (
        f"Coverage check passed: pairwise {current:.2f}% (baseline {baseline:.2f}%), "
        f"3-way {current_three_way:.2f}% (baseline {three_way_baseline:.2f}%, "
        f"{untested_three_way} three-way combinations untested)."
    )


def main():
    exit_code, message = check_coverage()
    print(message)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
