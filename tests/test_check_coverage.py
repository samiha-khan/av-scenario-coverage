import json

from check_coverage import check_coverage, load_baseline, write_baseline
from coverage import coverage_percentage
from generator import generate_scenarios


def test_first_run_bootstraps_baseline_and_passes(tmp_path):
    baseline_path = tmp_path / "coverage_baseline.json"
    exit_code, message = check_coverage(baseline_path=baseline_path, seed=1, count=50)
    assert exit_code == 0
    assert "Recorded initial coverage baseline" in message
    assert baseline_path.exists()


def test_bootstrapped_baseline_matches_computed_percentage(tmp_path):
    baseline_path = tmp_path / "coverage_baseline.json"
    check_coverage(baseline_path=baseline_path, seed=1, count=50)
    expected = coverage_percentage(generate_scenarios(50, seed=1))
    assert load_baseline(baseline_path) == expected


def test_passes_when_current_coverage_meets_baseline(tmp_path):
    baseline_path = tmp_path / "coverage_baseline.json"
    write_baseline(0.0, baseline_path)
    exit_code, message = check_coverage(baseline_path=baseline_path, seed=1, count=50)
    assert exit_code == 0
    assert "Coverage check passed" in message


def test_fails_when_current_coverage_drops_below_baseline(tmp_path):
    baseline_path = tmp_path / "coverage_baseline.json"
    write_baseline(100.0, baseline_path)
    exit_code, message = check_coverage(baseline_path=baseline_path, seed=1, count=50)
    assert exit_code == 1
    assert "Coverage regression" in message


def test_write_baseline_round_trips_through_json(tmp_path):
    baseline_path = tmp_path / "coverage_baseline.json"
    write_baseline(42.5, baseline_path)
    assert load_baseline(baseline_path) == 42.5
    assert json.loads(baseline_path.read_text()) == {"coverage_percentage": 42.5}


def test_load_baseline_returns_none_when_file_missing(tmp_path):
    baseline_path = tmp_path / "does_not_exist.json"
    assert load_baseline(baseline_path) is None
