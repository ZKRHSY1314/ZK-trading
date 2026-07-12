from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

import pandas as pd

from app.config import settings
from app.data.akshare_provider import AkshareProvider, MarketDataProvider
from app.data.daily_bar_cache import DailyBarCacheService


class DailyBarRefresher(Protocol):
    def refresh_symbols(self, symbols: list[str], days: int = 120) -> dict[str, Any]: ...


@dataclass(frozen=True)
class UniverseBackfillPlan:
    observed_at: str
    symbols: tuple[str, ...]
    universe_count: int
    universe_symbols: tuple[str, ...]
    resume_after: str | None = None


class UniverseBackfillService:
    """Discover the Shanghai/Shenzhen A-share universe before refreshing bars."""

    REFERENCE_SYMBOLS = ("SH000300", "SH000001")

    def __init__(
        self,
        *,
        provider: MarketDataProvider | None = None,
        cache_service: DailyBarRefresher | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self.provider = provider or AkshareProvider()
        self.cache_service = cache_service or DailyBarCacheService()
        self.sleep_fn = sleep_fn

    def plan(
        self,
        *,
        resume_after: str | None = None,
        limit: int | None = None,
    ) -> UniverseBackfillPlan:
        spot = self.provider.get_a_share_spot()
        universe = tuple(sorted(self._extract_symbols(spot)))
        normalized_resume = None
        if resume_after:
            normalized_resume = self._normalize_symbol(resume_after)
            if normalized_resume is None:
                raise ValueError(f"unsupported resume symbol: {resume_after}")
        symbols = tuple(
            symbol for symbol in universe if normalized_resume is None or symbol > normalized_resume
        )
        if limit is not None:
            normalized_limit = int(limit)
            if normalized_limit < 1:
                raise ValueError("limit must be at least 1")
            symbols = symbols[:normalized_limit]
        return UniverseBackfillPlan(
            observed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            symbols=symbols,
            universe_count=len(universe),
            universe_symbols=universe,
            resume_after=normalized_resume,
        )

    def run(
        self,
        *,
        apply: bool = False,
        days: int = 500,
        batch_size: int = 200,
        rate_limit_seconds: float = 0.5,
        resume_after: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        if apply and settings.enable_live_trading:
            return {
                "status": "blocked",
                "mode": "apply",
                "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "universe_count": 0,
                "planned": 0,
                "resume_after": resume_after,
                "processed": 0,
                "success": 0,
                "error": 0,
                "last_processed_symbol": None,
                "errors": [{"stage": "safety", "error": "live_trading_enabled"}],
                "coverage": self._coverage(()),
                "reference_data": self._reference_data_plan(apply=True),
                "safety": self._safety(apply=True),
            }
        try:
            plan = self.plan(resume_after=resume_after, limit=limit)
        except Exception as exc:
            return {
                "status": "error",
                "mode": "apply" if apply else "dry_run",
                "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "universe_count": 0,
                "planned": 0,
                "resume_after": resume_after,
                "processed": 0,
                "success": 0,
                "error": 0,
                "last_processed_symbol": None,
                "errors": [{"stage": "universe_discovery", "error": str(exc)}],
                "coverage": self._coverage(()),
                "reference_data": self._reference_data_plan(apply=apply),
                "safety": self._safety(apply=apply),
            }
        days = max(1, min(int(days), 500))
        batch_size = max(1, min(int(batch_size), 200))
        rate_limit_seconds = max(0.0, float(rate_limit_seconds))
        result: dict[str, Any] = {
            "status": "planned" if not apply else "completed",
            "mode": "apply" if apply else "dry_run",
            "observed_at": plan.observed_at,
            "universe_count": plan.universe_count,
            "planned": len(plan.symbols),
            "resume_after": plan.resume_after,
            "processed": 0,
            "success": 0,
            "error": 0,
            "last_processed_symbol": None,
            "errors": [],
            "coverage": self._coverage(plan.universe_symbols),
            "reference_data": self._reference_data_plan(apply=apply),
            "safety": self._safety(apply=apply),
        }
        if not apply:
            return result

        batches = [
            list(plan.symbols[offset : offset + batch_size])
            for offset in range(0, len(plan.symbols), batch_size)
        ]
        for index, symbols in enumerate(batches):
            items = self._refresh_with_isolation(symbols, days=days)
            by_symbol = {
                str(item.get("symbol")): item
                for item in items
                if isinstance(item, dict) and item.get("symbol")
            }
            for symbol in symbols:
                item = by_symbol.get(symbol)
                result["processed"] += 1
                result["last_processed_symbol"] = symbol
                if item is not None and item.get("status") == "success":
                    result["success"] += 1
                else:
                    result["error"] += 1
                    result["errors"].append(
                        {
                            "symbol": symbol,
                            "error": (item or {}).get("error", "refresh result missing"),
                        }
                    )
            if index < len(batches) - 1 and rate_limit_seconds:
                self.sleep_fn(rate_limit_seconds)

        if result["error"]:
            result["status"] = "partial" if result["success"] else "error"
        reference_data = self._refresh_reference_data(days=days)
        result["reference_data"] = reference_data
        if reference_data["status"] in {"partial", "error"} and result["status"] == "completed":
            result["status"] = "partial"
        result["coverage"] = self._coverage(plan.universe_symbols)
        return result

    def _reference_data_plan(self, *, apply: bool) -> dict[str, Any]:
        supported = callable(getattr(self.cache_service, "refresh_benchmark_bars", None))
        return {
            "supported": supported,
            "status": ("pending" if apply else "planned") if supported else "unsupported",
            "symbols": list(self.REFERENCE_SYMBOLS),
            "processed": 0,
            "success": 0,
            "error": 0,
            "errors": [],
        }

    def _refresh_reference_data(self, *, days: int) -> dict[str, Any]:
        summary = self._reference_data_plan(apply=True)
        refresh = getattr(self.cache_service, "refresh_benchmark_bars", None)
        if not callable(refresh):
            return summary
        try:
            response = refresh(symbols=list(self.REFERENCE_SYMBOLS), days=days)
        except Exception as exc:
            summary.update(
                {
                    "status": "error",
                    "processed": len(self.REFERENCE_SYMBOLS),
                    "error": len(self.REFERENCE_SYMBOLS),
                    "errors": [
                        {"symbol": symbol, "error": str(exc)} for symbol in self.REFERENCE_SYMBOLS
                    ],
                }
            )
            return summary

        items = self._response_items(response)
        by_symbol = {
            str(item.get("symbol")): item
            for item in items
            if isinstance(item, dict) and item.get("symbol")
        }
        errors: list[dict[str, str]] = []
        success = 0
        for symbol in self.REFERENCE_SYMBOLS:
            item = by_symbol.get(symbol)
            if item is not None and item.get("status") == "success":
                success += 1
                continue
            errors.append(
                {
                    "symbol": symbol,
                    "error": str((item or {}).get("error", "refresh result missing")),
                }
            )
        error_count = len(errors)
        summary.update(
            {
                "status": ("completed" if not error_count else "partial" if success else "error"),
                "processed": len(self.REFERENCE_SYMBOLS),
                "success": success,
                "error": error_count,
                "errors": errors,
            }
        )
        return summary

    def _coverage(self, universe: tuple[str, ...]) -> dict[str, Any]:
        universe_count = len(universe)
        empty = {
            "bar": {"symbols": 0, "universe": universe_count, "rows": 0, "pct": 0.0},
            "amount": {"complete_rows": 0, "total_rows": 0, "pct": 0.0},
            "latest_cross_section": {
                "trade_date": None,
                "symbols": 0,
                "universe": universe_count,
                "pct": 0.0,
            },
        }
        store = getattr(self.cache_service, "store", None)
        if not universe or store is None or not hasattr(store, "fetch_all"):
            return empty

        rows: list[dict[str, Any]] = []
        query_batch_size = 400
        for offset in range(0, universe_count, query_batch_size):
            symbols = universe[offset : offset + query_batch_size]
            placeholders = ",".join("?" for _ in symbols)
            rows.extend(
                store.fetch_all(
                    f"""
                    SELECT symbol,
                           COUNT(*) AS bar_rows,
                           SUM(CASE WHEN amount IS NOT NULL AND amount > 0 THEN 1 ELSE 0 END)
                               AS amount_complete_rows,
                           MAX(trade_date) AS latest_trade_date
                    FROM daily_bar_cache
                    WHERE trade_date != 'ERROR'
                      AND close IS NOT NULL
                      AND symbol IN ({placeholders})
                    GROUP BY symbol
                    """,
                    tuple(symbols),
                )
            )

        bar_rows = sum(int(row.get("bar_rows") or 0) for row in rows)
        amount_complete = sum(int(row.get("amount_complete_rows") or 0) for row in rows)
        latest_trade_date = max(
            (str(row["latest_trade_date"]) for row in rows if row.get("latest_trade_date")),
            default=None,
        )
        latest_symbols = sum(1 for row in rows if row.get("latest_trade_date") == latest_trade_date)
        return {
            "bar": {
                "symbols": len(rows),
                "universe": universe_count,
                "rows": bar_rows,
                "pct": self._pct(len(rows), universe_count),
            },
            "amount": {
                "complete_rows": amount_complete,
                "total_rows": bar_rows,
                "pct": self._pct(amount_complete, bar_rows),
            },
            "latest_cross_section": {
                "trade_date": latest_trade_date,
                "symbols": latest_symbols,
                "universe": universe_count,
                "pct": self._pct(latest_symbols, universe_count),
            },
        }

    @staticmethod
    def _pct(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return round(numerator / denominator * 100.0, 2)

    @staticmethod
    def _safety(*, apply: bool) -> dict[str, bool]:
        return {
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
            "writes_enabled": bool(apply),
        }

    def _refresh_with_isolation(self, symbols: list[str], *, days: int) -> list[dict[str, Any]]:
        try:
            response = self.cache_service.refresh_symbols(symbols, days=days)
        except Exception as batch_error:
            if len(symbols) == 1:
                return [{"symbol": symbols[0], "status": "error", "error": str(batch_error)}]
            isolated: list[dict[str, Any]] = []
            for symbol in symbols:
                try:
                    response = self.cache_service.refresh_symbols([symbol], days=days)
                except Exception as symbol_error:
                    isolated.append(
                        {"symbol": symbol, "status": "error", "error": str(symbol_error)}
                    )
                    continue
                isolated.extend(self._response_items(response))
            return isolated
        return self._response_items(response)

    @staticmethod
    def _response_items(response: object) -> list[dict[str, Any]]:
        if not isinstance(response, dict):
            return []
        raw_results = response.get("results", [])
        if not isinstance(raw_results, list):
            return []
        return [item for item in raw_results if isinstance(item, dict)]

    @classmethod
    def _extract_symbols(cls, spot: pd.DataFrame) -> set[str]:
        if not isinstance(spot, pd.DataFrame) or spot.empty:
            return set()
        code_column = next(
            (column for column in ("代码", "symbol", "code", "证券代码") if column in spot.columns),
            None,
        )
        if code_column is None:
            raise ValueError(f"spot data has no supported symbol column: {list(spot.columns)}")
        result: set[str] = set()
        for raw in spot[code_column].tolist():
            symbol = cls._normalize_symbol(raw)
            if symbol is not None:
                result.add(symbol)
        return result

    @staticmethod
    def _normalize_symbol(raw: object) -> str | None:
        if raw is None or pd.isna(raw):
            return None
        text = str(raw).strip().upper()
        if re.fullmatch(r"\d+(?:\.0+)?", text):
            code = f"{int(float(text)):06d}"
        else:
            match = re.search(r"(\d{6})", text)
            if not match:
                return None
            code = match.group(1)
        if code.startswith(("600", "601", "603", "605", "688", "689")):
            return f"SH{code}"
        if code.startswith(("000", "001", "002", "003", "300", "301")):
            return f"SZ{code}"
        return None
