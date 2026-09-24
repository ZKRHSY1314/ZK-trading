from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.backtest.engine import BacktestEngine  # noqa: E402
from app.config import settings  # noqa: E402
from app.storage.sqlite_store import SQLiteStore  # noqa: E402


def _load_json(raw: Any, default: Any) -> Any:
    if raw in (None, ""):
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except json.JSONDecodeError:
        return default


def _table_count(store: SQLiteStore, table: str) -> int:
    row = store.fetch_one(f"SELECT COUNT(*) AS count FROM {table}") or {}
    return int(row.get("count") or 0)


def _latest_historical_run(store: SQLiteStore) -> dict[str, Any] | None:
    row = store.fetch_one("SELECT * FROM historical_backtest_runs ORDER BY id DESC LIMIT 1")
    if not row:
        return None
    item = dict(row)
    item["metrics"] = _load_json(item.pop("metrics_json", "{}"), {})
    item["benchmark"] = _load_json(item.pop("benchmark_json", "{}"), {})
    item["execution_warnings"] = _load_json(item.pop("execution_warnings_json", "[]"), [])
    return item


def _latest_offhour_backtest(store: SQLiteStore) -> dict[str, Any]:
    row = store.fetch_one(
        """
        SELECT id, backtest_json, created_at, completed_at
        FROM offhour_research_runs
        ORDER BY id DESC
        LIMIT 1
        """
    )
    if not row:
        return {}
    payload = _load_json(row.get("backtest_json"), {})
    payload["offhour_run_id"] = row.get("id")
    payload["offhour_created_at"] = row.get("created_at")
    payload["offhour_completed_at"] = row.get("completed_at")
    return payload


def _historical_trade_symbols(store: SQLiteStore, run_id: int | None) -> list[str]:
    if not run_id:
        return []
    rows = store.fetch_all(
        """
        SELECT symbol, COUNT(*) AS count
        FROM historical_backtest_trades
        WHERE run_id = ?
        GROUP BY symbol
        ORDER BY count DESC, symbol ASC
        """,
        (run_id,),
    )
    return [str(row["symbol"]) for row in rows if row.get("symbol")]


def _daily_cache_symbols(store: SQLiteStore, limit: int) -> list[str]:
    rows = store.fetch_all(
        """
        SELECT symbol, COUNT(*) AS bar_count, MAX(trade_date) AS latest_trade_date
        FROM daily_bar_cache
        WHERE quality_status = 'ready'
          AND trade_date != 'ERROR'
          AND symbol NOT LIKE 'SH000%'
          AND symbol NOT LIKE 'SZ399%'
        GROUP BY symbol
        HAVING bar_count >= 3
        ORDER BY latest_trade_date DESC, bar_count DESC, symbol ASC
        LIMIT ?
        """,
        (max(1, int(limit)),),
    )
    return [str(row["symbol"]) for row in rows if row.get("symbol")]


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _cache_window(
    store: SQLiteStore,
    *,
    symbols: list[str],
    benchmark_symbol: str,
) -> dict[str, Any]:
    requested = [symbol for symbol in [*symbols, benchmark_symbol] if symbol]
    if not requested:
        return {
            "status": "no_symbols",
            "latest_common_trade_date": None,
            "max_latest_trade_date": None,
            "missing_symbols": [],
            "symbol_count": 0,
            "symbols": [],
        }

    placeholders = ",".join("?" for _ in requested)
    rows = store.fetch_all(
        f"""
        SELECT symbol,
               COUNT(*) AS bar_count,
               MIN(trade_date) AS first_trade_date,
               MAX(trade_date) AS latest_trade_date
        FROM daily_bar_cache
        WHERE symbol IN ({placeholders})
          AND trade_date != 'ERROR'
          AND quality_status = 'ready'
        GROUP BY symbol
        ORDER BY symbol ASC
        """,
        tuple(requested),
    )
    by_symbol = {str(row["symbol"]): dict(row) for row in rows if row.get("symbol")}
    missing = sorted(set(requested) - set(by_symbol))
    latest_dates = [
        str(item["latest_trade_date"])
        for item in by_symbol.values()
        if item.get("latest_trade_date")
    ]
    latest_common = min(latest_dates) if len(latest_dates) == len(requested) else None
    max_latest = max(latest_dates) if latest_dates else None
    stale_symbols = [
        symbol
        for symbol, item in by_symbol.items()
        if max_latest and item.get("latest_trade_date") and item.get("latest_trade_date") < max_latest
    ]
    status = "ready" if latest_common else "missing_symbol_history"
    if latest_common and stale_symbols:
        status = "partial_latest_alignment"
    return {
        "status": status,
        "latest_common_trade_date": latest_common,
        "max_latest_trade_date": max_latest,
        "missing_symbols": missing,
        "stale_symbols": sorted(stale_symbols),
        "symbol_count": len(requested),
        "symbols": [
            {
                "symbol": symbol,
                "bar_count": int(item.get("bar_count") or 0),
                "first_trade_date": item.get("first_trade_date"),
                "latest_trade_date": item.get("latest_trade_date"),
            }
            for symbol, item in sorted(by_symbol.items())
        ],
    }


def _select_symbols(
    *,
    store: SQLiteStore,
    historical_run: dict[str, Any] | None,
    offhour_backtest: dict[str, Any],
    override_symbols: list[str] | None,
    fallback_limit: int,
) -> tuple[list[str], str]:
    if override_symbols:
        return override_symbols, "cli_override"

    offhour_symbols = [
        str(symbol)
        for symbol in offhour_backtest.get("symbols", [])
        if symbol
    ]
    if offhour_symbols:
        return offhour_symbols, f"offhour_research_runs:{offhour_backtest.get('offhour_run_id')}"

    historical_symbols = _historical_trade_symbols(
        store,
        int(historical_run["id"]) if historical_run and historical_run.get("id") else None,
    )
    if historical_symbols:
        return historical_symbols, f"historical_backtest_trades:{historical_run.get('id')}"

    return _daily_cache_symbols(store, fallback_limit), "daily_bar_cache_fallback"


def _diagnostic_reasons(result: dict[str, Any]) -> list[str]:
    metrics = result.get("metrics") or {}
    benchmark = result.get("benchmark") or {}
    warnings = result.get("execution_warnings") or []
    reasons: list[str] = []
    if result.get("status") != "completed":
        reasons.append(f"status_{result.get('status')}")
    if int(metrics.get("trade_count") or 0) == 0:
        reasons.append("zero_completed_trades")
    if int(metrics.get("rejected_by_risk_count") or 0) > 0:
        reasons.append("candidates_rejected_by_risk")
    if benchmark.get("status") != "ready" or "insufficient_benchmark_data" in warnings:
        reasons.append("insufficient_benchmark_data")
    return sorted(set(reasons))


def _counts(store: SQLiteStore) -> dict[str, int]:
    return {
        "historical_backtest_runs": _table_count(store, "historical_backtest_runs"),
        "historical_backtest_trades": _table_count(store, "historical_backtest_trades"),
        "historical_backtest_closed_trades": _table_count(store, "historical_backtest_closed_trades"),
        "historical_backtest_daily_equity": _table_count(store, "historical_backtest_daily_equity"),
    }


def build_preflight(
    *,
    persist_review_backtest: bool = False,
    symbols: list[str] | None = None,
    fallback_symbol_limit: int = 10,
    use_latest_cache_end_date: bool = False,
    store: SQLiteStore | None = None,
) -> dict[str, Any]:
    store = store or SQLiteStore(settings.database_path)
    historical_run = _latest_historical_run(store)
    offhour_backtest = _latest_offhour_backtest(store)
    if not historical_run and not offhour_backtest:
        raise RuntimeError("No historical_backtest_runs or offhour_research_runs backtest context found.")
    if settings.enable_live_trading:
        raise RuntimeError("Refusing V1 backtest preflight while live trading is enabled.")

    start_date = (
        (offhour_backtest.get("start_date") if offhour_backtest else None)
        or (historical_run or {}).get("start_date")
    )
    end_date = (
        (offhour_backtest.get("end_date") if offhour_backtest else None)
        or (historical_run or {}).get("end_date")
    )
    if not start_date or not end_date:
        raise RuntimeError("Cannot infer backtest start_date/end_date for V1 preflight.")

    selected_symbols, symbol_source = _select_symbols(
        store=store,
        historical_run=historical_run,
        offhour_backtest=offhour_backtest,
        override_symbols=symbols,
        fallback_limit=fallback_symbol_limit,
    )
    if not selected_symbols:
        raise RuntimeError("No ready symbols available for V1 backtest preflight.")

    benchmark_symbol = settings.backtest_default_benchmark_symbol
    original_end_date = str(end_date)
    cache_window = _cache_window(
        store,
        symbols=selected_symbols,
        benchmark_symbol=benchmark_symbol,
    )
    latest_common_date = cache_window.get("latest_common_trade_date")
    if use_latest_cache_end_date and latest_common_date:
        parsed_start = _parse_date(start_date)
        parsed_latest = _parse_date(latest_common_date)
        if parsed_start and parsed_latest and parsed_latest >= parsed_start:
            end_date = latest_common_date

    before_counts = _counts(store)
    result = BacktestEngine().run(
        start_date=str(start_date),
        end_date=str(end_date),
        symbols=selected_symbols,
        initial_cash=100000.0,
        max_positions=min(5, max(1, len(selected_symbols))),
        per_symbol_cap=0.2,
        benchmark_symbol=benchmark_symbol,
        persist=persist_review_backtest,
    )
    after_counts = _counts(store)
    reasons = _diagnostic_reasons(result)
    benchmark_ready = (result.get("benchmark") or {}).get("status") == "ready"
    cache_max_latest_date = cache_window.get("max_latest_trade_date")
    cache_has_newer_data = bool(cache_max_latest_date and str(end_date) < str(cache_max_latest_date))
    cache_has_stale_symbols = bool(cache_window.get("stale_symbols"))
    backtest_window_current = not (cache_has_newer_data or cache_has_stale_symbols)
    safe_to_persist_review_backtest = (
        not settings.enable_live_trading
        and bool(result.get("simulation_only"))
        and result.get("status") == "completed"
        and benchmark_ready
    )

    return {
        "schema_version": "v1_backtest_preflight.v1",
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": settings.enable_live_trading,
        "persist_requested": persist_review_backtest,
        "writes_database": persist_review_backtest,
        "database_mutated": before_counts != after_counts,
        "cache_window": cache_window,
        "source_context": {
            "historical_backtest_run_id": (historical_run or {}).get("id"),
            "offhour_run_id": offhour_backtest.get("offhour_run_id"),
            "symbol_source": symbol_source,
        },
        "input": {
            "start_date": start_date,
            "end_date": end_date,
            "original_end_date": original_end_date,
            "use_latest_cache_end_date": use_latest_cache_end_date,
            "symbols": selected_symbols,
            "symbol_count": len(selected_symbols),
            "initial_cash": 100000.0,
            "max_positions": min(5, max(1, len(selected_symbols))),
            "per_symbol_cap": 0.2,
            "benchmark_symbol": benchmark_symbol,
        },
        "result": {
            "run_id": result.get("run_id"),
            "status": result.get("status"),
            "days": result.get("days"),
            "trades": result.get("trades"),
            "closed_trades": result.get("closed_trades"),
            "metrics": result.get("metrics") or {},
            "benchmark": result.get("benchmark") or {},
            "execution_warnings": result.get("execution_warnings") or [],
            "diagnostic_reasons": reasons,
        },
        "gates": {
            "safe_to_persist_review_backtest": safe_to_persist_review_backtest,
            "benchmark_ready": benchmark_ready,
            "live_trading_disabled": not settings.enable_live_trading,
            "simulation_only_result": bool(result.get("simulation_only")),
            "backtest_window_current": backtest_window_current,
        },
        "database_counts": {
            "before": before_counts,
            "after": after_counts,
        },
        "next_action": (
            "refresh_stale_backtest_symbols_or_benchmark"
            if cache_has_newer_data and cache_has_stale_symbols
            else (
                "rerun_with_latest_cache_end_date"
                if latest_common_date
                and str(end_date) < str(latest_common_date)
                and not use_latest_cache_end_date
                else (
                    "persist_review_backtest_can_refresh_latest_review_window"
                    if safe_to_persist_review_backtest and not persist_review_backtest
                    else "review_remaining_backtest_diagnostic_reasons"
                )
            )
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V1 review-only backtest rerun preflight.")
    parser.add_argument(
        "--persist-review-backtest",
        action="store_true",
        help="Persist a review-only historical_backtest_runs row after the preflight passes local safety checks.",
    )
    parser.add_argument("--symbols", default="", help="Optional comma-separated symbols to preflight.")
    parser.add_argument("--fallback-symbol-limit", type=int, default=10)
    parser.add_argument(
        "--use-latest-cache-end-date",
        action="store_true",
        help="Use the latest common ready daily_bar_cache date across selected symbols and benchmark.",
    )
    args = parser.parse_args(argv)

    symbols = [item.strip() for item in args.symbols.split(",") if item.strip()] or None
    summary = build_preflight(
        persist_review_backtest=args.persist_review_backtest,
        symbols=symbols,
        fallback_symbol_limit=args.fallback_symbol_limit,
        use_latest_cache_end_date=args.use_latest_cache_end_date,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
