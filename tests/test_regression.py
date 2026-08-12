from datetime import datetime

from models import scenario_hash
import regression


def test_connect_creates_runs_table_and_index():
    conn = regression.connect(":memory:")
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert "runs" in tables
    indexes = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    }
    assert "idx_runs_scenario_hash" in indexes


def test_record_run_inserts_a_row_with_correct_hash_and_passed_flag(make_scenario):
    conn = regression.connect(":memory:")
    scenario = make_scenario()
    regression.record_run(conn, scenario, True)
    row = conn.execute("SELECT scenario_hash, passed FROM runs").fetchone()
    assert row[0] == scenario_hash(scenario)
    assert row[1] == 1


def test_record_run_stores_zero_for_a_failed_run(make_scenario):
    conn = regression.connect(":memory:")
    scenario = make_scenario()
    regression.record_run(conn, scenario, False)
    passed = conn.execute("SELECT passed FROM runs").fetchone()[0]
    assert passed == 0


def test_record_run_generates_a_valid_iso_timestamp_when_none_given(make_scenario):
    conn = regression.connect(":memory:")
    scenario = make_scenario()
    timestamp = regression.record_run(conn, scenario, True)
    datetime.fromisoformat(timestamp)
    stored = conn.execute("SELECT run_timestamp FROM runs").fetchone()[0]
    assert stored == timestamp


def test_record_run_uses_an_explicit_timestamp_when_given(make_scenario):
    conn = regression.connect(":memory:")
    scenario = make_scenario()
    regression.record_run(conn, scenario, True, timestamp="2020-01-01T00:00:00+00:00")
    stored = conn.execute("SELECT run_timestamp FROM runs").fetchone()[0]
    assert stored == "2020-01-01T00:00:00+00:00"


def test_data_persists_across_reconnects(tmp_path, make_scenario):
    path = str(tmp_path / "regression.db")
    conn = regression.connect(path)
    scenario = make_scenario()
    regression.record_run(conn, scenario, True)
    conn.close()

    reopened = regression.connect(path)
    count = reopened.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    assert count == 1


def test_find_regressions_is_empty_with_no_runs():
    conn = regression.connect(":memory:")
    assert regression.find_regressions(conn) == []


def test_find_regressions_flags_a_pass_then_fail(make_scenario):
    conn = regression.connect(":memory:")
    scenario = make_scenario()
    regression.record_run(conn, scenario, True, timestamp="2026-01-01T00:00:00+00:00")
    regression.record_run(conn, scenario, False, timestamp="2026-01-02T00:00:00+00:00")

    results = regression.find_regressions(conn)
    assert len(results) == 1
    assert results[0].scenario == scenario
    assert results[0].earliest_pass == "2026-01-01T00:00:00+00:00"
    assert results[0].latest_fail == "2026-01-02T00:00:00+00:00"


def test_find_regressions_ignores_fail_then_pass(make_scenario):
    conn = regression.connect(":memory:")
    scenario = make_scenario()
    regression.record_run(conn, scenario, False, timestamp="2026-01-01T00:00:00+00:00")
    regression.record_run(conn, scenario, True, timestamp="2026-01-02T00:00:00+00:00")

    assert regression.find_regressions(conn) == []


def test_find_regressions_ignores_scenarios_that_never_passed(make_scenario):
    conn = regression.connect(":memory:")
    scenario = make_scenario()
    regression.record_run(conn, scenario, False, timestamp="2026-01-01T00:00:00+00:00")
    regression.record_run(conn, scenario, False, timestamp="2026-01-02T00:00:00+00:00")

    assert regression.find_regressions(conn) == []


def test_find_regressions_ignores_scenarios_that_never_failed(make_scenario):
    conn = regression.connect(":memory:")
    scenario = make_scenario()
    regression.record_run(conn, scenario, True, timestamp="2026-01-01T00:00:00+00:00")
    regression.record_run(conn, scenario, True, timestamp="2026-01-02T00:00:00+00:00")

    assert regression.find_regressions(conn) == []


def test_find_regressions_flags_ever_regressed_even_if_it_later_passed_again(make_scenario):
    conn = regression.connect(":memory:")
    scenario = make_scenario()
    regression.record_run(conn, scenario, True, timestamp="2026-01-01T00:00:00+00:00")
    regression.record_run(conn, scenario, False, timestamp="2026-01-02T00:00:00+00:00")
    regression.record_run(conn, scenario, True, timestamp="2026-01-03T00:00:00+00:00")

    results = regression.find_regressions(conn)
    assert len(results) == 1
    assert results[0].scenario == scenario


def test_find_regressions_keeps_different_scenarios_separate(make_scenario):
    conn = regression.connect(":memory:")
    regressed = make_scenario()
    stable = make_scenario(weather="rain")
    regression.record_run(conn, regressed, True, timestamp="2026-01-01T00:00:00+00:00")
    regression.record_run(conn, regressed, False, timestamp="2026-01-02T00:00:00+00:00")
    regression.record_run(conn, stable, True, timestamp="2026-01-01T00:00:00+00:00")
    regression.record_run(conn, stable, True, timestamp="2026-01-02T00:00:00+00:00")

    results = regression.find_regressions(conn)
    assert [result.scenario for result in results] == [regressed]


def test_most_recent_regressions_flags_simple_pass_then_fail(make_scenario):
    conn = regression.connect(":memory:")
    scenario = make_scenario()
    regression.record_run(conn, scenario, True, timestamp="2026-01-01T00:00:00+00:00")
    regression.record_run(conn, scenario, False, timestamp="2026-01-02T00:00:00+00:00")

    results = regression.most_recent_regressions(conn)
    assert len(results) == 1
    assert results[0].scenario == scenario


def test_most_recent_regressions_ignores_pass_fail_pass(make_scenario):
    conn = regression.connect(":memory:")
    scenario = make_scenario()
    regression.record_run(conn, scenario, True, timestamp="2026-01-01T00:00:00+00:00")
    regression.record_run(conn, scenario, False, timestamp="2026-01-02T00:00:00+00:00")
    regression.record_run(conn, scenario, True, timestamp="2026-01-03T00:00:00+00:00")

    assert regression.most_recent_regressions(conn) == []


def test_most_recent_regressions_ignores_never_passed(make_scenario):
    conn = regression.connect(":memory:")
    scenario = make_scenario()
    regression.record_run(conn, scenario, False, timestamp="2026-01-01T00:00:00+00:00")
    regression.record_run(conn, scenario, False, timestamp="2026-01-02T00:00:00+00:00")

    assert regression.most_recent_regressions(conn) == []


def test_most_recent_regressions_ignores_currently_passing(make_scenario):
    conn = regression.connect(":memory:")
    scenario = make_scenario()
    regression.record_run(conn, scenario, False, timestamp="2026-01-01T00:00:00+00:00")
    regression.record_run(conn, scenario, True, timestamp="2026-01-02T00:00:00+00:00")

    assert regression.most_recent_regressions(conn) == []


def test_most_recent_regressions_is_a_subset_signal_of_find_regressions(make_scenario):
    conn = regression.connect(":memory:")
    scenario = make_scenario()
    regression.record_run(conn, scenario, True, timestamp="2026-01-01T00:00:00+00:00")
    regression.record_run(conn, scenario, False, timestamp="2026-01-02T00:00:00+00:00")
    regression.record_run(conn, scenario, True, timestamp="2026-01-03T00:00:00+00:00")

    ever = {result.scenario_hash for result in regression.find_regressions(conn)}
    recent = {result.scenario_hash for result in regression.most_recent_regressions(conn)}
    assert recent <= ever
    assert recent == set()
    assert ever == {scenario_hash(scenario)}
