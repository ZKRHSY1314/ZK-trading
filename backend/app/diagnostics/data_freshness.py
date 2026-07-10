from __future__ import annotations

import json
from datetime import date
from typing import Any

from app.config import settings
from app.storage.sqlite_store import SQLiteStore


DEFAULT_MAX_LAG_DAYS = 7


class DataFreshnessDiagnosticsService:
    """Read-only preflight for stale cache and failed external discovery."""

    def __init__(self, store: SQLiteStore | None = None) -> None:
        self.store = store or SQLiteStore(settings.database_path)

    def report(
        self,
        *,
        max_lag_days: int = DEFAULT_MAX_LAG_DAYS,
        candidate_limit: int = 20,
    ) -> dict[str, Any]:
        return {
            "schema_version": "v1_data_freshness_diagnostics.v1",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
            "daily_bar_refresh_preflight": self.daily_bar_refresh_preflight(
                max_lag_days=max_lag_days,
                candidate_limit=candidate_limit,
            ),
            "discovery_recovery": self.discovery_recovery(),
        }

    def daily_bar_refresh_preflight(
        self,
        *,
        max_lag_days: int = DEFAULT_MAX_LAG_DAYS,
        candidate_limit: int = 20,
    ) -> dict[str, Any]:
        summary = self.store.fetch_one(
            """
            SELECT
                COUNT(*) AS row_count,
                COUNT(DISTINCT symbol) AS symbol_count,
                MAX(trade_date) AS latest_trade_date
            FROM daily_bar_cache
            WHERE quality_status = 'ready'
              AND trade_date != 'ERROR'
            """
        ) or {}
        latest_trade_date = summary.get("latest_trade_date")
        calendar_lag_days = self._calendar_lag_days(latest_trade_date)
        candidates = self._top_candidate_symbols(candidate_limit)
        coverage = self._candidate_coverage([item["symbol"] for item in candidates])

        stale_candidates: list[dict[str, Any]] = []
        missing_candidates: list[dict[str, Any]] = []
        for candidate in candidates:
            symbol = candidate["symbol"]
            item = dict(candidate)
            item.update(coverage.get(symbol, {}))
            item_lag = self._calendar_lag_days(item.get("latest_trade_date"))
            item["calendar_lag_days"] = item_lag
            if not coverage.get(symbol):
                missing_candidates.append(item)
            elif item_lag is not None and item_lag > max_lag_days:
                stale_candidates.append(item)

        stale_global = calendar_lag_days is not None and calendar_lag_days > max_lag_days
        refresh_recommended = bool(stale_global or stale_candidates or missing_candidates)
        status = "refresh_recommended" if refresh_recommended else "ready"
        return {
            "status": status,
            "max_lag_days": max_lag_days,
            "latest_trade_date": latest_trade_date,
            "calendar_lag_days": calendar_lag_days,
            "row_count": int(summary.get("row_count") or 0),
            "symbol_count": int(summary.get("symbol_count") or 0),
            "candidate_source": "candidate_scores_top",
            "candidate_count": len(candidates),
            "stale_candidate_count": len(stale_candidates),
            "missing_candidate_count": len(missing_candidates),
            "sample_stale_candidates": stale_candidates[:5],
            "sample_missing_candidates": missing_candidates[:5],
            "preflight_writes_database": False,
            "refresh_would_write_database": True,
            "requires_explicit_cache_mutation": True,
            "safe_to_refresh_review_cache": not settings.enable_live_trading,
            "recommended_api": f"POST /api/data/daily-bars/refresh?limit={max(1, min(candidate_limit, 200))}&days=120",
            "next_action": (
                "explicitly_run_daily_bar_cache_refresh_after_review"
                if refresh_recommended
                else "no_daily_bar_refresh_needed"
            ),
        }

    def discovery_recovery(self) -> dict[str, Any]:
        latest = self.store.fetch_one(
            """
            SELECT id, status, source, total_scanned, stored_count, scored_count,
                   errors_json, created_at, completed_at
            FROM potential_search_runs
            ORDER BY id DESC
            LIMIT 1
            """
        )
        candidate_scores = self._table_count("candidate_scores")
        lifecycle = self._table_count("candidate_lifecycle")
        auto_discovered = self._table_count("auto_discovered_candidates")
        if not latest:
            return {
                "status": "no_potential_search_run",
                "candidate_scores_available": candidate_scores,
                "lifecycle_candidates_available": lifecycle,
                "auto_discovered_candidates_available": auto_discovered,
                "preflight_writes_database": False,
                "retry_would_write_database": True,
                "safe_to_retry_review_discovery": not settings.enable_live_trading,
                "next_action": "run_potential_search_with_persist_false_first",
            }
        errors = self._json_loads(latest.get("errors_json"))
        external_errors = [item for item in errors if "discovery" in str(item).lower() or "remote end" in str(item).lower()]
        status = "external_source_failed" if external_errors else (
            "partial" if latest.get("status") != "completed" else "ready"
        )
        downstream_available = candidate_scores > 0 or lifecycle > 0
        return {
            "status": status,
            "latest_run_id": latest.get("id"),
            "latest_run_status": latest.get("status"),
            "source": latest.get("source"),
            "total_scanned": int(latest.get("total_scanned") or 0),
            "stored_count": int(latest.get("stored_count") or 0),
            "scored_count": int(latest.get("scored_count") or 0),
            "errors": errors,
            "external_error_count": len(external_errors),
            "candidate_scores_available": candidate_scores,
            "lifecycle_candidates_available": lifecycle,
            "auto_discovered_candidates_available": auto_discovered,
            "downstream_candidate_evidence_available": downstream_available,
            "preflight_writes_database": False,
            "retry_would_write_database": True,
            "safe_to_retry_review_discovery": not settings.enable_live_trading,
            "recommended_api": "POST /api/candidates/potential-search/run?limit=100&persist=false",
            "recommended_preflight_command": (
                "backend\\.venv\\Scripts\\python.exe backend\\scripts\\v1_discovery_retry_preflight.py --limit 100"
            ),
            "next_action": (
                "retry_discovery_persist_false_then_compare_downstream_candidates"
                if status != "ready"
                else "no_discovery_retry_needed"
            ),
            "created_at": latest.get("created_at"),
            "completed_at": latest.get("completed_at"),
        }

    def _top_candidate_symbols(self, limit: int) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT symbol, MAX(name) AS name, MAX(total_score) AS score
            FROM candidate_scores
            WHERE symbol NOT LIKE 'SH000%'
              AND symbol NOT LIKE 'SZ399%'
            GROUP BY symbol
            ORDER BY score DESC, symbol ASC
            LIMIT ?
            """,
            (max(1, min(int(limit), 200)),),
        )
        return [
            {
                "symbol": str(row["symbol"]),
                "name": row.get("name"),
                "score": row.get("score"),
            }
            for row in rows
            if row.get("symbol")
        ]

    def _candidate_coverage(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        if not symbols:
            return {}
        rows = self.store.fetch_all(
            f"""
            SELECT symbol, COUNT(*) AS bar_count, MIN(trade_date) AS first_trade_date,
                   MAX(trade_date) AS latest_trade_date
            FROM daily_bar_cache
            WHERE symbol IN ({",".join("?" for _ in symbols)})
              AND quality_status = 'ready'
              AND trade_date != 'ERROR'
            GROUP BY symbol
            """,
            tuple(symbols),
        )
        return {
            str(row["symbol"]): {
                "bar_count": int(row.get("bar_count") or 0),
                "first_trade_date": row.get("first_trade_date"),
                "latest_trade_date": row.get("latest_trade_date"),
            }
            for row in rows
        }

    def _table_count(self, table: str) -> int:
        row = self.store.fetch_one(f"SELECT COUNT(*) AS count FROM {table}") or {}
        return int(row.get("count") or 0)

    @staticmethod
    def _json_loads(value: Any) -> Any:
        if value in (None, ""):
            return []
        if isinstance(value, list):
            return value
        try:
            return json.loads(str(value))
        except Exception:
            return []

    @staticmethod
    def _calendar_lag_days(value: Any) -> int | None:
        if not value:
            return None
        try:
            parsed = date.fromisoformat(str(value)[:10])
        except ValueError:
            return None
        return (date.today() - parsed).days
