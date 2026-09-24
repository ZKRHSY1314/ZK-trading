from __future__ import annotations

import json

import pytest

from app.config import settings
from app.data.market_history import MarketHistoryStore
from scripts import init_market_history


def test_inspect_missing_store_is_read_only_and_never_creates_file(tmp_path) -> None:
    database_path = tmp_path / "market_history.sqlite3"
    store = MarketHistoryStore(database_path)

    result = store.inspect()

    assert result["status"] == "planned"
    assert result["mode"] == "inspect"
    assert result["database_exists"] is False
    assert result["writes_enabled"] is False
    assert result["safety"]["research_only"] is True
    assert result["safety"]["live_trading_enabled"] is False
    assert not database_path.exists()
    assert list(tmp_path.iterdir()) == []


def test_initialize_creates_versioned_research_schema_with_safe_sqlite_pragmas(
    tmp_path,
) -> None:
    database_path = tmp_path / "market_history.sqlite3"
    store = MarketHistoryStore(database_path)

    result = store.initialize()

    assert result["status"] == "ready"
    assert result["mode"] == "apply"
    assert result["created"] is True
    assert result["schema_name"] == "market_history.v1"
    assert result["schema_version"] == 1
    assert result["applied_schema_version"] == 1
    assert result["writes_enabled"] is True
    assert result["sqlite"] == {
        "journal_mode": "wal",
        "busy_timeout_ms": 5000,
        "foreign_keys": True,
    }
    assert result["tables"]["missing"] == []
    assert set(result["tables"]["present"]) == set(result["tables"]["expected"])
    assert result["safety"] == {
        "research_only": True,
        "live_trading_enabled": False,
        "broker_or_order_capability": False,
    }
    assert database_path.exists()


def test_initialize_is_idempotent_and_preserves_existing_research_rows(tmp_path) -> None:
    database_path = tmp_path / "market_history.sqlite3"
    store = MarketHistoryStore(database_path)
    store.initialize()
    with store.connect() as connection:
        connection.execute(
            """
            INSERT INTO instruments(symbol, name, exchange, provider, fetched_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("SZ000001", "平安银行", "SZ", "test", "2026-07-15T14:00:00+08:00"),
        )

    second = store.initialize()

    assert second["status"] == "ready"
    assert second["created"] is False
    assert second["tables"]["counts"]["instruments"] == 1


def test_initialize_refuses_the_runtime_trading_database_without_touching_it(
    tmp_path,
    monkeypatch,
) -> None:
    runtime_database = tmp_path / "trading_local.sqlite3"
    sentinel = b"runtime-database-must-not-be-opened"
    runtime_database.write_bytes(sentinel)
    monkeypatch.setattr(settings, "database_path", runtime_database)

    with pytest.raises(ValueError, match="runtime trading database"):
        MarketHistoryStore(runtime_database).initialize()

    assert runtime_database.read_bytes() == sentinel
    assert sorted(path.name for path in tmp_path.iterdir()) == [runtime_database.name]


def test_daily_bars_default_unknown_volume_unit_and_nullable_rule_regime(tmp_path) -> None:
    store = MarketHistoryStore(tmp_path / "market_history.sqlite3")
    store.initialize()
    with store.connect() as connection:
        connection.execute(
            """
            INSERT INTO instruments(symbol, exchange, provider, fetched_at)
            VALUES ('SH600000', 'SH', 'test', '2026-07-15T14:00:00+08:00')
            """
        )
        connection.execute(
            """
            INSERT INTO daily_bars(
                symbol, trade_date, adjustment_mode,
                open, high, low, close, volume, amount,
                provider, fetched_at, row_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "SH600000",
                "2026-07-15",
                "qfq",
                10.0,
                10.5,
                9.9,
                10.2,
                1_000.0,
                1_020_000.0,
                "test",
                "2026-07-15T15:10:00+08:00",
                "row-hash",
            ),
        )
        bar = connection.execute(
            "SELECT volume_unit, rule_regime FROM daily_bars WHERE symbol = 'SH600000'"
        ).fetchone()

    assert dict(bar) == {"volume_unit": "unknown", "rule_regime": None}


def test_init_script_defaults_to_json_inspect_without_creating_database(
    tmp_path,
    capsys,
) -> None:
    database_path = tmp_path / "market_history.sqlite3"

    exit_code = init_market_history.main(["--database-path", str(database_path)])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "planned"
    assert payload["mode"] == "inspect"
    assert payload["writes_enabled"] is False
    assert payload["database_path"] == str(database_path.resolve())
    assert not database_path.exists()


def test_init_script_requires_apply_to_create_and_reports_idempotency(
    tmp_path,
    capsys,
) -> None:
    database_path = tmp_path / "market_history.sqlite3"

    first_exit = init_market_history.main(
        ["--database-path", str(database_path), "--apply"]
    )
    first = json.loads(capsys.readouterr().out)
    second_exit = init_market_history.main(
        ["--database-path", str(database_path), "--apply"]
    )
    second = json.loads(capsys.readouterr().out)

    assert first_exit == second_exit == 0
    assert first["status"] == second["status"] == "ready"
    assert first["mode"] == second["mode"] == "apply"
    assert first["created"] is True
    assert second["created"] is False
    assert database_path.exists()


def test_apply_is_blocked_when_runtime_live_trading_is_enabled(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    database_path = tmp_path / "market_history.sqlite3"
    monkeypatch.setattr(settings, "enable_live_trading", True)

    exit_code = init_market_history.main(
        ["--database-path", str(database_path), "--apply"]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["status"] == "blocked"
    assert "live trading" in payload["error"]
    assert payload["writes_enabled"] is False
    assert not database_path.exists()


def test_daily_bar_identity_and_provenance_columns_are_part_of_schema(tmp_path) -> None:
    store = MarketHistoryStore(tmp_path / "market_history.sqlite3")
    store.initialize()

    with store.connect(read_only=True) as connection:
        columns = {
            str(row["name"]): dict(row)
            for row in connection.execute("PRAGMA table_info(daily_bars)").fetchall()
        }

    assert {
        "symbol",
        "trade_date",
        "adjustment_mode",
        "provider",
        "fetched_at",
        "ingest_run_id",
        "row_hash",
        "amount",
        "volume_unit",
        "rule_regime",
    }.issubset(columns)
    assert {
        "symbol": columns["symbol"]["pk"],
        "trade_date": columns["trade_date"]["pk"],
        "adjustment_mode": columns["adjustment_mode"]["pk"],
    } == {"symbol": 1, "trade_date": 2, "adjustment_mode": 3}
