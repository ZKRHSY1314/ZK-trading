from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MARKET_HISTORY_PATH = PROJECT_ROOT / "market_history.sqlite3"
DEFAULT_RUNTIME_DATABASE_PATH = PROJECT_ROOT / "trading_local.sqlite3"
SCHEMA_VERSION = 1
SCHEMA_NAME = "market_history.v1"
BUSY_TIMEOUT_MS = 5_000

EXPECTED_TABLES = (
    "schema_metadata",
    "instruments",
    "universe_snapshots",
    "universe_members",
    "ingest_runs",
    "daily_bars",
    "bar_quality_issues",
    "training_dataset_manifests",
)

FORBIDDEN_TABLE_TERMS = (
    "account",
    "broker",
    "credential",
    "entrust",
    "fill",
    "fund_transfer",
    "order",
    "position",
)

SCHEMA_SQL = """
BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS instruments (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    exchange TEXT NOT NULL CHECK(exchange IN ('SH', 'SZ', 'BJ', 'INDEX', 'OTHER')),
    asset_type TEXT NOT NULL DEFAULT 'stock',
    board TEXT,
    currency TEXT NOT NULL DEFAULT 'CNY',
    list_date TEXT,
    delist_date TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    provider TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK(length(trim(symbol)) > 0)
);

CREATE TABLE IF NOT EXISTS universe_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    universe_name TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    provider TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    member_count INTEGER NOT NULL CHECK(member_count >= 0),
    source_hash TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(universe_name, snapshot_date, provider, source_hash)
);

CREATE TABLE IF NOT EXISTS universe_members (
    snapshot_id INTEGER NOT NULL REFERENCES universe_snapshots(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL REFERENCES instruments(symbol) ON DELETE RESTRICT,
    weight REAL,
    member_metadata_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY(snapshot_id, symbol),
    CHECK(weight IS NULL OR weight >= 0)
);

CREATE TABLE IF NOT EXISTS ingest_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_name TEXT NOT NULL,
    provider TEXT NOT NULL,
    adjustment_mode TEXT NOT NULL CHECK(adjustment_mode IN ('none', 'qfq', 'hfq')),
    status TEXT NOT NULL CHECK(status IN ('planned', 'running', 'completed', 'partial', 'failed')),
    requested_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    requested_symbol_count INTEGER NOT NULL DEFAULT 0 CHECK(requested_symbol_count >= 0),
    processed_symbol_count INTEGER NOT NULL DEFAULT 0 CHECK(processed_symbol_count >= 0),
    inserted_row_count INTEGER NOT NULL DEFAULT 0 CHECK(inserted_row_count >= 0),
    updated_row_count INTEGER NOT NULL DEFAULT 0 CHECK(updated_row_count >= 0),
    rejected_row_count INTEGER NOT NULL DEFAULT 0 CHECK(rejected_row_count >= 0),
    parameters_json TEXT NOT NULL DEFAULT '{}',
    error_json TEXT NOT NULL DEFAULT '{}',
    research_only INTEGER NOT NULL DEFAULT 1 CHECK(research_only = 1),
    live_trading_enabled INTEGER NOT NULL DEFAULT 0 CHECK(live_trading_enabled = 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_bars (
    symbol TEXT NOT NULL REFERENCES instruments(symbol) ON DELETE RESTRICT,
    trade_date TEXT NOT NULL,
    adjustment_mode TEXT NOT NULL CHECK(adjustment_mode IN ('none', 'qfq', 'hfq')),
    open REAL NOT NULL CHECK(open >= 0),
    high REAL NOT NULL CHECK(high >= 0),
    low REAL NOT NULL CHECK(low >= 0),
    close REAL NOT NULL CHECK(close >= 0),
    volume REAL CHECK(volume IS NULL OR volume >= 0),
    volume_unit TEXT NOT NULL DEFAULT 'unknown'
        CHECK(volume_unit IN ('hand', 'share', 'unknown')),
    amount REAL CHECK(amount IS NULL OR amount >= 0),
    rule_regime TEXT,
    provider TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    available_at TEXT,
    ingest_run_id INTEGER REFERENCES ingest_runs(id) ON DELETE SET NULL,
    row_hash TEXT NOT NULL,
    quality_status TEXT NOT NULL DEFAULT 'ready',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(symbol, trade_date, adjustment_mode),
    CHECK(length(trade_date) = 10),
    CHECK(high >= low),
    CHECK(high >= open AND high >= close),
    CHECK(low <= open AND low <= close)
);

CREATE TABLE IF NOT EXISTS bar_quality_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL REFERENCES instruments(symbol) ON DELETE RESTRICT,
    trade_date TEXT,
    adjustment_mode TEXT CHECK(adjustment_mode IS NULL OR adjustment_mode IN ('none', 'qfq', 'hfq')),
    ingest_run_id INTEGER REFERENCES ingest_runs(id) ON DELETE SET NULL,
    issue_code TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('info', 'warning', 'error')),
    details_json TEXT NOT NULL DEFAULT '{}',
    detected_at TEXT NOT NULL,
    resolved_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS training_dataset_manifests (
    manifest_id TEXT PRIMARY KEY,
    dataset_name TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('draft', 'ready', 'superseded', 'invalid')),
    as_of_date TEXT NOT NULL,
    adjustment_mode TEXT NOT NULL CHECK(adjustment_mode IN ('none', 'qfq', 'hfq')),
    universe_snapshot_id INTEGER REFERENCES universe_snapshots(id) ON DELETE SET NULL,
    query_json TEXT NOT NULL,
    feature_schema_json TEXT NOT NULL,
    label_schema_json TEXT NOT NULL,
    split_policy_json TEXT NOT NULL,
    row_count INTEGER NOT NULL DEFAULT 0 CHECK(row_count >= 0),
    source_min_trade_date TEXT,
    source_max_trade_date TEXT,
    source_hash TEXT NOT NULL,
    artifact_uri TEXT,
    research_only INTEGER NOT NULL DEFAULT 1 CHECK(research_only = 1),
    live_trading_enabled INTEGER NOT NULL DEFAULT 0 CHECK(live_trading_enabled = 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(dataset_name, dataset_version)
);

CREATE INDEX IF NOT EXISTS idx_instruments_exchange_status
    ON instruments(exchange, status);
CREATE INDEX IF NOT EXISTS idx_universe_snapshots_name_date
    ON universe_snapshots(universe_name, snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_universe_members_symbol
    ON universe_members(symbol, snapshot_id);
CREATE INDEX IF NOT EXISTS idx_ingest_runs_dataset_created
    ON ingest_runs(dataset_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_daily_bars_date
    ON daily_bars(trade_date, adjustment_mode);
CREATE INDEX IF NOT EXISTS idx_daily_bars_provider_fetched
    ON daily_bars(provider, fetched_at);
CREATE INDEX IF NOT EXISTS idx_daily_bars_ingest_run
    ON daily_bars(ingest_run_id);
CREATE INDEX IF NOT EXISTS idx_bar_quality_issues_open
    ON bar_quality_issues(symbol, resolved_at, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_training_manifests_asof
    ON training_dataset_manifests(as_of_date DESC, status);

INSERT INTO schema_metadata(key, value) VALUES ('schema_name', 'market_history.v1')
    ON CONFLICT(key) DO NOTHING;
INSERT INTO schema_metadata(key, value) VALUES ('schema_version', '1')
    ON CONFLICT(key) DO NOTHING;
INSERT INTO schema_metadata(key, value) VALUES ('purpose', 'historical_market_research')
    ON CONFLICT(key) DO NOTHING;
INSERT INTO schema_metadata(key, value) VALUES ('research_only', 'true')
    ON CONFLICT(key) DO NOTHING;
INSERT INTO schema_metadata(key, value) VALUES ('live_trading_enabled', 'false')
    ON CONFLICT(key) DO NOTHING;

PRAGMA user_version = 1;
COMMIT;
"""


class MarketHistoryStore:
    """Independent, research-only SQLite store for historical market data."""

    def __init__(self, database_path: str | Path = DEFAULT_MARKET_HISTORY_PATH) -> None:
        self.database_path = Path(database_path)

    @contextmanager
    def connect(self, *, read_only: bool = False) -> Iterator[sqlite3.Connection]:
        if read_only:
            connection = sqlite3.connect(
                f"{self.database_path.resolve().as_uri()}?mode=ro",
                uri=True,
                timeout=BUSY_TIMEOUT_MS / 1_000,
            )
        else:
            connection = sqlite3.connect(
                self.database_path,
                timeout=BUSY_TIMEOUT_MS / 1_000,
            )
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            if not read_only:
                connection.commit()
        except Exception:
            if not read_only:
                connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> dict[str, Any]:
        self._assert_live_trading_disabled()
        self._assert_independent_target()
        created = not self.database_path.exists()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            journal_mode = str(connection.execute("PRAGMA journal_mode = WAL").fetchone()[0])
            if journal_mode.lower() != "wal":
                raise RuntimeError(f"market history database requires WAL, got {journal_mode}")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.executescript(SCHEMA_SQL)

        result = self.inspect()
        result.update(
            {
                "mode": "apply",
                "created": created,
                "writes_enabled": True,
            }
        )
        return result

    def inspect(self) -> dict[str, Any]:
        self._assert_independent_target()
        if not self.database_path.exists():
            return self._missing_plan()

        with self.connect(read_only=True) as connection:
            present_tables = sorted(
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                ).fetchall()
            )
            present_expected = sorted(set(present_tables).intersection(EXPECTED_TABLES))
            missing_tables = sorted(set(EXPECTED_TABLES).difference(present_tables))
            counts = {
                table: int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
                for table in present_expected
            }
            metadata = {}
            if "schema_metadata" in present_tables:
                metadata = {
                    str(row[0]): str(row[1])
                    for row in connection.execute(
                        "SELECT key, value FROM schema_metadata ORDER BY key"
                    ).fetchall()
                }
            applied_schema_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
            busy_timeout_ms = int(connection.execute("PRAGMA busy_timeout").fetchone()[0])
            foreign_keys = bool(connection.execute("PRAGMA foreign_keys").fetchone()[0])

        forbidden_tables = sorted(
            table
            for table in present_tables
            if any(term in table.lower() for term in FORBIDDEN_TABLE_TERMS)
        )
        compatible = (
            applied_schema_version == SCHEMA_VERSION
            and not missing_tables
            and metadata.get("schema_name") == SCHEMA_NAME
            and metadata.get("research_only") == "true"
            and metadata.get("live_trading_enabled") == "false"
            and journal_mode == "wal"
            and foreign_keys
            and not forbidden_tables
        )
        return {
            "status": "ready" if compatible else "incompatible",
            "mode": "inspect",
            "schema_name": SCHEMA_NAME,
            "schema_version": SCHEMA_VERSION,
            "applied_schema_version": applied_schema_version,
            "database_path": str(self.database_path.resolve()),
            "database_exists": True,
            "writes_enabled": False,
            "sqlite": {
                "journal_mode": journal_mode,
                "busy_timeout_ms": busy_timeout_ms,
                "foreign_keys": foreign_keys,
            },
            "tables": {
                "expected": list(EXPECTED_TABLES),
                "present": present_expected,
                "missing": missing_tables,
                "counts": counts,
                "unexpected": sorted(set(present_tables).difference(EXPECTED_TABLES)),
            },
            "metadata": metadata,
            "safety": {
                "research_only": True,
                "live_trading_enabled": False,
                "broker_or_order_capability": bool(forbidden_tables),
            },
        }

    def _missing_plan(self) -> dict[str, Any]:
        return {
            "status": "planned",
            "mode": "inspect",
            "schema_name": SCHEMA_NAME,
            "schema_version": SCHEMA_VERSION,
            "applied_schema_version": None,
            "database_path": str(self.database_path.resolve()),
            "database_exists": False,
            "writes_enabled": False,
            "tables": {
                "expected": list(EXPECTED_TABLES),
                "present": [],
                "missing": list(EXPECTED_TABLES),
                "counts": {},
                "unexpected": [],
            },
            "safety": {
                "research_only": True,
                "live_trading_enabled": False,
                "broker_or_order_capability": False,
            },
        }

    def _assert_independent_target(self) -> None:
        from app.config import settings

        target = self.database_path.resolve()
        runtime_targets = {
            DEFAULT_RUNTIME_DATABASE_PATH.resolve(),
            Path(settings.database_path).resolve(),
        }
        if target in runtime_targets:
            raise ValueError("market history store cannot use the runtime trading database")

    @staticmethod
    def _assert_live_trading_disabled() -> None:
        from app.config import settings

        if settings.enable_live_trading:
            raise ValueError(
                "market history initialization blocked while live trading is enabled"
            )
