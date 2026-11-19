import argparse
import json
import random
import sys
from pathlib import Path

from coverage import coverage_report, greedy_covering_array, tway_coverage_report
from suite import SUITE_PATH, load_suite

BASELINE_PATH = Path(__file__).resolve().parent / "coverage_baseline.json"

# How many untested combinations to name in the gate's output. Enough to
# act on without flooding the CI log.
MAX_LISTED_GAPS = 5


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


def _format_gap(fields, values):
    return " + ".join(f"{field}={value}" for field, value in zip(fields, values))


def _gap_summary(pairwise_report, three_way_report):
    pairwise_gaps = [((a, b), (va, vb)) for a, b, va, vb in pairwise_report["zero_coverage"]]
    gaps = pairwise_gaps + three_way_report["zero_coverage"]
    if not gaps:
        return ""
    listed = "; ".join(_format_gap(fields, values) for fields, values in gaps[:MAX_LISTED_GAPS])
    more = len(gaps) - MAX_LISTED_GAPS
    return f" Untested, e.g.: {listed}" + (f" (and {more} more)." if more > 0 else ".")


def check_coverage(baseline_path=BASELINE_PATH, suite_path=SUITE_PATH, scenarios=None):
    """Gate the committed scenario suite's coverage against the tracked baseline.

    The suite file is the set of scenarios actually run, so the gate fails
    when a change to it (removing or editing scenarios) leaves combinations
    untested that used to be covered.
    """
    if scenarios is None:
        scenarios = load_suite(suite_path)
    pairwise_report = coverage_report(scenarios)
    three_way_report = tway_coverage_report(scenarios, 3)
    current = pairwise_report["coverage_percentage"]
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
    gaps = _gap_summary(pairwise_report, three_way_report)
    if failures:
        return 1, "Coverage regression: " + "; ".join(failures) + "." + gaps

    return 0, (
        f"Coverage check passed: pairwise {current:.2f}% (baseline {baseline:.2f}%), "
        f"3-way {current_three_way:.2f}% (baseline {three_way_baseline:.2f}%, "
        f"{untested_three_way} three-way combinations untested).{gaps}"
    )


def suggest_additions(strength, suite_path=SUITE_PATH, seed=0):
    """Scenarios that, added to the suite, would close every strength-way gap."""
    return greedy_covering_array(strength, random.Random(seed), existing=load_suite(suite_path))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Gate scenario suite coverage against the tracked baseline.")
    parser.add_argument(
        "--suggest",
        type=int,
        metavar="STRENGTH",
        help="instead of gating, print scenarios that would close every STRENGTH-way gap in the suite",
    )
    args = parser.parse_args(argv)
    if args.suggest is not None:
        additions = suggest_additions(args.suggest)
        print(json.dumps([scenario.as_dict() for scenario in additions], indent=2))
        print(f"{len(additions)} scenarios close every {args.suggest}-way gap.", file=sys.stderr)
        return 0
    exit_code, message = check_coverage()
    print(message)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
