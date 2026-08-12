import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from models import SCHEMA_FIELDS, Scenario, scenario_hash

_FIELD_COLUMN_DEFS = ",\n    ".join(f"{field} TEXT NOT NULL" for field in SCHEMA_FIELDS)
_FIELD_COLUMNS = ", ".join(SCHEMA_FIELDS)
_QUALIFIED_FIELD_COLUMNS = ", ".join(f"runs.{field}" for field in SCHEMA_FIELDS)
_FIELD_PLACEHOLDERS = ", ".join("?" for _ in SCHEMA_FIELDS)

CREATE_RUNS_TABLE = f"""
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_hash TEXT NOT NULL,
    {_FIELD_COLUMN_DEFS},
    passed INTEGER NOT NULL,
    run_timestamp TEXT NOT NULL
)
"""

CREATE_SCENARIO_HASH_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_runs_scenario_hash ON runs(scenario_hash)"
)

INSERT_RUN = f"""
INSERT INTO runs (scenario_hash, {_FIELD_COLUMNS}, passed, run_timestamp)
VALUES (?, {_FIELD_PLACEHOLDERS}, ?, ?)
"""

# A scenario_hash's earliest passing timestamp preceding its latest failing
# timestamp is proof that some pass was followed, at some later point, by
# some fail for that scenario -- it doesn't require them to be adjacent runs.
FIND_REGRESSIONS_QUERY = f"""
WITH regression_hashes AS (
    SELECT
        scenario_hash,
        MIN(CASE WHEN passed = 1 THEN run_timestamp END) AS earliest_pass,
        MAX(CASE WHEN passed = 0 THEN run_timestamp END) AS latest_fail
    FROM runs
    GROUP BY scenario_hash
    HAVING earliest_pass IS NOT NULL
       AND latest_fail IS NOT NULL
       AND earliest_pass < latest_fail
)
SELECT DISTINCT
    runs.scenario_hash, {_QUALIFIED_FIELD_COLUMNS},
    regression_hashes.earliest_pass,
    regression_hashes.latest_fail
FROM runs
JOIN regression_hashes ON runs.scenario_hash = regression_hashes.scenario_hash
"""

# Stricter than FIND_REGRESSIONS_QUERY: only flags a scenario_hash whose
# single most recent run failed, with at least one earlier run that passed.
# The INNER JOIN to earliest_pass drops any scenario_hash that has never
# passed, since there's nothing to regress from.
MOST_RECENT_REGRESSIONS_QUERY = f"""
WITH latest_runs AS (
    SELECT scenario_hash, MAX(run_timestamp) AS latest_timestamp
    FROM runs
    GROUP BY scenario_hash
),
latest_status AS (
    SELECT runs.scenario_hash, runs.run_timestamp AS latest_timestamp, runs.passed AS latest_passed
    FROM runs
    JOIN latest_runs
      ON runs.scenario_hash = latest_runs.scenario_hash
     AND runs.run_timestamp = latest_runs.latest_timestamp
),
earliest_pass AS (
    SELECT scenario_hash, MIN(run_timestamp) AS earliest_pass_timestamp
    FROM runs
    WHERE passed = 1
    GROUP BY scenario_hash
)
SELECT DISTINCT
    runs.scenario_hash, {_QUALIFIED_FIELD_COLUMNS},
    earliest_pass.earliest_pass_timestamp,
    latest_status.latest_timestamp AS latest_fail_timestamp
FROM runs
JOIN latest_status ON runs.scenario_hash = latest_status.scenario_hash
JOIN earliest_pass ON runs.scenario_hash = earliest_pass.scenario_hash
WHERE latest_status.latest_passed = 0
  AND earliest_pass.earliest_pass_timestamp < latest_status.latest_timestamp
"""


@dataclass(frozen=True)
class Regression:
    scenario_hash: str
    scenario: Scenario
    earliest_pass: str
    latest_fail: str


def connect(path):
    conn = sqlite3.connect(path)
    conn.execute(CREATE_RUNS_TABLE)
    conn.execute(CREATE_SCENARIO_HASH_INDEX)
    conn.commit()
    return conn


def record_run(conn, scenario: Scenario, passed: bool, timestamp=None):
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()
    data = scenario.as_dict()
    field_values = tuple(data[field] for field in SCHEMA_FIELDS)
    conn.execute(
        INSERT_RUN,
        (scenario_hash(scenario), *field_values, 1 if passed else 0, timestamp),
    )
    conn.commit()
    return timestamp


def _row_to_regression(row):
    hash_value, *field_values, earliest_pass, latest_fail = row
    scenario = Scenario.from_values(dict(zip(SCHEMA_FIELDS, field_values)))
    return Regression(
        scenario_hash=hash_value,
        scenario=scenario,
        earliest_pass=earliest_pass,
        latest_fail=latest_fail,
    )


def find_regressions(conn):
    rows = conn.execute(FIND_REGRESSIONS_QUERY).fetchall()
    return [_row_to_regression(row) for row in rows]


def most_recent_regressions(conn):
    rows = conn.execute(MOST_RECENT_REGRESSIONS_QUERY).fetchall()
    return [_row_to_regression(row) for row in rows]
