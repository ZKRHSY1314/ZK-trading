from __future__ import annotations

import json
from datetime import date, datetime
import hashlib
from zoneinfo import ZoneInfo

import pytest

from app.data import daily_bar_cache
from app.data.daily_bar_cache import DailyBarCacheService
from app.data.market_history import MarketHistoryStore
from app.storage.sqlite_store import SQLiteStore
from scripts import market_history_refresh_loop
from scripts.seed_market_history import CandidateHistorySeeder


SHANGHAI = ZoneInfo("Asia/Shanghai")


def _write_manifest(path, symbols: list[str]) -> None:
    normalized = sorted(symbols)
    path.write_text(
        json.dumps(
            {
                "schema_version": "current_a_share_universe.v1",
                "observed_at": "2026-07-15T08:00:00+00:00",
                "universe_count": len(normalized),
                "universe_symbols": normalized,
                "universe_hash": hashlib.sha256(
                    "\n".join(normalized).encode("utf-8")
                ).hexdigest(),
                "discovery_source": "pytest.official_universe",
                "discovery_complete": True,
                "live_trading_enabled": False,
            }
        ),
        encoding="utf-8",
    )


def _seed_runtime_bar(store: SQLiteStore, symbol: str, trade_date: str) -> None:
    with store.connect() as connection:
        connection.execute(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume, amount,
                source, adjustment_mode, volume_unit, quality_status, updated_at
            ) VALUES (?, ?, 10, 10.2, 9.8, 10.1, 1000, 10000,
                      'tencent.fqkline.qfq', 'qfq', 'hand', 'ready',
                      '2026-07-15T16:00:00+08:00')
            """,
            (symbol, trade_date),
        )


def test_latest_qfq_dates_allows_only_exact_unit_verified_sina_composite(
    tmp_path,
) -> None:
    database = tmp_path / "runtime.sqlite3"
    store = SQLiteStore(database)
    store.init()
    with store.connect() as connection:
        connection.executemany(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume, source,
                adjustment_mode, volume_unit, quality_status
            ) VALUES (?, '2026-07-15', 10, 10.2, 9.8, 10.1, 1000,
                      ?, 'qfq', 'hand', 'ready')
            """,
            [
                (
                    "BJ920000",
                    "tencent.fqkline.raw+sina.qfq_factor.unit_verified",
                ),
                ("SH600000", "sina.cn.kline_daily_fallback"),
            ],
        )

    latest = market_history_refresh_loop._latest_qfq_dates(
        database,
        table="daily_bar_cache",
        symbols=["BJ920000", "SH600000"],
    )

    assert latest == {"BJ920000": date(2026, 7, 15)}


@pytest.mark.parametrize(("days", "expected_count"), [(7, 120), (150, 150), (500, 500)])
def test_tencent_only_refresh_uses_a_bounded_qfq_request(
    monkeypatch,
    tmp_path,
    days: int,
    expected_count: int,
) -> None:
    store = SQLiteStore(tmp_path / f"cache-{days}.sqlite3")
    store.init()
    service = DailyBarCacheService(store=store)
    requested_urls: list[str] = []

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "code": 0,
                    "data": {
                        "sh600000": {
                            "qfqday": [
                                ["2026-07-15", "10", "10.1", "10.2", "9.9", "1000"]
                            ]
                        }
                    },
                }
            ).encode("utf-8")

    def _urlopen(request, timeout):
        requested_urls.append(request.full_url)
        assert timeout == 20
        return _Response()

    monkeypatch.setattr(daily_bar_cache, "urlopen", _urlopen)
    monkeypatch.setattr(
        service.builder.provider,
        "get_daily_bars",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("tencent_only must not call AKShare")
        ),
    )

    result = service.refresh_symbols(
        ["SH600000"],
        days=days,
        source_policy="tencent_only",
        max_workers=1,
    )

    assert result["results"][0]["status"] == "success"
    assert result["results"][0]["latest_trade_date"] == "2026-07-15"
    assert len(requested_urls) == 1
    assert f",day,,,{expected_count},qfq" in requested_urls[0]


def test_refresh_worker_blocks_on_health_before_opening_data_files(tmp_path) -> None:
    calls: list[tuple[str, str]] = []

    def _request(method, url, payload=None, *, timeout=30):
        calls.append((method, url))
        return {"status": "ok", "live_trading_enabled": True}

    result = market_history_refresh_loop.run_once(
        "http://127.0.0.1:8000",
        source_database=tmp_path / "must-not-open-source.sqlite3",
        target_database=tmp_path / "must-not-open-target.sqlite3",
        universe_manifest_path=tmp_path / "must-not-open-manifest.json",
        request_fn=_request,
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "live_trading_enabled"
    assert result["safety"]["live_trading_enabled"] is True
    assert calls == [("GET", "http://127.0.0.1:8000/health")]
    assert not any(tmp_path.iterdir())


def test_up_to_date_history_skips_remote_refresh_and_still_scans(
    monkeypatch,
    tmp_path,
) -> None:
    source_path = tmp_path / "trading.sqlite3"
    target_path = tmp_path / "history.sqlite3"
    manifest_path = tmp_path / "official.json"
    source = SQLiteStore(source_path)
    source.init()
    _seed_runtime_bar(source, "SH600000", "2026-07-15")
    _write_manifest(manifest_path, ["SH600000"])
    MarketHistoryStore(target_path).initialize()
    seeded = CandidateHistorySeeder(source_path, target_path).run(
        apply=True,
        universe_scope="full_market_cache",
        universe_manifest_path=manifest_path,
        bars_per_symbol=150,
        now=datetime(2026, 7, 16, 10, 0, tzinfo=SHANGHAI),
    )
    assert seeded["status"] == "completed"

    monkeypatch.setattr(
        DailyBarCacheService,
        "refresh_symbols",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("up-to-date history must make no remote refresh")
        ),
    )
    calls: list[tuple[str, str]] = []

    def _request(method, url, payload=None, *, timeout=30):
        calls.append((method, url))
        if url.endswith("/health"):
            return {"status": "ok", "live_trading_enabled": False}
        return {"status": "completed", "scan_id": 41, "selected_count": 3}

    result = market_history_refresh_loop.run_once(
        "http://127.0.0.1:8000",
        source_database=source_path,
        target_database=target_path,
        universe_manifest_path=manifest_path,
        now=datetime(2026, 7, 16, 10, 0, tzinfo=SHANGHAI),
        trading_dates={date(2026, 7, 15), date(2026, 7, 16)},
        request_fn=_request,
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "up_to_date"
    assert result["target_session"] == "2026-07-15"
    assert result["refresh_planned"] == 0
    assert result["scan"]["status"] == "completed"
    assert [method for method, _url in calls] == ["GET", "POST"]


def test_up_to_date_history_degrades_when_followup_scan_fails(
    monkeypatch,
    tmp_path,
) -> None:
    source_path = tmp_path / "trading.sqlite3"
    target_path = tmp_path / "history.sqlite3"
    manifest_path = tmp_path / "official.json"
    source = SQLiteStore(source_path)
    source.init()
    _seed_runtime_bar(source, "SH600000", "2026-07-15")
    _write_manifest(manifest_path, ["SH600000"])
    MarketHistoryStore(target_path).initialize()
    CandidateHistorySeeder(source_path, target_path).run(
        apply=True,
        universe_scope="full_market_cache",
        universe_manifest_path=manifest_path,
        bars_per_symbol=150,
        now=datetime(2026, 7, 16, 10, 0, tzinfo=SHANGHAI),
    )
    monkeypatch.setattr(
        DailyBarCacheService,
        "refresh_symbols",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("up-to-date history must make no remote refresh")
        ),
    )

    def _request(method, url, payload=None, *, timeout=30):
        if url.endswith("/health"):
            return {"status": "ok", "live_trading_enabled": False}
        return {"status": "failed", "reason": "scan_unavailable"}

    result = market_history_refresh_loop.run_once(
        "http://127.0.0.1:8000",
        source_database=source_path,
        target_database=target_path,
        universe_manifest_path=manifest_path,
        now=datetime(2026, 7, 16, 10, 0, tzinfo=SHANGHAI),
        trading_dates={date(2026, 7, 15), date(2026, 7, 16)},
        request_fn=_request,
    )

    assert result["status"] == "partial"
    assert result["reason"] == "up_to_date_scan_failed"
    assert result["errors"] == [
        {
            "stage": "scan",
            "status": "failed",
            "error": "scan_unavailable",
        }
    ]
    assert market_history_refresh_loop.next_interval_seconds(
        result["status"],
        14_400,
        900,
    ) == 900


def test_manifest_hash_change_refreshes_complete_snapshot_without_new_qfq_bars(
    monkeypatch,
    tmp_path,
) -> None:
    source_path = tmp_path / "trading.sqlite3"
    target_path = tmp_path / "history.sqlite3"
    manifest_path = tmp_path / "official.json"
    source = SQLiteStore(source_path)
    source.init()
    _seed_runtime_bar(source, "SH600000", "2026-07-15")
    _write_manifest(manifest_path, ["SH600000"])
    MarketHistoryStore(target_path).initialize()
    first = CandidateHistorySeeder(source_path, target_path).run(
        apply=True,
        universe_scope="full_market_cache",
        universe_manifest_path=manifest_path,
        now=datetime(2026, 7, 16, 10, 0, tzinfo=SHANGHAI),
    )
    assert first["status"] == "completed"

    _write_manifest(manifest_path, ["BJ920000", "SH600000"])
    manifest = CandidateHistorySeeder._load_universe_manifest(manifest_path)

    monkeypatch.setattr(
        DailyBarCacheService,
        "refresh_symbols",
        lambda _self, symbols, **_kwargs: {
            "results": [
                {
                    "symbol": symbol,
                    "status": "isolated_non_qfq",
                    "error": "fixture_raw_only",
                }
                for symbol in symbols
            ]
        },
    )

    def _request(method, url, payload=None, *, timeout=30):
        if url.endswith("/health"):
            return {"status": "ok", "live_trading_enabled": False}
        return {"status": "completed", "scan_id": 44, "selected_count": 1}

    result = market_history_refresh_loop.run_once(
        "http://127.0.0.1:8000",
        source_database=source_path,
        target_database=target_path,
        universe_manifest_path=manifest_path,
        now=datetime(2026, 7, 16, 10, 0, tzinfo=SHANGHAI),
        trading_dates={date(2026, 7, 15), date(2026, 7, 16)},
        request_fn=_request,
    )

    assert result["universe_snapshot_refresh_needed"] is True
    assert result["universe_snapshot_refreshed"] is True
    assert result["seed_batches"] >= 1
    with MarketHistoryStore(target_path).connect(read_only=True) as connection:
        snapshot = dict(
            connection.execute(
                """
                SELECT id, member_count, source_hash
                FROM universe_snapshots
                WHERE universe_name = 'a_share_full_market_cache'
                ORDER BY id DESC LIMIT 1
                """
            ).fetchone()
        )
        actual_members = connection.execute(
            "SELECT COUNT(*) FROM universe_members WHERE snapshot_id = ?",
            (snapshot["id"],),
        ).fetchone()[0]
    assert snapshot["member_count"] == 2
    assert actual_members == 2
    assert snapshot["source_hash"] == manifest["universe_hash"]


def test_due_cycle_refreshes_qfq_cache_seeds_history_then_scans(
    monkeypatch,
    tmp_path,
) -> None:
    source_path = tmp_path / "trading.sqlite3"
    target_path = tmp_path / "history.sqlite3"
    manifest_path = tmp_path / "official.json"
    source = SQLiteStore(source_path)
    source.init()
    _seed_runtime_bar(source, "SH600000", "2026-07-14")
    _write_manifest(manifest_path, ["SH600000"])
    MarketHistoryStore(target_path).initialize()
    requested_urls: list[str] = []

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "code": 0,
                    "data": {
                        "sh600000": {
                            "qfqday": [
                                ["2026-07-14", "10", "10.1", "10.2", "9.9", "1000"],
                                ["2026-07-15", "10.1", "10.3", "10.4", "10", "1200"],
                            ]
                        }
                    },
                }
            ).encode("utf-8")

    def _urlopen(request, timeout):
        requested_urls.append(request.full_url)
        return _Response()

    monkeypatch.setattr(daily_bar_cache, "urlopen", _urlopen)
    calls: list[tuple[str, str]] = []

    def _request(method, url, payload=None, *, timeout=30):
        calls.append((method, url))
        if url.endswith("/health"):
            return {"status": "ok", "live_trading_enabled": False}
        return {"status": "completed", "scan_id": 42, "selected_count": 1}

    progress: list[dict] = []
    result = market_history_refresh_loop.run_once(
        "http://127.0.0.1:8000",
        source_database=source_path,
        target_database=target_path,
        universe_manifest_path=manifest_path,
        days=150,
        batch_size=200,
        max_workers=20,
        seed_batch_size=500,
        deadline_seconds=900,
        now=datetime(2026, 7, 16, 10, 0, tzinfo=SHANGHAI),
        trading_dates={date(2026, 7, 14), date(2026, 7, 15), date(2026, 7, 16)},
        request_fn=_request,
        progress_fn=progress.append,
    )

    assert result["status"] == "completed"
    assert result["refresh_planned"] == 1
    assert result["refreshed"] == 1
    assert result["refresh_failed"] == 0
    assert result["seed_batches"] == 1
    assert result["seeded_symbols"] == 1
    assert result["scan"]["scan_id"] == 42
    assert [item["phase"] for item in progress] == [
        "planning",
        "refresh",
        "seed",
        "scan",
    ]
    assert len(requested_urls) == 1
    assert ",day,,,150,qfq" in requested_urls[0]
    with MarketHistoryStore(target_path).connect(read_only=True) as connection:
        latest = connection.execute(
            "SELECT MAX(trade_date) FROM daily_bars WHERE symbol = 'SH600000'"
        ).fetchone()[0]
    assert latest == "2026-07-15"
    assert [method for method, _url in calls] == ["GET", "POST"]


def test_partial_refresh_preserves_old_qfq_and_keeps_unresolved_gaps_isolated(
    monkeypatch,
    tmp_path,
) -> None:
    source_path = tmp_path / "trading.sqlite3"
    target_path = tmp_path / "history.sqlite3"
    manifest_path = tmp_path / "official.json"
    source = SQLiteStore(source_path)
    source.init()
    _seed_runtime_bar(source, "SH600000", "2026-07-14")
    _write_manifest(manifest_path, ["BJ920000", "SH600000"])
    MarketHistoryStore(target_path).initialize()
    seeded = CandidateHistorySeeder(source_path, target_path).run(
        apply=True,
        universe_scope="full_market_cache",
        universe_manifest_path=manifest_path,
        bars_per_symbol=150,
        now=datetime(2026, 7, 16, 10, 0, tzinfo=SHANGHAI),
    )
    assert seeded["status"] == "partial"

    monkeypatch.setattr(
        daily_bar_cache,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("provider timed out")),
    )

    def _request(method, url, payload=None, *, timeout=30):
        if url.endswith("/health"):
            return {"status": "ok", "live_trading_enabled": False}
        return {"status": "completed", "scan_id": 43, "selected_count": 0}

    result = market_history_refresh_loop.run_once(
        "http://127.0.0.1:8000",
        source_database=source_path,
        target_database=target_path,
        universe_manifest_path=manifest_path,
        now=datetime(2026, 7, 16, 10, 0, tzinfo=SHANGHAI),
        trading_dates={date(2026, 7, 14), date(2026, 7, 15), date(2026, 7, 16)},
        request_fn=_request,
    )

    assert result["status"] == "partial"
    assert result["qfq_ready_count"] == 1
    assert result["qfq_gap_count_before"] == 1
    assert result["qfq_gap_recovery_planned"] == 1
    assert result["qfq_gap_recovered"] == 0
    assert result["qfq_gap_remaining"] == 1
    assert result["permanent_qfq_gap_count"] == 1
    assert result["refresh_planned"] == 2
    assert result["refreshed"] == 0
    assert result["refresh_failed"] == 2
    errors_by_symbol = {
        item["symbol"]: item
        for item in result["errors"]
        if item.get("stage") == "refresh" and item.get("symbol")
    }
    assert set(errors_by_symbol) == {"BJ920000", "SH600000"}
    assert errors_by_symbol["SH600000"]["status"] == "degraded_cached"
    assert result["scan"]["status"] == "completed"
    rows = source.fetch_all(
        "SELECT trade_date, quality_status, adjustment_mode FROM daily_bar_cache "
        "WHERE symbol = 'SH600000' ORDER BY trade_date"
    )
    assert rows == [
        {
            "trade_date": "2026-07-14",
            "quality_status": "ready",
            "adjustment_mode": "qfq",
        }
    ]


def test_refresh_worker_recovers_missing_qfq_symbols_with_verified_fallback(
    monkeypatch,
    tmp_path,
) -> None:
    source_path = tmp_path / "trading.sqlite3"
    target_path = tmp_path / "history.sqlite3"
    manifest_path = tmp_path / "official.json"
    source = SQLiteStore(source_path)
    source.init()
    _seed_runtime_bar(source, "SH600000", "2026-07-15")
    _write_manifest(manifest_path, ["BJ920000", "SH600000"])
    MarketHistoryStore(target_path).initialize()
    CandidateHistorySeeder(source_path, target_path).run(
        apply=True,
        universe_scope="full_market_cache",
        universe_manifest_path=manifest_path,
        bars_per_symbol=150,
        now=datetime(2026, 7, 16, 10, 0, tzinfo=SHANGHAI),
    )

    requested_urls: list[str] = []

    class _Response:
        def __init__(self, body: str) -> None:
            self.body = body.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return self.body

    def _urlopen(request, timeout):
        assert timeout == 20
        requested_urls.append(request.full_url)
        if "/appstock/app/fqkline/get?" in request.full_url:
            return _Response(
                json.dumps(
                    {
                        "code": 0,
                        "data": {
                            "bj920000": {
                                "day": [
                                    [
                                        "2026-07-15",
                                        "99.0",
                                        "99.5",
                                        "100.0",
                                        "98.0",
                                        "1000",
                                    ]
                                ]
                            }
                        },
                    }
                )
            )
        payload = {
            "code": 0,
            "data": {
                "bj920000": {
                    "qfqday": [
                        ["2026-07-15", "11.5", "11.6", "11.8", "11.3", "1000"]
                    ]
                }
            },
        }
        return _Response(f"kline_dayqfq={json.dumps(payload)}")

    monkeypatch.setattr(daily_bar_cache, "urlopen", _urlopen)

    def _request(method, url, payload=None, *, timeout=30):
        if url.endswith("/health"):
            return {"status": "ok", "live_trading_enabled": False}
        return {"status": "completed", "scan_id": 44, "selected_count": 1}

    result = market_history_refresh_loop.run_once(
        "http://127.0.0.1:8000",
        source_database=source_path,
        target_database=target_path,
        universe_manifest_path=manifest_path,
        now=datetime(2026, 7, 16, 10, 0, tzinfo=SHANGHAI),
        trading_dates={date(2026, 7, 14), date(2026, 7, 15), date(2026, 7, 16)},
        request_fn=_request,
        gap_recovery_limit=500,
    )

    assert result["status"] == "completed"
    assert result["qfq_gap_count_before"] == 1
    assert result["qfq_gap_recovery_planned"] == 1
    assert result["qfq_gap_recovered"] == 1
    assert result["qfq_gap_remaining"] == 0
    assert result["permanent_qfq_gap_count"] == 0
    assert result["qfq_ready_count"] == 2
    assert result["refresh_planned"] == 1
    assert result["refreshed"] == 1
    assert len(requested_urls) == 2
    assert "/appstock/app/fqkline/get?" in requested_urls[0]
    assert "/appstock/app/newfqkline/get?" in requested_urls[1]
    assert source.fetch_one(
        "SELECT source, adjustment_mode, quality_status FROM daily_bar_cache "
        "WHERE symbol = 'BJ920000' AND trade_date = '2026-07-15'"
    ) == {
        "source": "tencent.newfqkline.qfq",
        "adjustment_mode": "qfq",
        "quality_status": "ready",
    }


def test_up_to_date_worker_wakes_near_session_finalization() -> None:
    interval = market_history_refresh_loop.next_interval_seconds(
        "skipped",
        14_400,
        900,
        reason="up_to_date",
        now=datetime(2026, 7, 16, 14, 53, tzinfo=SHANGHAI),
    )

    assert interval == 1_380


def test_worker_heartbeat_exposes_progress_and_partial_retry(tmp_path) -> None:
    heartbeat_path = tmp_path / "heartbeat.json"

    def _runner(api_base, **kwargs):
        assert api_base == "http://127.0.0.1:8000"
        assert kwargs["gap_recovery_limit"] == 500
        kwargs["progress_fn"](
            {
                "phase": "refresh",
                "status": "running",
                "progress": {"planned": 200, "attempted": 100},
            }
        )
        return {
            "status": "partial",
            "target_session": "2026-07-15",
            "calendar_source": "injected",
            "official_universe_count": 5528,
            "qfq_ready_count": 5129,
            "qfq_gap_count_before": 399,
            "qfq_gap_recovery_planned": 399,
            "qfq_gap_recovered": 398,
            "qfq_gap_remaining": 1,
            "permanent_qfq_gap_count": 399,
            "refresh_planned": 200,
            "refreshed": 199,
            "refresh_failed": 1,
            "seed_batches": 1,
            "seeded_symbols": 199,
            "scan": {"status": "completed", "scan_id": 44, "selected_count": 10},
            "errors": [
                {"stage": "refresh", "symbol": "SH600000", "error": "timeout"}
            ],
            "safety": {
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": False,
            },
        }

    rc = market_history_refresh_loop.main(
        [
            "--max-cycles",
            "1",
            "--heartbeat-path",
            str(heartbeat_path),
        ],
        runner=_runner,
    )

    assert rc == 0
    heartbeat = json.loads(heartbeat_path.read_text(encoding="utf-8"))
    assert heartbeat["status"] == "partial"
    assert heartbeat["phase"] == "retry_wait"
    assert heartbeat["next_interval_seconds"] == 900
    assert heartbeat["deadline_seconds"] == 900
    assert heartbeat["days"] == 150
    assert heartbeat["batch_size"] == 200
    assert heartbeat["max_workers"] == 20
    assert heartbeat["seed_batch_size"] == 500
    assert heartbeat["gap_recovery_limit"] == 500
    assert heartbeat["qfq_gap_count_before"] == 399
    assert heartbeat["qfq_gap_recovery_planned"] == 399
    assert heartbeat["qfq_gap_recovered"] == 398
    assert heartbeat["qfq_gap_remaining"] == 1
    assert heartbeat["progress"] == {"planned": 200, "attempted": 100}
    assert heartbeat["scan_status"] == "completed"
    assert heartbeat["error_count"] == 1
    assert heartbeat["live_trading_enabled"] is False
