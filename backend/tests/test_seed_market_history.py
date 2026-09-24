from __future__ import annotations

import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from app.data.market_history import MarketHistoryStore
from app.config import settings
from app.storage.sqlite_store import SQLiteStore
from scripts.seed_market_history import CandidateHistorySeeder, main


SHANGHAI = ZoneInfo("Asia/Shanghai")


def _write_universe_manifest(path, symbols: list[str]):
    normalized = sorted(dict.fromkeys(symbols))
    universe_hash = hashlib.sha256("\n".join(normalized).encode("utf-8")).hexdigest()
    path.write_text(
        json.dumps(
            {
                "schema_version": "universe_backfill_checkpoint.v2",
                "observed_at": "2026-07-15T16:30:00+00:00",
                "universe_count": len(normalized),
                "universe_hash": universe_hash,
                "universe_symbols": normalized,
                "discovery_source": "akshare.segmented_exchange_code_lists",
                "discovery_complete": True,
                "live_trading_enabled": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path, universe_hash


def _seed_source(source_path) -> SQLiteStore:
    store = SQLiteStore(source_path)
    store.init()
    with store.connect() as connection:
        connection.execute(
            """
            INSERT INTO candidate_lifecycle(
                symbol, name, state, score, source, reason, raw_json
            ) VALUES (
                'SZ002842', '翔鹭钨业', 'focus_watch', 38.28,
                'fixture', 'candidate hot cache fixture', '{}'
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume, amount,
                source, adjustment_mode, volume_unit, quality_status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "SZ002842",
                    "2026-07-13",
                    10.0,
                    10.3,
                    9.9,
                    10.2,
                    1_000.0,
                    None,
                    "sina.cn.kline_daily_fallback",
                    "unknown",
                    "share",
                    "review_only_unknown_adjustment",
                    "2026-07-13T15:20:00+08:00",
                ),
                (
                    "SZ002842",
                    "2026-07-14",
                    10.2,
                    10.8,
                    10.1,
                    10.7,
                    2_000.0,
                    21_400_000.0,
                    "tencent.fqkline.qfq",
                    "qfq",
                    "hand",
                    "ready",
                    "2026-07-14T15:20:00+08:00",
                ),
                (
                    "SZ002842",
                    "2026-07-15",
                    10.7,
                    11.0,
                    10.5,
                    10.9,
                    800.0,
                    8_720_000.0,
                    "tencent.fqkline.qfq",
                    "qfq",
                    "hand",
                    "ready",
                    "2026-07-15T13:30:00+08:00",
                ),
            ],
        )
    return store


def test_dry_run_uses_latest_completed_bar_date_and_writes_neither_database(
    tmp_path,
) -> None:
    source_path = tmp_path / "trading_local.sqlite3"
    target_path = tmp_path / "market_history.sqlite3"
    source = _seed_source(source_path)
    target = MarketHistoryStore(target_path)
    target.initialize()

    result = CandidateHistorySeeder(source_path, target_path).run(
        now=datetime(2026, 7, 15, 13, 30, tzinfo=SHANGHAI)
    )

    assert result["status"] == "planned"
    assert result["mode"] == "dry_run"
    assert result["as_of"] == "2026-07-14"
    assert result["candidate_count"] == 1
    assert result["bar_count"] == 1
    assert result["write_stats"] == {
        "instruments": 0,
        "universe_snapshots": 0,
        "universe_members": 0,
        "ingest_runs": 0,
        "bars_inserted": 0,
        "bars_updated": 0,
        "bars_unchanged": 0,
    }
    assert target.inspect()["tables"]["counts"]["daily_bars"] == 0
    assert source.fetch_one("SELECT COUNT(*) AS count FROM daily_bar_cache")["count"] == 3


def test_full_market_cache_scope_is_not_capped_at_five_hundred_symbols(tmp_path) -> None:
    source_path = tmp_path / "trading_local.sqlite3"
    target_path = tmp_path / "market_history.sqlite3"
    source = SQLiteStore(source_path)
    source.init()
    rows = [
        (
            f"SH{600000 + index:06d}",
            "2026-07-14",
            10.0,
            10.2,
            9.8,
            10.1,
            1000.0,
            None,
            "tencent.fqkline.qfq",
            "qfq",
            "hand",
            "ready",
            "2026-07-14T15:20:00+08:00",
        )
        for index in range(520)
    ]
    with source.connect() as connection:
        connection.executemany(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume, amount,
                source, adjustment_mode, volume_unit, quality_status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    MarketHistoryStore(target_path).initialize()
    manifest_path, _ = _write_universe_manifest(
        tmp_path / "universe.json",
        [row[0] for row in rows],
    )

    result = CandidateHistorySeeder(source_path, target_path).run(
        universe_scope="full_market_cache",
        universe_manifest_path=manifest_path,
        now=datetime(2026, 7, 15, 16, 0, tzinfo=SHANGHAI),
    )

    assert result["status"] == "planned"
    assert result["universe_scope"] == "full_market_cache"
    assert result["universe_name"] == "a_share_full_market_cache"
    assert result["candidate_count"] == 520
    assert result["candidate_symbols_with_bars"] == 520
    assert result["bar_count"] == 520
    assert result["planned_writes"]["universe_members"] == 520


def test_full_market_seed_requires_a_valid_official_universe_manifest(tmp_path) -> None:
    source_path = tmp_path / "trading_local.sqlite3"
    target_path = tmp_path / "market_history.sqlite3"
    SQLiteStore(source_path).init()
    MarketHistoryStore(target_path).initialize()

    try:
        CandidateHistorySeeder(source_path, target_path).run(
            universe_scope="full_market_cache",
            now=datetime(2026, 7, 15, 16, 0, tzinfo=SHANGHAI),
        )
    except ValueError as exc:
        assert "universe manifest" in str(exc).lower()
    else:
        raise AssertionError("full-market seed accepted an implicit stale cache universe")


def test_full_market_seed_rejects_an_incomplete_discovery_manifest(tmp_path) -> None:
    source_path = tmp_path / "trading_local.sqlite3"
    target_path = tmp_path / "market_history.sqlite3"
    SQLiteStore(source_path).init()
    MarketHistoryStore(target_path).initialize()
    manifest_path, _ = _write_universe_manifest(
        tmp_path / "universe.json",
        ["SH600000"],
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["discovery_complete"] = False
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    try:
        CandidateHistorySeeder(source_path, target_path).run(
            universe_scope="full_market_cache",
            universe_manifest_path=manifest_path,
            now=datetime(2026, 7, 15, 16, 0, tzinfo=SHANGHAI),
        )
    except ValueError as exc:
        assert "complete discovery" in str(exc).lower()
    else:
        raise AssertionError("full-market seed accepted a partial universe discovery")


def test_full_market_seed_reports_raw_rows_newer_than_available_qfq_history(tmp_path) -> None:
    source_path = tmp_path / "trading_local.sqlite3"
    target_path = tmp_path / "market_history.sqlite3"
    source = SQLiteStore(source_path)
    source.init()
    with source.connect() as connection:
        connection.executemany(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume, source,
                adjustment_mode, volume_unit, quality_status, updated_at
            ) VALUES (?, ?, 10, 10.2, 9.8, 10.1, 1000, ?, ?, 'hand', ?, ?)
            """,
            [
                (
                    "SH600000",
                    "2026-07-14",
                    "tencent.fqkline.qfq",
                    "qfq",
                    "ready",
                    "2026-07-14T15:20:00+08:00",
                ),
                (
                    "SH600000",
                    "2026-07-15",
                    "tencent.fqkline.raw",
                    "none",
                    "review_only_unadjusted",
                    "2026-07-15T15:20:00+08:00",
                ),
                (
                    "SZ302132",
                    "2026-07-15",
                    "tencent.fqkline.qfq",
                    "qfq",
                    "ready",
                    "2026-07-15T15:20:00+08:00",
                ),
            ],
        )
    MarketHistoryStore(target_path).initialize()
    manifest_path, _ = _write_universe_manifest(
        tmp_path / "universe.json",
        ["SH600000", "SZ302132"],
    )

    result = CandidateHistorySeeder(source_path, target_path).run(
        universe_scope="full_market_cache",
        universe_manifest_path=manifest_path,
        now=datetime(2026, 7, 15, 16, 0, tzinfo=SHANGHAI),
    )

    assert result["latest_raw_newer_than_qfq_symbols"] == ["SH600000"]
    assert result["latest_raw_newer_than_qfq_count"] == 1


def test_full_market_seed_accepts_only_the_exact_unit_factor_verified_sina_composite(
    tmp_path,
) -> None:
    source_path = tmp_path / "trading_local.sqlite3"
    target_path = tmp_path / "market_history.sqlite3"
    source = SQLiteStore(source_path)
    source.init()
    with source.connect() as connection:
        connection.executemany(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume, amount,
                source, adjustment_mode, volume_unit, quality_status, updated_at
            ) VALUES (?, ?, 10, 10.2, 9.8, 10.1, 1000, NULL,
                      ?, 'qfq', 'hand', 'ready', ?)
            """,
            [
                (
                    "BJ920000",
                    "2026-07-13",
                    "sina.cn.kline_daily_fallback",
                    "2026-07-13T15:20:00+08:00",
                ),
                (
                    "BJ920000",
                    "2026-07-14",
                    "tencent.fqkline.raw+sina.qfq_factor.unit_verified",
                    "2026-07-14T15:20:00+08:00",
                ),
            ],
        )
    MarketHistoryStore(target_path).initialize()
    manifest_path, _ = _write_universe_manifest(
        tmp_path / "universe.json",
        ["BJ920000"],
    )

    result = CandidateHistorySeeder(source_path, target_path).run(
        apply=True,
        universe_scope="full_market_cache",
        universe_manifest_path=manifest_path,
        now=datetime(2026, 7, 15, 16, 0, tzinfo=SHANGHAI),
    )

    assert result["status"] == "completed"
    assert result["missing_qfq_symbols"] == []
    assert result["qfq_symbol_coverage"]["ALL"]["available"] == 1
    assert result["excluded"]["sina_rows"] == 1
    with MarketHistoryStore(target_path).connect(read_only=True) as connection:
        bars = [dict(row) for row in connection.execute("SELECT * FROM daily_bars")]
    assert [(bar["trade_date"], bar["provider"]) for bar in bars] == [
        (
            "2026-07-14",
            "tencent.fqkline.raw+sina.qfq_factor.unit_verified",
        )
    ]


def test_full_market_cache_apply_writes_a_distinct_snapshot_and_excludes_indices(
    tmp_path,
) -> None:
    source_path = tmp_path / "trading_local.sqlite3"
    target_path = tmp_path / "market_history.sqlite3"
    source = SQLiteStore(source_path)
    source.init()
    with source.connect() as connection:
        connection.executemany(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume, amount,
                source, adjustment_mode, volume_unit, quality_status, updated_at
            ) VALUES (?, '2026-07-14', 10, 10.2, 9.8, 10.1, 1000, NULL,
                      'tencent.fqkline.qfq', 'qfq', 'hand', 'ready',
                      '2026-07-14T15:20:00+08:00')
            """,
            [
                ("SH600000",),
                ("BJ920000",),
                ("SH000300",),
                ("SZ002842",),  # stale cache symbol, absent from official manifest
            ],
        )
    target = MarketHistoryStore(target_path)
    target.initialize()
    manifest_path, universe_hash = _write_universe_manifest(
        tmp_path / "universe.json",
        ["BJ920000", "SH600000", "SZ302132"],
    )

    result = CandidateHistorySeeder(source_path, target_path).run(
        apply=True,
        universe_scope="full_market_cache",
        universe_manifest_path=manifest_path,
        now=datetime(2026, 7, 15, 16, 0, tzinfo=SHANGHAI),
    )

    assert result["status"] == "partial"
    assert result["candidate_count"] == 3
    assert result["bar_count"] == 2
    assert result["universe_hash"] == universe_hash
    assert result["missing_qfq_symbols"] == ["SZ302132"]
    assert result["qfq_symbol_coverage"]["BJ"] == {
        "available": 1,
        "universe": 1,
        "pct": 100.0,
    }
    with target.connect(read_only=True) as connection:
        snapshot = dict(connection.execute("SELECT * FROM universe_snapshots").fetchone())
        symbols = [
            row[0]
            for row in connection.execute(
                "SELECT symbol FROM universe_members ORDER BY symbol"
            ).fetchall()
        ]
        ingest = dict(connection.execute("SELECT * FROM ingest_runs").fetchone())
    assert snapshot["universe_name"] == "a_share_full_market_cache"
    assert snapshot["provider"] == "akshare.segmented_exchange_code_lists"
    assert snapshot["source_hash"] == universe_hash
    assert symbols == ["BJ920000", "SH600000", "SZ302132"]
    assert ingest["dataset_name"] == "a_share_full_market_daily_bars"
    assert ingest["status"] == "partial"


def test_full_market_seed_preserves_v2_official_catalog_names(tmp_path) -> None:
    source_path = tmp_path / "trading_local.sqlite3"
    target_path = tmp_path / "market_history.sqlite3"
    source = SQLiteStore(source_path)
    source.init()
    with source.connect() as connection:
        connection.execute(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume, amount,
                source, adjustment_mode, volume_unit, quality_status, updated_at
            ) VALUES (
                'SH600000', '2026-07-14', 10, 10.2, 9.8, 10.1, 1000, NULL,
                'tencent.fqkline.qfq', 'qfq', 'hand', 'ready',
                '2026-07-14T15:20:00+08:00'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO stock_profiles(
                symbol, name, score, dataset_name, source_file, raw_json
            ) VALUES ('SH600000', '缓存旧名称', 0, 'fixture', 'fixture', '{}')
            """
        )
    target = MarketHistoryStore(target_path)
    target.initialize()
    manifest_path, _ = _write_universe_manifest(
        tmp_path / "universe-v2.json",
        ["SH600000"],
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema_version": 2,
            "manifest_kind": "a_share_instrument_catalog",
            "members": [
                {
                    "symbol": "SH600000",
                    "name": "浦发银行官方名称",
                    "exchange": "SH",
                    "board": "sh_main",
                    "status": "active",
                }
            ],
        }
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )

    result = CandidateHistorySeeder(source_path, target_path).run(
        apply=True,
        universe_scope="full_market_cache",
        universe_manifest_path=manifest_path,
        now=datetime(2026, 7, 15, 16, 0, tzinfo=SHANGHAI),
    )

    assert result["status"] == "completed"
    with target.connect(read_only=True) as connection:
        instrument = dict(
            connection.execute(
                "SELECT name, board, status FROM instruments WHERE symbol = 'SH600000'"
            ).fetchone()
        )
    assert instrument == {
        "name": "浦发银行官方名称",
        "board": "sh_main",
        "status": "active",
    }


def test_full_market_seed_batches_bars_but_keeps_one_complete_universe_snapshot(
    tmp_path,
) -> None:
    source_path = tmp_path / "trading_local.sqlite3"
    target_path = tmp_path / "market_history.sqlite3"
    source = SQLiteStore(source_path)
    source.init()
    with source.connect() as connection:
        connection.executemany(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume, amount,
                source, adjustment_mode, volume_unit, quality_status, updated_at
            ) VALUES (?, '2026-07-14', 10, 10.2, 9.8, 10.1, 1000, NULL,
                      'tencent.fqkline.qfq', 'qfq', 'hand', 'ready',
                      '2026-07-14T15:20:00+08:00')
            """,
            [("SH600000",), ("SZ000001",), ("BJ920000",)],
        )
    target = MarketHistoryStore(target_path)
    target.initialize()
    manifest_path, _ = _write_universe_manifest(
        tmp_path / "universe.json",
        ["SH600000", "SZ000001", "BJ920000"],
    )

    result = CandidateHistorySeeder(source_path, target_path).run(
        apply=True,
        universe_scope="full_market_cache",
        universe_manifest_path=manifest_path,
        symbol_limit=1,
        now=datetime(2026, 7, 15, 16, 0, tzinfo=SHANGHAI),
    )

    assert result["universe_count"] == 3
    assert result["candidate_count"] == 1
    assert result["last_processed_symbol"] == "BJ920000"
    with target.connect(read_only=True) as connection:
        member_count = connection.execute(
            "SELECT COUNT(*) FROM universe_members"
        ).fetchone()[0]
        bar_symbols = [
            row[0]
            for row in connection.execute("SELECT symbol FROM daily_bars").fetchall()
        ]
    assert member_count == 3
    assert bar_symbols == ["BJ920000"]


def test_apply_writes_candidate_snapshot_and_preserves_daily_bar_provenance(
    tmp_path,
) -> None:
    source_path = tmp_path / "trading_local.sqlite3"
    target_path = tmp_path / "market_history.sqlite3"
    source = _seed_source(source_path)
    target = MarketHistoryStore(target_path)
    target.initialize()

    result = CandidateHistorySeeder(source_path, target_path).run(
        apply=True,
        now=datetime(2026, 7, 15, 13, 30, tzinfo=SHANGHAI),
    )

    assert result["status"] == "completed"
    assert result["mode"] == "apply"
    assert result["write_stats"] == {
        "instruments": 1,
        "universe_snapshots": 1,
        "universe_members": 1,
        "ingest_runs": 1,
        "bars_inserted": 1,
        "bars_updated": 0,
        "bars_unchanged": 0,
    }
    with target.connect(read_only=True) as connection:
        bar = dict(connection.execute("SELECT * FROM daily_bars").fetchone())
        ingest = dict(connection.execute("SELECT * FROM ingest_runs").fetchone())
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("instruments", "universe_snapshots", "universe_members")
        }

    assert counts == {
        "instruments": 1,
        "universe_snapshots": 1,
        "universe_members": 1,
    }
    assert bar["symbol"] == "SZ002842"
    assert bar["trade_date"] == "2026-07-14"
    assert bar["adjustment_mode"] == "qfq"
    assert bar["provider"] == "tencent.fqkline.qfq"
    assert bar["amount"] == 21_400_000.0
    assert bar["volume_unit"] == "hand"
    assert bar["updated_at"] == "2026-07-14T15:20:00+08:00"
    assert bar["rule_regime"] == "cn_a_share_2026_07_06_onward"
    assert len(bar["row_hash"]) == 64
    assert bar["ingest_run_id"] == ingest["id"]
    assert ingest["status"] == "completed"
    assert ingest["research_only"] == 1
    assert ingest["live_trading_enabled"] == 0
    assert source.fetch_one("SELECT COUNT(*) AS count FROM daily_bar_cache")["count"] == 3


def test_repeated_apply_is_idempotent_and_keeps_unchanged_bar_provenance(tmp_path) -> None:
    source_path = tmp_path / "trading_local.sqlite3"
    target_path = tmp_path / "market_history.sqlite3"
    _seed_source(source_path)
    target = MarketHistoryStore(target_path)
    target.initialize()
    seeder = CandidateHistorySeeder(source_path, target_path)
    now = datetime(2026, 7, 15, 13, 30, tzinfo=SHANGHAI)

    first = seeder.run(apply=True, now=now)
    with target.connect(read_only=True) as connection:
        first_bar = dict(connection.execute("SELECT * FROM daily_bars").fetchone())
    second = seeder.run(apply=True, now=now)
    with target.connect(read_only=True) as connection:
        second_bar = dict(connection.execute("SELECT * FROM daily_bars").fetchone())
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "instruments",
                "universe_snapshots",
                "universe_members",
                "ingest_runs",
                "daily_bars",
            )
        }

    assert second["write_stats"]["universe_snapshots"] == 0
    assert second["write_stats"]["bars_inserted"] == 0
    assert second["write_stats"]["bars_updated"] == 0
    assert second["write_stats"]["bars_unchanged"] == 1
    assert first_bar["row_hash"] == second_bar["row_hash"]
    assert first_bar["ingest_run_id"] == first["ingest_run_id"]
    assert second_bar["ingest_run_id"] == first["ingest_run_id"]
    assert counts == {
        "instruments": 1,
        "universe_snapshots": 1,
        "universe_members": 1,
        "ingest_runs": 2,
        "daily_bars": 1,
    }


def test_unknown_adjustment_and_sina_rows_are_counted_but_never_seeded(tmp_path) -> None:
    source_path = tmp_path / "trading_local.sqlite3"
    target_path = tmp_path / "market_history.sqlite3"
    source = _seed_source(source_path)
    with source.connect() as connection:
        connection.executemany(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume, amount,
                source, adjustment_mode, volume_unit, quality_status, updated_at
            ) VALUES (?, ?, 9.8, 10.2, 9.7, 10.0, 1000, NULL, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "SZ002842",
                    "2026-07-11",
                    "sina.cn.kline_daily_fallback",
                    "qfq",
                    "share",
                    "ready",
                    "2026-07-11T15:20:00+08:00",
                ),
                (
                    "SZ002842",
                    "2026-07-12",
                    "tencent.legacy.unknown_adjustment",
                    "unknown",
                    "hand",
                    "ready",
                    "2026-07-12T15:20:00+08:00",
                ),
            ],
        )
    target = MarketHistoryStore(target_path)
    target.initialize()

    result = CandidateHistorySeeder(source_path, target_path).run(
        apply=True,
        now=datetime(2026, 7, 15, 13, 30, tzinfo=SHANGHAI),
    )

    assert result["status"] == "completed"
    assert result["excluded"] == {
        "unknown_adjustment_rows": 2,
        "sina_rows": 2,
        "non_ready_rows": 1,
        "incomplete_current_session_rows": 1,
        "invalid_ready_qfq_rows": 0,
    }
    with target.connect(read_only=True) as connection:
        bars = [dict(row) for row in connection.execute("SELECT * FROM daily_bars")]
    assert [(bar["trade_date"], bar["provider"]) for bar in bars] == [
        ("2026-07-14", "tencent.fqkline.qfq")
    ]


def test_live_trading_enabled_blocks_before_opening_source_or_target(
    tmp_path,
    monkeypatch,
) -> None:
    source_path = tmp_path / "trading_local.sqlite3"
    target_path = tmp_path / "market_history.sqlite3"
    source_sentinel = b"must-not-open-source"
    target_sentinel = b"must-not-open-target"
    source_path.write_bytes(source_sentinel)
    target_path.write_bytes(target_sentinel)
    monkeypatch.setattr(settings, "enable_live_trading", True)

    result = CandidateHistorySeeder(source_path, target_path).run(apply=True)

    assert result["status"] == "blocked"
    assert result["reason"] == "live_trading_enabled"
    assert result["writes_enabled"] is False
    assert result["safety"]["live_trading_enabled"] is True
    assert source_path.read_bytes() == source_sentinel
    assert target_path.read_bytes() == target_sentinel


def test_explicit_current_session_as_of_is_blocked_before_market_finalization(
    tmp_path,
) -> None:
    source_path = tmp_path / "trading_local.sqlite3"
    target_path = tmp_path / "market_history.sqlite3"
    _seed_source(source_path)
    target = MarketHistoryStore(target_path)
    target.initialize()

    result = CandidateHistorySeeder(source_path, target_path).run(
        apply=True,
        as_of="2026-07-15",
        now=datetime(2026, 7, 15, 13, 30, tzinfo=SHANGHAI),
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "as_of_is_not_a_completed_session"
    assert result["requested_as_of"] == "2026-07-15"
    assert result["completed_cutoff"] == "2026-07-14"
    assert target.inspect()["tables"]["counts"]["daily_bars"] == 0


def test_cli_defaults_to_dry_run_and_emits_json(capsys) -> None:
    class _RecordingSeeder:
        def __init__(self) -> None:
            self.kwargs = None

        def run(self, **kwargs):
            self.kwargs = kwargs
            return {
                "schema_version": "market_history_seed.v1",
                "status": "planned",
                "mode": "dry_run",
                "writes_enabled": False,
            }

    seeder = _RecordingSeeder()

    exit_code = main(
        [
            "--candidate-limit",
            "25",
            "--bars-per-symbol",
            "120",
            "--as-of",
            "2026-07-14",
        ],
        seeder=seeder,
    )

    assert exit_code == 0
    assert seeder.kwargs == {
        "apply": False,
        "candidate_limit": 25,
        "bars_per_symbol": 120,
        "universe_scope": "candidate_hot_cache",
        "universe_manifest_path": None,
        "resume_after": None,
        "symbol_limit": None,
        "as_of": "2026-07-14",
    }
    assert '"mode": "dry_run"' in capsys.readouterr().out


def test_after_close_still_rejects_current_day_rows_fetched_before_finalization(
    tmp_path,
) -> None:
    source_path = tmp_path / "trading_local.sqlite3"
    target_path = tmp_path / "market_history.sqlite3"
    source = _seed_source(source_path)
    with source.connect() as connection:
        connection.execute(
            """
            INSERT INTO candidate_lifecycle(
                symbol, name, state, score, source, reason, raw_json
            ) VALUES (
                'SH600000', '浦发银行', 'focus_watch', 50,
                'fixture', 'completed current-day fixture', '{}'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume, amount,
                source, adjustment_mode, volume_unit, quality_status, updated_at
            ) VALUES (
                'SH600000', '2026-07-15', 10, 10.5, 9.9, 10.3, 1000, 1030000,
                'tencent.fqkline.qfq', 'qfq', 'hand', 'ready',
                '2026-07-15T15:20:00+08:00'
            )
            """
        )
    target = MarketHistoryStore(target_path)
    target.initialize()

    result = CandidateHistorySeeder(source_path, target_path).run(
        apply=True,
        now=datetime(2026, 7, 15, 15, 30, tzinfo=SHANGHAI),
    )

    assert result["as_of"] == "2026-07-15"
    assert result["bar_count"] == 2
    assert result["excluded"]["incomplete_current_session_rows"] == 1
    with target.connect(read_only=True) as connection:
        bars = [
            (row["symbol"], row["trade_date"])
            for row in connection.execute(
                "SELECT symbol, trade_date FROM daily_bars ORDER BY symbol, trade_date"
            )
        ]
    assert bars == [("SH600000", "2026-07-15"), ("SZ002842", "2026-07-14")]


def test_row_hash_is_stable_when_only_source_fetch_timestamp_changes(tmp_path) -> None:
    source_path = tmp_path / "trading_local.sqlite3"
    target_path = tmp_path / "market_history.sqlite3"
    source = _seed_source(source_path)
    target = MarketHistoryStore(target_path)
    target.initialize()
    seeder = CandidateHistorySeeder(source_path, target_path)
    now = datetime(2026, 7, 15, 13, 30, tzinfo=SHANGHAI)

    first = seeder.run(apply=True, now=now)
    with target.connect(read_only=True) as connection:
        first_bar = dict(connection.execute("SELECT * FROM daily_bars").fetchone())
    with source.connect() as connection:
        connection.execute(
            """
            UPDATE daily_bar_cache
            SET updated_at = '2026-07-15T09:00:00+08:00'
            WHERE symbol = 'SZ002842' AND trade_date = '2026-07-14'
            """
        )

    second = seeder.run(apply=True, now=now)
    with target.connect(read_only=True) as connection:
        second_bar = dict(connection.execute("SELECT * FROM daily_bars").fetchone())

    assert second["write_stats"]["bars_updated"] == 1
    assert first_bar["row_hash"] == second_bar["row_hash"]
    assert first_bar["ingest_run_id"] == first["ingest_run_id"]
    assert second_bar["ingest_run_id"] == second["ingest_run_id"]
    assert second_bar["updated_at"] == "2026-07-15T09:00:00+08:00"
