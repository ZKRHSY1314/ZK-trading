import importlib.util
import json
from pathlib import Path


def _load_preflight_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "v1_backtest_preflight.py"
    spec = importlib.util.spec_from_file_location("v1_backtest_preflight", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _insert_bar(conn, symbol: str, trade_date: str, close: float) -> None:
    conn.execute(
        """
        INSERT INTO daily_bar_cache(
            symbol, trade_date, open, high, low, close, volume, amount, source, quality_status
        )
        VALUES (?, ?, ?, ?, ?, ?, 10000, 1000000, 'fixture', 'ready')
        """,
        (symbol, trade_date, close, close + 0.2, close - 0.2, close),
    )


def _seed_preflight_context(test_db) -> None:
    with test_db.connect() as conn:
        for table in [
            "daily_bar_cache",
            "historical_backtest_runs",
            "historical_backtest_trades",
            "historical_backtest_closed_trades",
            "historical_backtest_daily_equity",
            "offhour_research_runs",
        ]:
            conn.execute(f"DELETE FROM {table}")
        for symbol, closes in {
            "SH000300": [100.0, 101.0, 102.0],
            "SH600000": [10.0, 10.2, 10.4],
            "SZ002081": [20.0, 20.2, 20.5],
        }.items():
            for index, close in enumerate(closes, start=1):
                _insert_bar(conn, symbol, f"2026-06-2{index}", close)
        conn.execute(
            """
            INSERT INTO historical_backtest_runs(
                config_json, data_source, start_date, end_date, status, benchmark_symbol,
                initial_cash, final_cash, metrics_json, benchmark_json, execution_warnings_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "{}",
                "daily_bar_cache",
                "2026-06-21",
                "2026-06-23",
                "completed",
                "SH000300",
                100000,
                100000,
                json.dumps({"trade_count": 0, "rejected_by_risk_count": 0}),
                json.dumps({"status": "insufficient_benchmark_data"}),
                json.dumps(["insufficient_benchmark_data"]),
            ),
        )
        conn.execute(
            """
            INSERT INTO offhour_research_runs(
                mode, status, backtest_json, summary_json, review_only, simulation_only,
                live_trading_enabled
            )
            VALUES (?, ?, ?, ?, 1, 1, 0)
            """,
            (
                "balanced_search_replay",
                "completed",
                json.dumps(
                    {
                        "symbols": ["SH600000", "SZ002081"],
                        "start_date": "2026-06-21",
                        "end_date": "2026-06-23",
                    }
                ),
                "{}",
            ),
        )


def test_v1_backtest_preflight_defaults_to_no_database_write(test_db):
    module = _load_preflight_module()
    _seed_preflight_context(test_db)

    summary = module.build_preflight(store=test_db)

    assert summary["review_only"] is True
    assert summary["simulation_only"] is True
    assert summary["persist_requested"] is False
    assert summary["writes_database"] is False
    assert summary["database_mutated"] is False
    assert summary["source_context"]["symbol_source"].startswith("offhour_research_runs:")
    assert summary["input"]["symbols"] == ["SH600000", "SZ002081"]
    assert summary["result"]["benchmark"]["status"] == "ready"
    assert "insufficient_benchmark_data" not in summary["result"]["diagnostic_reasons"]

    run_count = test_db.fetch_one("SELECT COUNT(*) AS count FROM historical_backtest_runs")["count"]
    assert run_count == 1


def test_v1_backtest_preflight_persists_only_with_explicit_flag(test_db):
    module = _load_preflight_module()
    _seed_preflight_context(test_db)

    summary = module.build_preflight(store=test_db, persist_review_backtest=True)

    assert summary["persist_requested"] is True
    assert summary["writes_database"] is True
    assert summary["database_mutated"] is True
    assert summary["result"]["run_id"] > 0
    assert summary["result"]["benchmark"]["status"] == "ready"
    run_count = test_db.fetch_one("SELECT COUNT(*) AS count FROM historical_backtest_runs")["count"]
    assert run_count == 2


def test_v1_backtest_preflight_uses_latest_cache_end_date_only_when_requested(test_db):
    module = _load_preflight_module()
    _seed_preflight_context(test_db)
    with test_db.connect() as conn:
        for symbol, close in {
            "SH000300": 103.0,
            "SH600000": 10.6,
            "SZ002081": 20.8,
        }.items():
            _insert_bar(conn, symbol, "2026-06-24", close)

    default_summary = module.build_preflight(store=test_db)
    latest_summary = module.build_preflight(store=test_db, use_latest_cache_end_date=True)

    assert default_summary["input"]["end_date"] == "2026-06-23"
    assert default_summary["input"]["original_end_date"] == "2026-06-23"
    assert default_summary["gates"]["backtest_window_current"] is False
    assert default_summary["next_action"] == "rerun_with_latest_cache_end_date"
    assert default_summary["database_mutated"] is False

    assert latest_summary["input"]["end_date"] == "2026-06-24"
    assert latest_summary["input"]["original_end_date"] == "2026-06-23"
    assert latest_summary["input"]["use_latest_cache_end_date"] is True
    assert latest_summary["gates"]["backtest_window_current"] is True
    assert latest_summary["database_mutated"] is False
