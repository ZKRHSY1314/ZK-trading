from __future__ import annotations

import pandas as pd

from app.config import settings
from app.data.universe_backfill import UniverseBackfillService
from app.storage.sqlite_store import SQLiteStore
from scripts.backfill_market_universe import main


class _Provider:
    def __init__(self, codes: list[object]) -> None:
        self.codes = codes

    def get_a_share_spot(self) -> pd.DataFrame:
        return pd.DataFrame({"代码": self.codes})


class _NoWriteCache:
    def refresh_symbols(self, symbols: list[str], days: int = 120) -> dict[str, object]:
        raise AssertionError("planning must not refresh the cache")


class _RecordingCache:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self.calls: list[tuple[list[str], int]] = []

    def refresh_symbols(self, symbols: list[str], days: int = 120) -> dict[str, object]:
        self.calls.append((symbols, days))
        return {"processed": len(symbols), "results": []}


class _ResultCache(_RecordingCache):
    def __init__(self, store: SQLiteStore, *, error_symbol: str | None = None) -> None:
        super().__init__(store)
        self.error_symbol = error_symbol

    def refresh_symbols(self, symbols: list[str], days: int = 120) -> dict[str, object]:
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

    def refresh_symbols(self, symbols: list[str], days: int = 120) -> dict[str, object]:
        self.calls.append((symbols, days))
        if len(symbols) > 1:
            raise RuntimeError("batch transport failed")
        if symbols[0] == self.bad_symbol:
            raise RuntimeError("symbol source failed")
        return {
            "processed": 1,
            "results": [{"symbol": symbols[0], "status": "success"}],
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


def test_plan_normalizes_and_filters_the_shanghai_shenzhen_a_share_universe() -> None:
    provider = _Provider(
        [
            "1",
            "SZ000001",
            "600000",
            "sh688001",
            "300750",
            "200001",  # Shenzhen B share
            "900901",  # Shanghai B share
            "430047",  # Beijing exchange
            None,
            "not-a-code",
        ]
    )

    plan = UniverseBackfillService(provider=provider, cache_service=_NoWriteCache()).plan()

    assert plan.universe_count == 4
    assert plan.symbols == ("SH600000", "SH688001", "SZ000001", "SZ300750")


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
                (symbol, trade_date, close, amount, source, quality_status)
            VALUES (?, ?, ?, ?, 'fixture', 'ready')
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
            return {"mode": "apply" if kwargs["apply"] else "dry_run", "planned": 3}

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
        "resume_after": None,
        "limit": None,
    }
    assert '"mode": "dry_run"' in capsys.readouterr().out


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
    assert result["errors"] == [
        {"stage": "universe_discovery", "error": "spot provider unavailable"}
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
