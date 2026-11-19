import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from itertools import combinations

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


# Per-scenario pass/fail counts split at a cutoff timestamp (e.g. the time a
# new build was deployed). Runs strictly before the cutoff are the baseline,
# runs at or after it are the candidate.
SPLIT_COUNTS_QUERY = f"""
SELECT
    scenario_hash,
    {_FIELD_COLUMNS},
    SUM(CASE WHEN run_timestamp < :cutoff THEN 1 ELSE 0 END) AS before_runs,
    SUM(CASE WHEN run_timestamp < :cutoff AND passed = 0 THEN 1 ELSE 0 END) AS before_failures,
    SUM(CASE WHEN run_timestamp >= :cutoff THEN 1 ELSE 0 END) AS after_runs,
    SUM(CASE WHEN run_timestamp >= :cutoff AND passed = 0 THEN 1 ELSE 0 END) AS after_failures
FROM runs
GROUP BY scenario_hash
"""

# Default false discovery rate for significant_regressions. Every scenario
# is its own hypothesis test, so without a multiple-comparison correction a
# suite of a few hundred scenarios would flag several "regressions" from
# noise alone on every build.
DEFAULT_FALSE_DISCOVERY_RATE = 0.05


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
    # Raw flip detection: any pass followed later by any fail. Useful as an
    # audit trail, but scenarios fail at a nonzero rate even when nothing
    # changed, so most flips are noise. Use significant_regressions to gate.
    rows = conn.execute(FIND_REGRESSIONS_QUERY).fetchall()
    return [_row_to_regression(row) for row in rows]


def most_recent_regressions(conn):
    rows = conn.execute(MOST_RECENT_REGRESSIONS_QUERY).fetchall()
    return [_row_to_regression(row) for row in rows]


@dataclass(frozen=True)
class RateRegression:
    scenario_hash: str
    scenario: Scenario
    before_runs: int
    before_failures: int
    after_runs: int
    after_failures: int
    p_value: float

    @property
    def before_failure_rate(self) -> float:
        return self.before_failures / self.before_runs

    @property
    def after_failure_rate(self) -> float:
        return self.after_failures / self.after_runs


def fisher_exact_greater(before_failures, before_runs, after_failures, after_runs) -> float:
    """One-sided Fisher exact p-value that the after failure rate exceeds the before rate.

    Conditions on the total number of failures across both windows and asks
    how likely it is that at least after_failures of them land in the after
    window by chance (hypergeometric upper tail).
    """
    total_runs = before_runs + after_runs
    total_failures = before_failures + after_failures
    denominator = math.comb(total_runs, total_failures)
    upper = min(total_failures, after_runs)
    tail = sum(
        math.comb(after_runs, k) * math.comb(before_runs, total_failures - k)
        for k in range(after_failures, upper + 1)
    )
    return tail / denominator


def benjamini_hochberg(p_values, false_discovery_rate):
    """Return the indices of p_values rejected at the given false discovery rate."""
    order = sorted(range(len(p_values)), key=lambda i: p_values[i])
    m = len(p_values)
    cutoff_rank = 0
    for rank, index in enumerate(order, start=1):
        if p_values[index] <= false_discovery_rate * rank / m:
            cutoff_rank = rank
    return set(order[:cutoff_rank])


def _split_counts(conn, cutoff):
    rows = conn.execute(SPLIT_COUNTS_QUERY, {"cutoff": cutoff}).fetchall()
    for hash_value, *rest in rows:
        field_values = rest[: len(SCHEMA_FIELDS)]
        counts = tuple(rest[len(SCHEMA_FIELDS):])
        yield hash_value, dict(zip(SCHEMA_FIELDS, field_values)), counts


def significant_regressions(conn, cutoff, false_discovery_rate=DEFAULT_FALSE_DISCOVERY_RATE):
    """Scenarios whose failure rate rose significantly at cutoff, controlling false discoveries.

    Unlike find_regressions, a single pass followed by a single fail is not
    evidence on its own: scenarios have nonzero failure rates, so isolated
    flips happen without any change to the system. Each scenario needs runs
    on both sides of cutoff. The failure rate before cutoff is compared with
    the rate after it using a one-sided Fisher exact test, and the resulting
    p-values are corrected across scenarios with Benjamini-Hochberg.

    Inherently hard scenarios are not suppressed for being noisy; they are
    flagged when their failure rate goes up, which is the case flaky-test
    filtering tends to hide.
    """
    candidates = []
    for hash_value, values, counts in _split_counts(conn, cutoff):
        before_runs, before_failures, after_runs, after_failures = counts
        if before_runs == 0 or after_runs == 0:
            continue
        p_value = fisher_exact_greater(before_failures, before_runs, after_failures, after_runs)
        candidates.append(
            RateRegression(
                scenario_hash=hash_value,
                scenario=Scenario.from_values(values),
                before_runs=before_runs,
                before_failures=before_failures,
                after_runs=after_runs,
                after_failures=after_failures,
                p_value=p_value,
            )
        )
    rejected = benjamini_hochberg([c.p_value for c in candidates], false_discovery_rate)
    flagged = [candidates[i] for i in sorted(rejected)]
    flagged.sort(key=lambda c: c.p_value)
    return flagged


@dataclass(frozen=True)
class CombinationRegression:
    field_a: str
    field_b: str
    value_a: str
    value_b: str
    scenario_count: int
    before_runs: int
    before_failures: int
    after_runs: int
    after_failures: int
    p_value: float

    @property
    def before_failure_rate(self) -> float:
        return self.before_failures / self.before_runs

    @property
    def after_failure_rate(self) -> float:
        return self.after_failures / self.after_runs


def significant_combination_regressions(
    conn, cutoff, false_discovery_rate=DEFAULT_FALSE_DISCOVERY_RATE
):
    """Pairwise parameter combinations whose pooled failure rate rose significantly at cutoff.

    Regressions usually follow operating conditions ("rain", "night with
    cyclists") rather than a single scenario vector, so pooling every run
    of every scenario that shares a pairwise combination gives far more
    statistical power than testing scenarios one by one. Only scenarios with
    runs on both sides of cutoff contribute, so a change in which scenarios
    were run cannot masquerade as a change in failure rate. Same one-sided
    Fisher exact test and Benjamini-Hochberg correction as
    significant_regressions.
    """
    pooled = {}
    for _, values, counts in _split_counts(conn, cutoff):
        before_runs, _, after_runs, _ = counts
        if before_runs == 0 or after_runs == 0:
            continue
        for field_a, field_b in combinations(SCHEMA_FIELDS, 2):
            key = (field_a, field_b, values[field_a], values[field_b])
            totals = pooled.setdefault(key, [0, 0, 0, 0, 0])
            totals[0] += 1
            for i, count in enumerate(counts, start=1):
                totals[i] += count
    candidates = [
        CombinationRegression(
            *key,
            scenario_count=totals[0],
            before_runs=totals[1],
            before_failures=totals[2],
            after_runs=totals[3],
            after_failures=totals[4],
            p_value=fisher_exact_greater(totals[2], totals[1], totals[4], totals[3]),
        )
        for key, totals in pooled.items()
    ]
    rejected = benjamini_hochberg([c.p_value for c in candidates], false_discovery_rate)
    flagged = [candidates[i] for i in sorted(rejected)]
    flagged.sort(key=lambda c: c.p_value)
    return flagged
