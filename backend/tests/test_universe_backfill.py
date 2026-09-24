from __future__ import annotations

import json

import pandas as pd
import pytest

from app.config import settings
from app.data.universe_backfill import UniverseBackfillService
from app.data.daily_bar_cache import DailyBarCacheService
from app.storage.sqlite_store import SQLiteStore
from scripts.backfill_market_universe import (
    DEFAULT_CHECKPOINT_PATH,
    DEFAULT_MANIFEST_PATH,
    main,
)


class _Provider:
    def __init__(self, codes: list[object]) -> None:
        self.codes = codes

    def get_a_share_spot(self) -> pd.DataFrame:
        return pd.DataFrame({"代码": self.codes})


class _FallbackProvider:
    def __init__(self, codes: list[object]) -> None:
        self.codes = codes

    def get_a_share_spot(self) -> pd.DataFrame:
        raise RuntimeError("primary spot unavailable")

    def get_a_share_code_name(self) -> pd.DataFrame:
        return pd.DataFrame({"code": self.codes, "name": ["fixture"] * len(self.codes)})


class _SegmentedProvider:
    def get_sh_main_code_name(self) -> pd.DataFrame:
        return pd.DataFrame({"证券代码": ["600000"]})

    def get_sh_star_code_name(self) -> pd.DataFrame:
        raise RuntimeError("STAR endpoint unavailable")

    def get_sz_a_code_name(self) -> pd.DataFrame:
        return pd.DataFrame({"A股代码": ["000001"]})

    def get_bj_code_name(self) -> pd.DataFrame:
        return pd.DataFrame({"证券代码": ["920000"]})


class _NoWriteCache:
    def refresh_symbols(
        self,
        symbols: list[str],
        days: int = 120,
        source_policy: str = "akshare_first",
        max_workers: int = 5,
    ) -> dict[str, object]:
        raise AssertionError("planning must not refresh the cache")


class _RecordingCache:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self.calls: list[tuple[list[str], int]] = []

    def refresh_symbols(
        self,
        symbols: list[str],
        days: int = 120,
        source_policy: str = "akshare_first",
        max_workers: int = 5,
    ) -> dict[str, object]:
        self.calls.append((symbols, days))
        return {"processed": len(symbols), "results": []}


class _ResultCache(_RecordingCache):
    def __init__(self, store: SQLiteStore, *, error_symbol: str | None = None) -> None:
        super().__init__(store)
        self.error_symbol = error_symbol

    def refresh_symbols(
        self,
        symbols: list[str],
        days: int = 120,
        source_policy: str = "akshare_first",
        max_workers: int = 5,
    ) -> dict[str, object]:
        self.calls.append((symbols, days))
        results = [
            {
                "symbol": symbol,
                "status": "error" if symbol == self.error_symbol else "success",
            }
            for symbol in symbols
        ]
        return {"processed": len(results), "results": results}


class _ExplodingCache(_RecordingCache):
    def __init__(self, store: SQLiteStore, bad_symbol: str) -> None:
        super().__init__(store)
        self.bad_symbol = bad_symbol

    def refresh_symbols(
        self,
        symbols: list[str],
        days: int = 120,
        source_policy: str = "akshare_first",
        max_workers: int = 5,
    ) -> dict[str, object]:
        self.calls.append((symbols, days))
        if len(symbols) > 1:
            raise RuntimeError("batch transport failed")
        if symbols[0] == self.bad_symbol:
            raise RuntimeError("symbol source failed")
        return {
            "processed": 1,
            "results": [{"symbol": symbols[0], "status": "success"}],
        }


class _PolicyRecordingCache(_RecordingCache):
    def __init__(self, store: SQLiteStore) -> None:
        super().__init__(store)
        self.policies: list[str] = []
        self.worker_limits: list[int] = []

    def refresh_symbols(
        self,
        symbols: list[str],
        days: int = 120,
        source_policy: str = "akshare_first",
        max_workers: int = 5,
    ) -> dict[str, object]:
        self.calls.append((symbols, days))
        self.policies.append(source_policy)
        self.worker_limits.append(max_workers)
        return {
            "processed": len(symbols),
            "results": [
                {"symbol": symbol, "status": "success"} for symbol in symbols
            ],
        }


class _IsolationCache(_RecordingCache):
    def refresh_symbols(
        self,
        symbols: list[str],
        days: int = 120,
        source_policy: str = "akshare_first",
        max_workers: int = 5,
    ) -> dict[str, object]:
        self.calls.append((symbols, days))
        return {
            "processed": len(symbols),
            "results": [
                {
                    "symbol": symbol,
                    "status": "isolated_non_qfq" if symbol.startswith("BJ") else "success",
                    "adjustment_mode": "none" if symbol.startswith("BJ") else "qfq",
                }
                for symbol in symbols
            ],
        }


class _BenchmarkCache(_ResultCache):
    def __init__(
        self,
        store: SQLiteStore,
        *,
        benchmark_response: dict[str, object] | None = None,
        benchmark_error: Exception | None = None,
    ) -> None:
        super().__init__(store)
        self.benchmark_response = benchmark_response or {
            "status": "completed",
            "processed": 2,
            "results": [
                {"symbol": "SH000300", "status": "success"},
                {"symbol": "SH000001", "status": "success"},
            ],
        }
        self.benchmark_error = benchmark_error
        self.benchmark_calls: list[tuple[list[str], int]] = []

    def refresh_benchmark_bars(
        self,
        symbols: list[str],
        days: int = 500,
    ) -> dict[str, object]:
        self.benchmark_calls.append((symbols, days))
        if self.benchmark_error is not None:
            raise self.benchmark_error
        return self.benchmark_response


def test_plan_normalizes_and_filters_the_current_a_share_universe() -> None:
    provider = _Provider(
        [
            "1",
            "SZ000001",
            "600000",
            "sh688001",
            "300750",
            "302132",
            "200001",  # Shenzhen B share
            "900901",  # Shanghai B share
            "430047",  # Beijing exchange legacy code
            None,
            "not-a-code",
        ]
    )

    plan = UniverseBackfillService(provider=provider, cache_service=_NoWriteCache()).plan()

    assert plan.universe_count == 6
    assert plan.symbols == (
        "BJ430047",
        "SH600000",
        "SH688001",
        "SZ000001",
        "SZ300750",
        "SZ302132",
    )
    assert plan.discovery_status == "complete_external"
    assert plan.discovery_complete is True


def test_segmented_exchange_discovery_keeps_healthy_markets_when_one_endpoint_fails() -> None:
    plan = UniverseBackfillService(
        provider=_SegmentedProvider(),
        cache_service=_NoWriteCache(),
    ).plan()

    assert plan.universe_count == 3
    assert plan.symbols == ("BJ920000", "SH600000", "SZ000001")
    assert plan.discovery_source == "akshare.segmented_exchange_code_lists"
    assert plan.discovery_status == "partial_external"
    assert plan.discovery_complete is False
    assert [
        (item["source"], item["status"], item["count"])
        for item in plan.discovery_attempts
    ] == [
        ("akshare.stock_info_sh_name_code.main", "success", 1),
        ("akshare.stock_info_sh_name_code.star", "error", 0),
        ("akshare.stock_info_sz_name_code.a", "success", 1),
        ("akshare.stock_info_bj_name_code", "success", 1),
    ]


def test_discovery_falls_back_to_independent_external_code_list(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "external-fallback.sqlite3")
    store.init()

    result = UniverseBackfillService(
        provider=_FallbackProvider(["000001", "600000", "430047"]),
        cache_service=_RecordingCache(store),
    ).run()

    assert result["status"] == "planned"
    assert result["universe_count"] == 3
    assert result["discovery"]["source"] == "akshare.stock_info_a_code_name"
    assert result["discovery"]["status"] == "complete_external"
    assert result["discovery"]["complete"] is True
    assert [item["status"] for item in result["discovery"]["attempts"]] == [
        "error",
        "success",
    ]


def test_local_known_symbols_are_explicitly_degraded_not_full_market(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "local-fallback.sqlite3")
    store.init()
    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO daily_bar_cache(symbol, trade_date, close, source, quality_status)
            VALUES ('SH600000', '2026-07-10', 10, 'fixture', 'ready')
            """
        )
        conn.execute(
            """
            INSERT INTO stock_profiles(symbol, name, dataset_name, source_file, raw_json)
            VALUES ('SZ000001', 'fixture', 'fixture', 'fixture', '{}')
            """
        )
        snapshot = conn.execute(
            """
            INSERT INTO sector_membership_snapshots(
                source, sector, member_hash, member_count, observed_at,
                effective_date, confidence
            ) VALUES (
                'fixture', 'semiconductor', 'snapshot-hash', 1,
                '2026-07-10T09:00:00+08:00', '2026-07-10', 0.9
            )
            """
        )
        conn.execute(
            """
            INSERT INTO sector_membership_snapshot_members(snapshot_id, symbol)
            VALUES (?, 'SZ300750')
            """,
            (snapshot.lastrowid,),
        )

    class _UnavailableProvider:
        def get_a_share_spot(self) -> pd.DataFrame:
            raise RuntimeError("primary unavailable")

        def get_a_share_code_name(self) -> pd.DataFrame:
            raise RuntimeError("fallback unavailable")

    result = UniverseBackfillService(
        provider=_UnavailableProvider(),
        cache_service=_RecordingCache(store),
    ).run()

    assert result["status"] == "degraded"
    assert result["planned"] == 3
    assert result["discovery"] == {
        "source": "local_known_symbols",
        "status": "degraded_local_partial",
        "complete": False,
        "attempts": [
            {
                "source": "akshare.stock_zh_a_spot_em",
                "status": "error",
                "count": 0,
                "error": "primary unavailable",
            },
            {
                "source": "akshare.stock_info_a_code_name",
                "status": "error",
                "count": 0,
                "error": "fallback unavailable",
            },
            {
                "source": "local_known_symbols",
                "status": "success_partial",
                "count": 3,
            },
        ],
    }


def test_run_is_a_read_only_dry_run_until_apply_is_explicit(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "dry-run.sqlite3")
    store.init()
    cache = _RecordingCache(store)

    result = UniverseBackfillService(
        provider=_Provider(["000001", "600000", "300750"]),
        cache_service=cache,
    ).run(days=300, batch_size=2)

    assert result["mode"] == "dry_run"
    assert result["universe_count"] == 3
    assert result["planned"] == 3
    assert result["processed"] == 0
    assert result["success"] == 0
    assert result["error"] == 0
    assert result["safety"] == {
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": False,
        "writes_enabled": False,
    }
    assert cache.calls == []


def test_dry_run_reports_benchmark_plan_without_refreshing_reference_data(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "benchmark-dry-run.sqlite3")
    store.init()
    cache = _BenchmarkCache(store)

    result = UniverseBackfillService(
        provider=_Provider(["600000"]),
        cache_service=cache,
    ).run()

    assert cache.benchmark_calls == []
    assert result["reference_data"] == {
        "supported": True,
        "status": "planned",
        "symbols": ["SH000300", "SH000001"],
        "processed": 0,
        "success": 0,
        "error": 0,
        "errors": [],
    }


def test_apply_refreshes_reference_benchmarks_and_reports_them_separately(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "benchmark-apply.sqlite3")
    store.init()
    cache = _BenchmarkCache(store)

    result = UniverseBackfillService(
        provider=_Provider(["600000"]),
        cache_service=cache,
    ).run(apply=True, rate_limit_seconds=0)

    assert cache.benchmark_calls == [(["SH000300", "SH000001"], 500)]
    assert result["reference_data"] == {
        "supported": True,
        "status": "completed",
        "symbols": ["SH000300", "SH000001"],
        "processed": 2,
        "success": 2,
        "error": 0,
        "errors": [],
    }
    assert result["processed"] == 1
    assert result["success"] == 1
    assert result["error"] == 0


def test_reference_failure_downgrades_status_without_changing_stock_counts(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "benchmark-partial.sqlite3")
    store.init()
    cache = _BenchmarkCache(
        store,
        benchmark_response={
            "status": "partial",
            "processed": 2,
            "results": [
                {"symbol": "SH000300", "status": "success"},
                {"symbol": "SH000001", "status": "error", "error": "source timeout"},
            ],
        },
    )

    result = UniverseBackfillService(
        provider=_Provider(["600000"]),
        cache_service=cache,
    ).run(apply=True, rate_limit_seconds=0)

    assert result["status"] == "partial"
    assert result["processed"] == 1
    assert result["success"] == 1
    assert result["error"] == 0
    assert result["errors"] == []
    assert result["reference_data"] == {
        "supported": True,
        "status": "partial",
        "symbols": ["SH000300", "SH000001"],
        "processed": 2,
        "success": 1,
        "error": 1,
        "errors": [{"symbol": "SH000001", "error": "source timeout"}],
    }


def test_apply_refreshes_in_bounded_batches_and_reports_symbol_results(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "apply.sqlite3")
    store.init()
    codes = [f"{600000 + index:06d}" for index in range(205)]
    cache = _ResultCache(store, error_symbol="SH600100")
    sleeps: list[float] = []

    result = UniverseBackfillService(
        provider=_Provider(codes),
        cache_service=cache,
        sleep_fn=sleeps.append,
    ).run(apply=True, days=400, batch_size=999, rate_limit_seconds=0.25)

    assert [len(symbols) for symbols, _ in cache.calls] == [200, 5]
    assert {days for _, days in cache.calls} == {400}
    assert sleeps == [0.25]
    assert result["processed"] == 205
    assert result["success"] == 204
    assert result["error"] == 1
    assert result["last_processed_symbol"] == "SH600204"
    assert result["status"] == "partial"
    assert result["reference_data"]["status"] == "unsupported"


def test_apply_passes_tencent_first_policy_through_batches_and_checkpoint(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "source-policy.sqlite3")
    store.init()
    cache = _PolicyRecordingCache(store)
    checkpoint = tmp_path / "source-policy.json"

    result = UniverseBackfillService(
        provider=_Provider(["600000", "600001", "600002"]),
        cache_service=cache,
    ).run(
        apply=True,
        batch_size=2,
        rate_limit_seconds=0,
        source_policy="tencent_first",
        max_workers=10,
        checkpoint_path=checkpoint,
    )

    assert cache.policies == ["tencent_first", "tencent_first"]
    assert cache.worker_limits == [10, 10]
    assert result["source_policy"] == "tencent_first"
    assert result["max_workers"] == 10
    assert json.loads(checkpoint.read_text(encoding="utf-8"))["source_policy"] == (
        "tencent_first"
    )
    assert json.loads(checkpoint.read_text(encoding="utf-8"))["max_workers"] == 10


def test_apply_reports_non_qfq_symbols_as_isolated_not_success(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "isolation-summary.sqlite3")
    store.init()

    result = UniverseBackfillService(
        provider=_Provider(["600000", "920000"]),
        cache_service=_IsolationCache(store),
    ).run(apply=True, rate_limit_seconds=0)

    assert result["processed"] == 2
    assert result["success"] == 1
    assert result["isolated"] == 1
    assert result["error"] == 0
    assert result["status"] == "partial"
    assert result["isolated_results"] == [
        {
            "symbol": "BJ920000",
            "status": "isolated_non_qfq",
            "adjustment_mode": "none",
        }
    ]


def test_resume_after_and_limit_create_a_deterministic_continuation(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "resume.sqlite3")
    store.init()
    cache = _ResultCache(store)
    service = UniverseBackfillService(
        provider=_Provider(["600004", "600001", "600003", "600000", "600002"]),
        cache_service=cache,
    )

    plan = service.plan(resume_after="600001", limit=2)
    result = service.run(apply=True, resume_after="SH600001", limit=2, rate_limit_seconds=0)

    assert plan.universe_count == 5
    assert plan.symbols == ("SH600002", "SH600003")
    assert result["universe_count"] == 5
    assert result["planned"] == 2
    assert result["processed"] == 2
    assert cache.calls == [(["SH600002", "SH600003"], 500)]
    assert result["last_processed_symbol"] == "SH600003"


def test_apply_writes_atomic_batch_checkpoint_for_process_resume(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "checkpoint.sqlite3")
    store.init()
    checkpoint = tmp_path / "logs" / "backfill.json"

    result = UniverseBackfillService(
        provider=_Provider(["600000", "600001", "600002"]),
        cache_service=_ResultCache(store),
    ).run(
        apply=True,
        batch_size=2,
        rate_limit_seconds=0,
        checkpoint_path=checkpoint,
    )

    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "universe_backfill_checkpoint.v2"
    assert payload["checkpoint_kind"] == "run_state"
    assert payload["last_processed_symbol"] == "SH600002"
    assert payload["processed"] == 3
    assert payload["status"] == result["status"]
    assert payload["universe_hash"] == result["universe_hash"]
    assert payload["days"] == 500
    assert payload["error_symbols"] == []
    assert payload["isolated_symbols"] == []
    assert payload["pending_gap_count"] == 0
    assert payload["pending_error_count"] == 0
    assert payload["pending_isolated_count"] == 0
    assert payload["universe_symbols"] == [
        "SH600000",
        "SH600001",
        "SH600002",
    ]
    assert result["checkpoint"]["granularity"] == "batch"


def test_resume_blocks_before_refresh_when_universe_hash_changed(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "universe-hash.sqlite3")
    store.init()
    cache = _ResultCache(store)

    result = UniverseBackfillService(
        provider=_Provider(["600000", "600001"]),
        cache_service=cache,
    ).run(
        apply=True,
        expected_universe_hash="stale-universe-hash",
        rate_limit_seconds=0,
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "universe_hash_mismatch"
    assert result["expected_universe_hash"] == "stale-universe-hash"
    assert result["universe_hash"] != "stale-universe-hash"
    assert cache.calls == []


def test_retry_only_resume_keeps_the_completed_continuation_cursor(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "retry-cursor.sqlite3")
    store.init()
    cache = _ResultCache(store)
    checkpoint = tmp_path / "retry-cursor.json"
    provider = _Provider(["600000", "600001", "600002"])
    service = UniverseBackfillService(provider=provider, cache_service=cache)
    universe_hash = service._universe_hash(("SH600000", "SH600001", "SH600002"))

    first = service.run(
        apply=True,
        resume_after="SH600002",
        retry_symbols=["SH600000"],
        expected_universe_hash=universe_hash,
        rate_limit_seconds=0,
        checkpoint_path=checkpoint,
    )

    assert cache.calls == [(["SH600000"], 500)]
    assert first["last_processed_symbol"] == "SH600002"
    assert first["last_attempted_symbol"] == "SH600000"
    assert first["retry_last_attempted"] == "SH600000"
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert payload["last_processed_symbol"] == "SH600002"
    assert payload["last_attempted_symbol"] == "SH600000"

    cache.calls.clear()
    second = service.run(
        apply=True,
        resume_after=payload["last_processed_symbol"],
        retry_symbols=payload["error_symbols"],
        expected_universe_hash=payload["universe_hash"],
        rate_limit_seconds=0,
    )

    assert second["planned"] == 0
    assert cache.calls == []


def test_retry_quality_gaps_selects_only_current_non_qfq_or_error_symbols(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "retry-quality-gaps.sqlite3")
    store.init()
    with store.connect() as connection:
        connection.executemany(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, close, source, adjustment_mode, quality_status
            ) VALUES (?, ?, ?, 'fixture', ?, ?)
            """,
            [
                ("SH600000", "2026-07-14", 10.0, "none", "review_only_unadjusted"),
                ("SH600001", "ERROR", None, "unknown", "error"),
                ("SH600002", "2026-07-14", 12.0, "qfq", "ready"),
                ("SZ000004", "2026-07-14", 8.0, "none", "review_only_unadjusted"),
            ],
        )
    cache = _ResultCache(store)

    result = UniverseBackfillService(
        provider=_Provider(["600000", "600001", "600002"]),
        cache_service=cache,
    ).run(
        apply=True,
        resume_after="SH600002",
        retry_quality_gaps=True,
        rate_limit_seconds=0,
    )

    assert cache.calls == [(["SH600000", "SH600001"], 500)]
    assert result["retry_planned"] == 2
    assert result["last_processed_symbol"] == "SH600002"


def test_failed_retry_remains_retryable_without_moving_the_main_cursor(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "failed-retry.sqlite3")
    store.init()
    cache = _ResultCache(store, error_symbol="SH600000")
    checkpoint = tmp_path / "failed-retry.json"
    service = UniverseBackfillService(
        provider=_Provider(["600000", "600001"]),
        cache_service=cache,
    )
    universe_hash = service._universe_hash(("SH600000", "SH600001"))

    first = service.run(
        apply=True,
        resume_after="SH600001",
        retry_symbols=["SH600000"],
        expected_universe_hash=universe_hash,
        rate_limit_seconds=0,
        checkpoint_path=checkpoint,
    )
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))

    assert first["planned"] == 1
    assert first["last_processed_symbol"] == "SH600001"
    assert payload["error_symbols"] == ["SH600000"]

    second = service.run(
        apply=True,
        resume_after=payload["last_processed_symbol"],
        retry_symbols=payload["error_symbols"],
        expected_universe_hash=payload["universe_hash"],
        rate_limit_seconds=0,
    )

    assert second["planned"] == 1
    assert second["last_processed_symbol"] == "SH600001"
    assert second["errors"] == [
        {"symbol": "SH600000", "error": "refresh result missing"}
    ]


def test_noop_resume_writes_manifest_without_erasing_retry_checkpoint(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "noop-manifest.sqlite3")
    store.init()
    with store.connect() as connection:
        connection.execute(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, close, source, adjustment_mode, quality_status
            ) VALUES (
                'SH600000', '2026-07-14', 10, 'fixture',
                'none', 'review_only_unadjusted'
            )
            """
        )
    checkpoint = tmp_path / "retry-checkpoint.json"
    checkpoint_payload = {
        "schema_version": "universe_backfill_checkpoint.v2",
        "last_processed_symbol": "SH600001",
        "error_symbols": ["SH600000"],
        "isolated_symbols": [],
    }
    checkpoint.write_text(json.dumps(checkpoint_payload), encoding="utf-8")
    before = checkpoint.read_bytes()
    manifest = tmp_path / "current-universe.json"

    result = UniverseBackfillService(
        provider=_Provider(["600000", "600001"]),
        cache_service=_ResultCache(store),
    ).run(
        apply=True,
        resume_after="SH600001",
        rate_limit_seconds=0,
        checkpoint_path=checkpoint,
        manifest_path=manifest,
    )

    assert result["planned"] == 0
    assert result["status"] == "partial"
    assert result["unresolved_quality_gap_symbols"] == ["SH600000"]
    assert result["checkpoint_preserved"] is True
    assert checkpoint.read_bytes() == before
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "a_share_universe_manifest.v1"
    assert payload["universe_symbols"] == ["SH600000", "SH600001"]
    assert payload["quality_gap_symbols"] == ["SH600000"]


def test_existing_cache_is_not_reported_as_success_when_remote_refresh_fails(
    monkeypatch,
    tmp_path,
) -> None:
    store = SQLiteStore(tmp_path / "degraded-cache.sqlite3")
    store.init()
    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, source, quality_status
            ) VALUES ('SH600000', '2026-07-01', 10, 10.2, 9.8, 10.1, 'old', 'ready')
            """
        )
    service = DailyBarCacheService(store=store)

    def fail(*_: object, **__: object):
        raise RuntimeError("remote unavailable")

    monkeypatch.setattr(service.builder.provider, "get_daily_bars", fail)
    monkeypatch.setattr(service, "_load_tencent_qfq_daily_bars", fail)

    result = service.refresh_symbols(["SH600000"], days=30)

    item = result["results"][0]
    assert item["status"] == "degraded_cached"
    assert item["bars_saved"] == 0
    assert item["latest_trade_date"] == "2026-07-01"
    assert item["error"] == "remote_refresh_failed_existing_cache_preserved"


def test_tencent_first_policy_skips_slow_akshare_and_supports_beijing_symbols(
    monkeypatch,
    tmp_path,
) -> None:
    store = SQLiteStore(tmp_path / "tencent-first.sqlite3")
    store.init()
    service = DailyBarCacheService(store=store)

    def tencent_history(symbol: str, **_kwargs) -> pd.DataFrame:
        assert symbol == "BJ920000"
        frame = pd.DataFrame(
            [
                {
                    "date": "2026-07-14",
                    "open": 10.0,
                    "close": 10.2,
                    "high": 10.3,
                    "low": 9.9,
                    "volume": 1000,
                    "amount": None,
                }
            ]
        )
        frame.attrs["adjustment_mode"] = "qfq"
        return frame

    monkeypatch.setattr(service, "_load_tencent_qfq_daily_bars", tencent_history)
    monkeypatch.setattr(
        service.builder.provider,
        "get_daily_bars",
        lambda *_: (_ for _ in ()).throw(AssertionError("AKShare should not be called")),
    )

    result = service.refresh_symbols(
        ["BJ920000"],
        days=30,
        source_policy="tencent_first",
    )

    item = result["results"][0]
    assert item["status"] == "success"
    assert item["source"] == "tencent.fqkline.qfq"
    assert item["attempts"] == [
        {"source": "tencent.fqkline.qfq", "status": "success"}
    ]
    row = store.fetch_one(
        """
        SELECT symbol, adjustment_mode, volume_unit, amount
        FROM daily_bar_cache
        WHERE symbol = 'BJ920000' AND trade_date = '2026-07-14'
        """
    )
    assert row == {
        "symbol": "BJ920000",
        "adjustment_mode": "qfq",
        "volume_unit": "hand",
        "amount": None,
    }


def test_tencent_only_policy_is_bounded_and_preserves_existing_cache(
    monkeypatch,
    tmp_path,
) -> None:
    store = SQLiteStore(tmp_path / "tencent-only.sqlite3")
    store.init()
    with store.connect() as connection:
        connection.execute(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume,
                source, adjustment_mode, volume_unit, quality_status
            ) VALUES (
                'SH600000', '2026-07-15', 10, 10.2, 9.8, 10.1, 1000,
                'fixture.qfq', 'qfq', 'hand', 'ready'
            )
            """
        )
    service = DailyBarCacheService(store=store)
    monkeypatch.setattr(
        service,
        "_load_tencent_qfq_daily_bars",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("tencent unavailable")
        ),
    )
    monkeypatch.setattr(
        service.builder.provider,
        "get_daily_bars",
        lambda *_: (_ for _ in ()).throw(AssertionError("AKShare must remain bounded out")),
    )

    result = service.refresh_symbols(
        ["SH600000"],
        days=120,
        source_policy="tencent_only",
    )

    item = result["results"][0]
    assert item["status"] == "degraded_cached"
    assert item["latest_trade_date"] == "2026-07-15"
    assert [attempt["source"] for attempt in item["attempts"]] == [
        "tencent.fqkline.qfq",
        "sina.cn.kline_daily_fallback",
        "local_cache",
    ]


def test_tencent_raw_day_fallback_is_provenanced_and_isolated_from_qfq(
    monkeypatch,
    tmp_path,
) -> None:
    store = SQLiteStore(tmp_path / "tencent-raw-day.sqlite3")
    store.init()
    service = DailyBarCacheService(store=store)

    frame = pd.DataFrame(
        [
            {
                "date": "2026-07-15",
                "open": 11.48,
                "close": 11.62,
                "high": 11.91,
                "low": 11.27,
                "volume": 8180,
                "amount": None,
            }
        ]
    )
    frame.attrs["adjustment_mode"] = "none"
    monkeypatch.setattr(
        service,
        "_load_tencent_qfq_daily_bars",
        lambda *_args, **_kwargs: frame,
    )
    monkeypatch.setattr(
        service.builder.provider,
        "get_daily_bars",
        lambda *_: (_ for _ in ()).throw(RuntimeError("AKShare unavailable")),
    )

    result = service.refresh_symbols(
        ["BJ920000"],
        days=30,
        source_policy="tencent_first",
    )

    item = result["results"][0]
    assert item["status"] == "isolated_non_qfq"
    assert item["adjustment_mode"] == "none"
    row = store.fetch_one(
        """
        SELECT adjustment_mode, quality_status
        FROM daily_bar_cache
        WHERE symbol = 'BJ920000' AND trade_date = '2026-07-15'
        """
    )
    assert row == {
        "adjustment_mode": "none",
        "quality_status": "review_only_unadjusted",
    }


def test_tencent_only_uses_newfqkline_qfq_when_primary_returns_raw(
    monkeypatch,
    tmp_path,
) -> None:
    store = SQLiteStore(tmp_path / "tencent-newfqkline.sqlite3")
    store.init()
    service = DailyBarCacheService(store=store)
    calls: list[str] = []

    class _Response:
        def __init__(self, body: str) -> None:
            self._body = body.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return self._body

    def fake_urlopen(request, *, timeout: int):
        assert timeout == 20
        calls.append(request.full_url)
        if "/appstock/app/fqkline/get?" in request.full_url:
            return _Response(
                json.dumps(
                    {
                        "code": 0,
                        "data": {
                            "bj920000": {
                                "day": [
                                    [
                                        "2026-07-14",
                                        "99.00",
                                        "99.50",
                                        "100.00",
                                        "98.00",
                                        "8180",
                                    ]
                                ]
                            }
                        },
                    }
                )
            )
        if "/appstock/app/newfqkline/get?" in request.full_url:
            payload = {
                "code": 0,
                "data": {
                    "bj920000": {
                        "qfqday": [
                            [
                                "2026-07-14",
                                "11.48",
                                "11.62",
                                "11.91",
                                "11.27",
                                "8180",
                            ]
                        ]
                    }
                },
            }
            return _Response(f"kline_dayqfq={json.dumps(payload)}")
        raise AssertionError(f"unexpected URL: {request.full_url}")

    monkeypatch.setattr("app.data.daily_bar_cache.urlopen", fake_urlopen)
    monkeypatch.setattr(
        service.builder.provider,
        "get_daily_bars",
        lambda *_: (_ for _ in ()).throw(AssertionError("AKShare must stay out")),
    )

    result = service.refresh_symbols(
        ["BJ920000"],
        days=30,
        source_policy="tencent_only",
    )

    item = result["results"][0]
    assert item["status"] == "success"
    assert item["adjustment_mode"] == "qfq"
    assert item["source"] == "tencent.newfqkline.qfq"
    assert len(calls) == 2
    assert "/appstock/app/fqkline/get?" in calls[0]
    assert "/appstock/app/newfqkline/get?" in calls[1]
    row = store.fetch_one(
        """
        SELECT close, source, adjustment_mode, quality_status
        FROM daily_bar_cache
        WHERE symbol = 'BJ920000' AND trade_date = '2026-07-14'
        """
    )
    assert row == {
        "close": 11.62,
        "source": "tencent.newfqkline.qfq",
        "adjustment_mode": "qfq",
        "quality_status": "ready",
    }


@pytest.mark.parametrize("primary_failure", ["network_error", "provider_error"])
def test_tencent_only_uses_newfqkline_qfq_when_primary_fails(
    monkeypatch,
    tmp_path,
    primary_failure: str,
) -> None:
    store = SQLiteStore(tmp_path / "tencent-newfqkline-network-fallback.sqlite3")
    store.init()
    service = DailyBarCacheService(store=store)
    calls: list[str] = []

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            payload = {
                "code": 0,
                "data": {
                    "sh600000": {
                        "qfqday": [
                            [
                                "2026-07-14",
                                "8.40",
                                "8.50",
                                "8.55",
                                "8.35",
                                "1000",
                            ]
                        ]
                    }
                },
            }
            return f"kline_dayqfq={json.dumps(payload)}".encode()

    class _ProviderErrorResponse(_Response):
        def read(self) -> bytes:
            return json.dumps({"code": 5, "msg": "primary rejected"}).encode()

    def fake_urlopen(request, *, timeout: int):
        assert timeout == 20
        calls.append(request.full_url)
        if "/appstock/app/fqkline/get?" in request.full_url:
            if primary_failure == "network_error":
                raise OSError("primary endpoint reset")
            return _ProviderErrorResponse()
        if "/appstock/app/newfqkline/get?" in request.full_url:
            return _Response()
        raise AssertionError(f"unexpected URL: {request.full_url}")

    monkeypatch.setattr("app.data.daily_bar_cache.urlopen", fake_urlopen)

    result = service.refresh_symbols(
        ["SH600000"],
        days=30,
        source_policy="tencent_only",
    )

    item = result["results"][0]
    assert item["status"] == "success"
    assert item["adjustment_mode"] == "qfq"
    assert len(calls) == 2
    assert "/appstock/app/newfqkline/get?" in calls[1]


def test_tencent_raw_day_is_deferred_until_akshare_qfq_is_attempted(
    monkeypatch,
    tmp_path,
) -> None:
    store = SQLiteStore(tmp_path / "raw-then-akshare.sqlite3")
    store.init()
    service = DailyBarCacheService(store=store)
    raw = pd.DataFrame(
        [
            {
                "date": "2026-07-14",
                "open": 10.0,
                "close": 99.0,
                "high": 100.0,
                "low": 9.9,
                "volume": 1000,
                "amount": None,
            }
        ]
    )
    raw.attrs["adjustment_mode"] = "none"
    qfq = pd.DataFrame(
        [
            {
                "date": "2026-07-14",
                "open": 10.0,
                "close": 10.2,
                "high": 10.3,
                "low": 9.9,
                "volume": 1000,
                "amount": 10_200_000.0,
            }
        ]
    )
    monkeypatch.setattr(
        service,
        "_load_tencent_qfq_daily_bars",
        lambda *_args, **_kwargs: raw,
    )
    monkeypatch.setattr(service.builder.provider, "get_daily_bars", lambda _: qfq)

    result = service.refresh_symbols(["SH600000"], source_policy="tencent_first")

    item = result["results"][0]
    assert item["status"] == "success"
    assert item["source"] == "akshare.stock_zh_a_hist"
    assert item["attempts"] == [
        {
            "source": "tencent.fqkline.qfq",
            "status": "raw_only_deferred",
            "adjustment_mode": "none",
        },
        {"source": "akshare.stock_zh_a_hist", "status": "success"},
    ]
    row = store.fetch_one(
        """
        SELECT close, amount, source, adjustment_mode, quality_status
        FROM daily_bar_cache
        WHERE symbol = 'SH600000' AND trade_date = '2026-07-14'
        """
    )
    assert row == {
        "close": 10.2,
        "amount": 10_200_000.0,
        "source": "akshare.stock_zh_a_hist",
        "adjustment_mode": "qfq",
        "quality_status": "ready",
    }


def test_raw_day_refresh_cannot_downgrade_an_existing_ready_qfq_row(
    monkeypatch,
    tmp_path,
) -> None:
    store = SQLiteStore(tmp_path / "qfq-no-downgrade.sqlite3")
    store.init()
    service = DailyBarCacheService(store=store)
    qfq = pd.DataFrame(
        [
            {
                "date": "2026-07-14",
                "open": 10.0,
                "close": 10.2,
                "high": 10.3,
                "low": 9.9,
                "volume": 1000,
                "amount": None,
            }
        ]
    )
    qfq.attrs["adjustment_mode"] = "qfq"
    raw = qfq.copy()
    raw.loc[0, "close"] = 99.0
    raw.attrs["adjustment_mode"] = "none"
    responses = iter((qfq, raw))
    monkeypatch.setattr(
        service,
        "_load_tencent_qfq_daily_bars",
        lambda *_args, **_kwargs: next(responses),
    )
    monkeypatch.setattr(
        service.builder.provider,
        "get_daily_bars",
        lambda *_: (_ for _ in ()).throw(RuntimeError("AKShare unavailable")),
    )

    service.refresh_symbols(["SH600000"], source_policy="tencent_first")
    service.refresh_symbols(["SH600000"], source_policy="tencent_first")

    row = store.fetch_one(
        """
        SELECT close, adjustment_mode, quality_status
        FROM daily_bar_cache
        WHERE symbol = 'SH600000' AND trade_date = '2026-07-14'
        """
    )
    assert row == {
        "close": 10.2,
        "adjustment_mode": "qfq",
        "quality_status": "ready",
    }


def test_legacy_sina_stock_rows_are_quarantined_from_ready_history(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "legacy-sina.sqlite3")
    store.init()
    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, open, high, low, close, volume,
                source, quality_status
            ) VALUES (
                'SZ002842', '2026-07-14', 36.92, 38.88, 36.13, 38.23, 63735184,
                'sina.cn.kline_daily_fallback', 'ready'
            )
            """
        )

    store.init()

    row = store.fetch_one(
        """
        SELECT adjustment_mode, volume_unit, quality_status
        FROM daily_bar_cache
        WHERE symbol = 'SZ002842'
        """
    )
    assert row["adjustment_mode"] == "unknown"
    assert row["volume_unit"] == "share"
    assert row["quality_status"] == "review_only_unknown_adjustment"


def test_batch_failure_is_isolated_to_each_symbol_and_does_not_abort_the_run(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "failure-isolation.sqlite3")
    store.init()
    cache = _ExplodingCache(store, bad_symbol="SH600001")

    result = UniverseBackfillService(
        provider=_Provider(["600000", "600001", "600002"]),
        cache_service=cache,
    ).run(apply=True, batch_size=3, rate_limit_seconds=0)

    assert [symbols for symbols, _ in cache.calls] == [
        ["SH600000", "SH600001", "SH600002"],
        ["SH600000"],
        ["SH600001"],
        ["SH600002"],
    ]
    assert result["status"] == "partial"
    assert result["processed"] == 3
    assert result["success"] == 2
    assert result["error"] == 1
    assert result["errors"] == [{"symbol": "SH600001", "error": "symbol source failed"}]


def test_result_reports_bar_amount_and_latest_cross_section_coverage(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "coverage.sqlite3")
    store.init()
    rows = [
        ("SH600000", "2026-07-10", 10.0, 100.0),
        ("SH600000", "2026-07-11", 10.1, None),
        ("SZ000001", "2026-07-10", 11.0, 0.0),
        ("SZ000001", "2026-07-11", 11.2, 200.0),
        ("SH601000", "2026-07-12", 9.0, 300.0),  # outside this run's universe
    ]
    with store.connect() as conn:
        conn.executemany(
            """
            INSERT INTO daily_bar_cache
                (symbol, trade_date, close, amount, source,
                 adjustment_mode, quality_status)
            VALUES (?, ?, ?, ?, 'fixture', 'qfq', 'ready')
            """,
            rows,
        )

    result = UniverseBackfillService(
        provider=_Provider(["600000", "000001", "300750"]),
        cache_service=_RecordingCache(store),
    ).run()

    assert result["coverage"] == {
        "bar": {"symbols": 2, "universe": 3, "rows": 4, "pct": 66.67},
        "amount": {"complete_rows": 2, "total_rows": 4, "pct": 50.0},
        "latest_cross_section": {
            "trade_date": "2026-07-11",
            "symbols": 2,
            "universe": 3,
            "pct": 66.67,
        },
    }


def test_cli_defaults_to_dry_run_and_requires_an_explicit_apply_flag(capsys) -> None:
    class _Runner:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] = {}

        def run(self, **kwargs: object) -> dict[str, object]:
            self.kwargs = kwargs
            return {
                "status": "completed" if kwargs["apply"] else "planned",
                "mode": "apply" if kwargs["apply"] else "dry_run",
                "planned": 3,
            }

    runner = _Runner()

    exit_code = main(
        ["--days", "300", "--batch-size", "50", "--rate-limit-seconds", "0.2"],
        service=runner,
    )

    assert exit_code == 0
    assert runner.kwargs == {
        "apply": False,
        "days": 300,
        "batch_size": 50,
        "rate_limit_seconds": 0.2,
        # None, not a literal: the CLI defers to DAILY_BAR_SOURCE_POLICY so a
        # full-market backfill cannot default to a source without 成交额.
        "source_policy": None,
        "max_workers": 5,
        "resume_after": None,
        "retry_symbols": [],
        "retry_quality_gaps": False,
        "expected_universe_hash": None,
        "limit": None,
        "checkpoint_path": str(DEFAULT_CHECKPOINT_PATH),
        "manifest_path": str(DEFAULT_MANIFEST_PATH),
    }
    assert '"mode": "dry_run"' in capsys.readouterr().out


def test_cli_returns_nonzero_for_partial_or_blocked_business_status() -> None:
    class _Runner:
        def __init__(self, status: str) -> None:
            self.status = status

        def run(self, **_: object) -> dict[str, object]:
            return {"status": self.status, "mode": "apply"}

    assert main(["--apply"], service=_Runner("partial")) == 2
    assert main(["--apply"], service=_Runner("blocked")) == 2
    assert main(["--apply"], service=_Runner("error")) == 1


def test_cli_can_resume_from_persisted_checkpoint(tmp_path) -> None:
    checkpoint = tmp_path / "resume.json"
    checkpoint.write_text(
        json.dumps(
            {
                "last_processed_symbol": "SH600123",
                "checkpoint_kind": "resume_state",
                "universe_hash": "stable-hash",
                "error_symbols": ["SH600100"],
                "isolated_symbols": ["SZ301292"],
            }
        ),
        encoding="utf-8",
    )

    class _Runner:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] = {}

        def run(self, **kwargs: object) -> dict[str, object]:
            self.kwargs = kwargs
            return {"status": "planned", "mode": "dry_run"}

    runner = _Runner()
    exit_code = main(
        ["--resume-from-checkpoint", "--checkpoint-path", str(checkpoint)],
        service=runner,
    )

    assert exit_code == 0
    assert runner.kwargs["resume_after"] == "SH600123"
    assert runner.kwargs["expected_universe_hash"] == "stable-hash"
    assert runner.kwargs["retry_symbols"] == ["SH600100", "SZ301292"]
    assert runner.kwargs["checkpoint_path"] == str(checkpoint)


def test_universe_discovery_failure_returns_the_same_safe_summary_shape() -> None:
    class _FailingProvider:
        def get_a_share_spot(self) -> pd.DataFrame:
            raise RuntimeError("spot provider unavailable")

    result = UniverseBackfillService(
        provider=_FailingProvider(),
        cache_service=_NoWriteCache(),
    ).run()

    assert result["status"] == "error"
    assert result["mode"] == "dry_run"
    assert result["universe_count"] == 0
    assert result["planned"] == 0
    assert result["processed"] == 0
    assert result["success"] == 0
    assert result["error"] == 0
    assert result["errors"][0]["stage"] == "universe_discovery"
    assert "spot provider unavailable" in result["errors"][0]["error"]
    assert result["discovery"]["status"] == "error"
    assert result["discovery"]["complete"] is False
    assert [item["status"] for item in result["discovery"]["attempts"]] == [
        "error",
        "unsupported",
        "empty",
    ]
    assert result["safety"]["writes_enabled"] is False


def test_apply_is_blocked_when_live_trading_is_enabled(monkeypatch, tmp_path) -> None:
    store = SQLiteStore(tmp_path / "live-block.sqlite3")
    store.init()
    cache = _RecordingCache(store)
    monkeypatch.setattr(settings, "enable_live_trading", True)

    result = UniverseBackfillService(
        provider=_Provider(["600000"]),
        cache_service=cache,
    ).run(apply=True)

    assert result["status"] == "blocked"
    assert result["errors"] == [{"stage": "safety", "error": "live_trading_enabled"}]
    assert result["safety"]["live_trading_enabled"] is True
    assert cache.calls == []
