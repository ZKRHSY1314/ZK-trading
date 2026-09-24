from __future__ import annotations

import sqlite3

import pytest

from app.storage.sqlite_store import (
    _migrate_decision_day_run_kind,
    _migrate_evaluation_policy_version,
)

PRE_BATCH_A_DECISION_DAYS = """
CREATE TABLE forecast_decision_days (
    scope TEXT NOT NULL CHECK(scope IN ('sector', 'stock', 'system')),
    data_version TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    claimed_at TEXT NOT NULL,
    candidate_count INTEGER NOT NULL,
    recorded_count INTEGER NOT NULL,
    PRIMARY KEY (scope, data_version)
);
"""

PRE_BATCH_A_EVALUATIONS = """
CREATE TABLE forecast_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_id TEXT NOT NULL UNIQUE,
    as_of TEXT NOT NULL,
    scope TEXT NOT NULL,
    horizon_days INTEGER NOT NULL,
    status TEXT NOT NULL,
    sample_count INTEGER NOT NULL,
    fold_count INTEGER NOT NULL,
    coverage REAL NOT NULL,
    metrics_json TEXT NOT NULL,
    review_only INTEGER NOT NULL DEFAULT 1
);
"""


@pytest.fixture
def legacy(tmp_path) -> sqlite3.Connection:
    """A database as it stood before Batch A, holding one historical claim."""

    conn = sqlite3.connect(tmp_path / "legacy.sqlite3")
    conn.row_factory = sqlite3.Row
    conn.executescript(PRE_BATCH_A_DECISION_DAYS + PRE_BATCH_A_EVALUATIONS)
    conn.execute(
        "INSERT INTO forecast_decision_days "
        "(scope, data_version, decision_id, claimed_at, candidate_count, recorded_count) "
        "VALUES ('stock', '2026-09-03', 'decision-historical', "
        "'2026-09-04T12:43:08+08:00', 30, 150)"
    )
    conn.execute(
        "INSERT INTO forecast_evaluations "
        "(evaluation_id, as_of, scope, horizon_days, status, sample_count, "
        " fold_count, coverage, metrics_json) "
        "VALUES ('eval-legacy', '2026-07-20', 'stock', 5, 'ready', 3630, 121, 1.0, '{}')"
    )
    conn.commit()
    return conn


def test_a_historical_claim_is_not_promoted_to_scheduled(legacy):
    """Provenance that was never recorded must not be invented by a DEFAULT.

    The production database holds exactly one claim, written during a manual
    run. ADD COLUMN ... DEFAULT 'scheduled' would apply that default to it and
    silently make a manual snapshot the official decision of record - the very
    thing the canonical policy exists to prevent.
    """

    _migrate_decision_day_run_kind(legacy)

    row = legacy.execute(
        "SELECT run_kind, decision_id, recorded_count FROM forecast_decision_days"
    ).fetchone()
    assert row["run_kind"] == "legacy_unknown"
    # The rest of the row is carried across untouched.
    assert row["decision_id"] == "decision-historical"
    assert int(row["recorded_count"]) == 150


def test_an_upgraded_database_enforces_the_same_check_as_a_new_one(legacy):
    """ALTER TABLE ADD COLUMN cannot attach a CHECK, so the table is rebuilt.

    Without the rebuild an upgraded database would accept run_kind values that a
    freshly created one rejects, and the two schemas would quietly diverge.
    """

    _migrate_decision_day_run_kind(legacy)

    with pytest.raises(sqlite3.IntegrityError):
        legacy.execute(
            "INSERT INTO forecast_decision_days "
            "(scope, data_version, decision_id, claimed_at, candidate_count, "
            " recorded_count, run_kind) "
            "VALUES ('stock', '2026-09-04', 'decision-x', '2026-09-04T17:00:00+08:00', "
            " 1, 1, 'not_a_valid_kind')"
        )


def test_the_migration_is_idempotent(legacy):
    """Running it twice must not rebuild again or disturb the rows."""

    _migrate_decision_day_run_kind(legacy)
    first = legacy.execute(
        "SELECT scope, data_version, decision_id, run_kind FROM forecast_decision_days"
    ).fetchall()

    _migrate_decision_day_run_kind(legacy)
    second = legacy.execute(
        "SELECT scope, data_version, decision_id, run_kind FROM forecast_decision_days"
    ).fetchall()

    assert [tuple(row) for row in first] == [tuple(row) for row in second]
    assert len(second) == 1


def test_a_real_migration_failure_is_raised_not_swallowed(tmp_path):
    """Only the already-migrated case is tolerated; anything else must surface.

    The blanket `except sqlite3.OperationalError: pass` around the older
    migrations would hide a genuinely broken upgrade, so these run outside it.
    """

    conn = sqlite3.connect(tmp_path / "broken.sqlite3")
    conn.row_factory = sqlite3.Row
    # No forecast_decision_days table at all.
    with pytest.raises(sqlite3.OperationalError):
        _migrate_decision_day_run_kind(conn)


def test_legacy_evaluations_keep_a_null_policy_version(legacy):
    """A NULL is how a pre-policy result is identified later, not its date."""

    _migrate_evaluation_policy_version(legacy)

    row = legacy.execute(
        "SELECT canonical_policy_version, sample_count, fold_count "
        "FROM forecast_evaluations WHERE evaluation_id = 'eval-legacy'"
    ).fetchone()
    assert row["canonical_policy_version"] is None
    # The inflated counts are preserved as audit history, not rewritten.
    assert int(row["sample_count"]) == 3630
    assert int(row["fold_count"]) == 121

    # Idempotent.
    _migrate_evaluation_policy_version(legacy)
    assert (
        legacy.execute("SELECT COUNT(*) FROM forecast_evaluations").fetchone()[0] == 1
    )


def test_a_migrated_claim_is_never_canonical(legacy, tmp_path):
    """legacy_unknown must not satisfy the confirmed path.

    This is the end of the chain: the historical claim survives, keeps its rows,
    and still cannot become the official snapshot.
    """

    from app.forecasting.canonical import canonical_snapshot_cte

    _migrate_decision_day_run_kind(legacy)
    legacy.executescript(
        """
        CREATE TABLE forecast_decisions (
            decision_id TEXT, scope TEXT, subject TEXT, data_version TEXT,
            decision_cutoff TEXT, horizon_days INTEGER
        );
        """
    )
    for subject in ("SH600000", "SH600001"):
        for horizon in (1, 3, 5, 10, 20):
            legacy.execute(
                "INSERT INTO forecast_decisions VALUES "
                "('decision-historical', 'stock', ?, '2026-09-03', "
                "'2026-09-04T12:43:08+08:00', ?)",
                (subject, horizon),
            )
    legacy.commit()

    picked = legacy.execute(
        f"WITH {canonical_snapshot_cte()} SELECT decision_id FROM canonical"
    ).fetchall()

    assert picked == []


def test_a_failure_after_the_drop_leaves_the_original_table_intact(legacy):
    """The rebuild must be all-or-nothing.

    CREATE -> INSERT -> DROP -> RENAME has a window where the original table is
    already gone. Without one enclosing transaction, a failure there leaves the
    database with only forecast_decision_days__migrated and no
    forecast_decision_days at all - unrecoverable for a running system.
    """

    class _FailAtRename:
        """sqlite3.Connection.execute is read-only, so wrap rather than patch."""

        def __init__(self, conn):
            self._conn = conn

        def execute(self, sql, *args, **kwargs):
            if "RENAME TO forecast_decision_days" in sql:
                raise sqlite3.OperationalError("injected failure during rename")
            return self._conn.execute(sql, *args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._conn, name)

    with pytest.raises(sqlite3.OperationalError, match="injected failure"):
        _migrate_decision_day_run_kind(_FailAtRename(legacy))

    tables = {
        row[0]
        for row in legacy.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "forecast_decision_days" in tables
    # No half-built table stranded behind.
    assert "forecast_decision_days__migrated" not in tables

    row = legacy.execute(
        "SELECT decision_id, candidate_count, recorded_count FROM forecast_decision_days"
    ).fetchone()
    assert row["decision_id"] == "decision-historical"
    assert int(row["candidate_count"]) == 30
    assert int(row["recorded_count"]) == 150
    # The pre-migration shape is untouched, so a retry can still run.
    assert "run_kind" not in {r[1] for r in legacy.execute("PRAGMA table_info(forecast_decision_days)")}


def test_the_migration_takes_the_write_lock_before_touching_the_schema(tmp_path):
    """A concurrent initializer must not be able to rebuild at the same time.

    Another connection holding the write lock has to block this one at
    BEGIN IMMEDIATE - before any DDL - rather than partway through the rebuild.
    """

    path = tmp_path / "locked.sqlite3"
    owner = sqlite3.connect(path)
    owner.row_factory = sqlite3.Row
    owner.executescript(PRE_BATCH_A_DECISION_DAYS)
    owner.execute(
        "INSERT INTO forecast_decision_days VALUES "
        "('stock', '2026-09-03', 'decision-historical', '2026-09-04T12:43:08+08:00', 30, 150)"
    )
    owner.commit()

    other = sqlite3.connect(path, timeout=0.2)
    other.row_factory = sqlite3.Row
    owner.execute("BEGIN IMMEDIATE")  # hold the write lock
    try:
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            _migrate_decision_day_run_kind(other)
    finally:
        owner.execute("ROLLBACK")

    # Nothing was changed while the lock was held elsewhere.
    tables = {
        row[0]
        for row in owner.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert tables == {"forecast_decision_days"}

    # Once the lock is free the migration succeeds and is a no-op on a re-run.
    _migrate_decision_day_run_kind(other)
    assert (
        other.execute("SELECT run_kind FROM forecast_decision_days").fetchone()["run_kind"]
        == "legacy_unknown"
    )
    _migrate_decision_day_run_kind(other)
    assert other.execute("SELECT COUNT(*) FROM forecast_decision_days").fetchone()[0] == 1


def test_store_init_applies_the_migration_end_to_end(tmp_path):
    """The real entry point, not just the helper."""

    from app.storage.sqlite_store import SQLiteStore

    path = tmp_path / "store-init.sqlite3"
    seed = sqlite3.connect(path)
    seed.executescript(PRE_BATCH_A_DECISION_DAYS)
    seed.execute(
        "INSERT INTO forecast_decision_days VALUES "
        "('stock', '2026-09-03', 'decision-historical', '2026-09-04T12:43:08+08:00', 30, 150)"
    )
    seed.commit()
    seed.close()

    store = SQLiteStore(path)
    store.init()
    store.init()  # idempotent through the public entry point too

    with store.connect() as conn:
        row = conn.execute(
            "SELECT run_kind, decision_id FROM forecast_decision_days"
        ).fetchone()
        tables = {
            r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert row["run_kind"] == "legacy_unknown"
    assert row["decision_id"] == "decision-historical"
    assert "forecast_decision_days__migrated" not in tables
