import json

from check_coverage import check_coverage, load_baseline, load_three_way_baseline, write_baseline
from coverage import coverage_percentage, tway_coverage_percentage
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


def test_bootstrapped_baseline_records_three_way_coverage(tmp_path):
    baseline_path = tmp_path / "coverage_baseline.json"
    check_coverage(baseline_path=baseline_path, seed=1, count=50)
    expected = tway_coverage_percentage(generate_scenarios(50, seed=1), 3)
    assert load_three_way_baseline(baseline_path) == expected


def test_legacy_pairwise_only_baseline_gains_three_way_entry_and_passes(tmp_path):
    baseline_path = tmp_path / "coverage_baseline.json"
    write_baseline(0.0, baseline_path)
    assert load_three_way_baseline(baseline_path) is None
    exit_code, _ = check_coverage(baseline_path=baseline_path, seed=1, count=50)
    assert exit_code == 0
    assert load_baseline(baseline_path) == 0.0
    assert load_three_way_baseline(baseline_path) is not None


def test_fails_when_three_way_coverage_drops_below_baseline(tmp_path):
    baseline_path = tmp_path / "coverage_baseline.json"
    write_baseline(0.0, baseline_path, three_way_percentage=100.0)
    exit_code, message = check_coverage(baseline_path=baseline_path, seed=1, count=50)
    assert exit_code == 1
    assert "3-way coverage" in message
    assert "pairwise coverage" not in message


def test_passing_message_reports_untested_three_way_combinations(tmp_path):
    baseline_path = tmp_path / "coverage_baseline.json"
    write_baseline(0.0, baseline_path, three_way_percentage=0.0)
    exit_code, message = check_coverage(baseline_path=baseline_path, seed=1, count=50)
    assert exit_code == 0
    assert "three-way combinations untested" in message


def test_passes_when_current_coverage_meets_baseline(tmp_path):
    baseline_path = tmp_path / "coverage_baseline.json"
    write_baseline(0.0, baseline_path)
    exit_code, message = check_coverage(baseline_path=baseline_path, seed=1, count=50)
    assert exit_code == 0
    assert "Coverage check passed" in message


def test_fails_when_current_coverage_drops_below_baseline(tmp_path):
    baseline_path = tmp_path / "coverage_baseline.json"
    write_baseline(100.0, baseline_path, three_way_percentage=0.0)
    exit_code, message = check_coverage(baseline_path=baseline_path, seed=1, count=50)
    assert exit_code == 1
    assert "Coverage regression" in message
    assert "pairwise coverage" in message


def test_write_baseline_round_trips_through_json(tmp_path):
    baseline_path = tmp_path / "coverage_baseline.json"
    write_baseline(42.5, baseline_path)
    assert load_baseline(baseline_path) == 42.5
    assert json.loads(baseline_path.read_text()) == {"coverage_percentage": 42.5}


def test_load_baseline_returns_none_when_file_missing(tmp_path):
    baseline_path = tmp_path / "does_not_exist.json"
    assert load_baseline(baseline_path) is None


def test_write_baseline_includes_three_way_when_given(tmp_path):
    baseline_path = tmp_path / "coverage_baseline.json"
    write_baseline(42.5, baseline_path, three_way_percentage=12.5)
    assert json.loads(baseline_path.read_text()) == {
        "coverage_percentage": 42.5,
        "three_way_coverage_percentage": 12.5,
    }
