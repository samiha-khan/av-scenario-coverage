import json

from check_coverage import check_coverage, load_baseline, load_three_way_baseline, write_baseline
from coverage import coverage_percentage, tway_coverage_percentage
from generator import generate_scenarios


def test_first_run_bootstraps_baseline_and_passes(tmp_path):
    baseline_path = tmp_path / "coverage_baseline.json"
    exit_code, message = check_coverage(baseline_path=baseline_path, scenarios=generate_scenarios(50, seed=1))
    assert exit_code == 0
    assert "Recorded initial coverage baseline" in message
    assert baseline_path.exists()


def test_bootstrapped_baseline_matches_computed_percentage(tmp_path):
    baseline_path = tmp_path / "coverage_baseline.json"
    check_coverage(baseline_path=baseline_path, scenarios=generate_scenarios(50, seed=1))
    expected = coverage_percentage(generate_scenarios(50, seed=1))
    assert load_baseline(baseline_path) == expected


def test_bootstrapped_baseline_records_three_way_coverage(tmp_path):
    baseline_path = tmp_path / "coverage_baseline.json"
    check_coverage(baseline_path=baseline_path, scenarios=generate_scenarios(50, seed=1))
    expected = tway_coverage_percentage(generate_scenarios(50, seed=1), 3)
    assert load_three_way_baseline(baseline_path) == expected


def test_legacy_pairwise_only_baseline_gains_three_way_entry_and_passes(tmp_path):
    baseline_path = tmp_path / "coverage_baseline.json"
    write_baseline(0.0, baseline_path)
    assert load_three_way_baseline(baseline_path) is None
    exit_code, _ = check_coverage(baseline_path=baseline_path, scenarios=generate_scenarios(50, seed=1))
    assert exit_code == 0
    assert load_baseline(baseline_path) == 0.0
    assert load_three_way_baseline(baseline_path) is not None


def test_fails_when_three_way_coverage_drops_below_baseline(tmp_path):
    baseline_path = tmp_path / "coverage_baseline.json"
    write_baseline(0.0, baseline_path, three_way_percentage=100.0)
    exit_code, message = check_coverage(baseline_path=baseline_path, scenarios=generate_scenarios(50, seed=1))
    assert exit_code == 1
    assert "3-way coverage" in message
    assert "pairwise coverage" not in message


def test_passing_message_reports_untested_three_way_combinations(tmp_path):
    baseline_path = tmp_path / "coverage_baseline.json"
    write_baseline(0.0, baseline_path, three_way_percentage=0.0)
    exit_code, message = check_coverage(baseline_path=baseline_path, scenarios=generate_scenarios(50, seed=1))
    assert exit_code == 0
    assert "three-way combinations untested" in message


def test_passes_when_current_coverage_meets_baseline(tmp_path):
    baseline_path = tmp_path / "coverage_baseline.json"
    write_baseline(0.0, baseline_path)
    exit_code, message = check_coverage(baseline_path=baseline_path, scenarios=generate_scenarios(50, seed=1))
    assert exit_code == 0
    assert "Coverage check passed" in message


def test_fails_when_current_coverage_drops_below_baseline(tmp_path):
    baseline_path = tmp_path / "coverage_baseline.json"
    write_baseline(100.0, baseline_path, three_way_percentage=0.0)
    exit_code, message = check_coverage(baseline_path=baseline_path, scenarios=generate_scenarios(50, seed=1))
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


def test_gate_reads_the_committed_suite_file(tmp_path):
    from suite import save_suite

    suite_path = tmp_path / "suite.json"
    baseline_path = tmp_path / "coverage_baseline.json"
    save_suite(generate_scenarios(50, seed=1), suite_path)
    check_coverage(baseline_path=baseline_path, suite_path=suite_path)
    assert load_baseline(baseline_path) == coverage_percentage(generate_scenarios(50, seed=1))


def test_removing_scenarios_from_the_suite_fails_the_gate(tmp_path):
    from suite import save_suite

    suite_path = tmp_path / "suite.json"
    baseline_path = tmp_path / "coverage_baseline.json"
    full = generate_scenarios(50, seed=1)
    save_suite(full, suite_path)
    assert check_coverage(baseline_path=baseline_path, suite_path=suite_path)[0] == 0

    save_suite(full[:25], suite_path)
    exit_code, message = check_coverage(baseline_path=baseline_path, suite_path=suite_path)
    assert exit_code == 1
    assert "Untested, e.g.:" in message


def test_gate_message_names_untested_combinations(tmp_path):
    baseline_path = tmp_path / "coverage_baseline.json"
    write_baseline(0.0, baseline_path, three_way_percentage=0.0)
    _, message = check_coverage(baseline_path=baseline_path, scenarios=generate_scenarios(10, seed=2))
    assert "Untested, e.g.:" in message
    assert "more)." in message


def test_suggest_additions_close_every_gap_in_the_suite(tmp_path):
    from check_coverage import suggest_additions
    from coverage import tway_coverage_percentage
    from suite import load_suite, save_suite

    suite_path = tmp_path / "suite.json"
    save_suite(generate_scenarios(50, seed=1), suite_path)
    additions = suggest_additions(3, suite_path=suite_path)
    assert additions
    assert tway_coverage_percentage(load_suite(suite_path) + additions, 3) == 100.0


def test_committed_suite_matches_tracked_baseline():
    from suite import load_suite

    scenarios = load_suite()
    assert len(scenarios) == 50
    assert coverage_percentage(scenarios) == load_baseline()
    assert tway_coverage_percentage(scenarios, 3) == load_three_way_baseline()
