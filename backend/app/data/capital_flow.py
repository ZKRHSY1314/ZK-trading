from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time
import hashlib
import json
import math
import re
from typing import Any, Protocol

import pandas as pd

from app.config import settings
from app.data.trading_calendar import trading_session_age
from app.models import CapitalFlowSnapshot
from app.storage.sqlite_store import SQLiteStore


SOURCE_SEMANTICS = "vendor_derived_order_size_classification"


@dataclass(frozen=True)
class CapitalFlowSource:
    source: str
    provider: str
    upstream: str
    endpoint: str
    source_url: str


MARKET_SOURCE = CapitalFlowSource(
    source="akshare.eastmoney.stock_market_fund_flow",
    provider="akshare",
    upstream="eastmoney",
    endpoint="stock_market_fund_flow",
    source_url="https://data.eastmoney.com/zjlx/dpzjlx.html",
)
SYMBOL_SOURCE = CapitalFlowSource(
    source="akshare.eastmoney.stock_individual_fund_flow",
    provider="akshare",
    upstream="eastmoney",
    endpoint="stock_individual_fund_flow",
    source_url="https://data.eastmoney.com/zjlx/detail.html",
)


class CapitalFlowProvider(Protocol):
    def fetch_market_flow(self) -> pd.DataFrame:
        ...

    def fetch_symbol_flow(self, stock: str, market: str) -> pd.DataFrame:
        ...


class AkshareEastmoneyCapitalFlowProvider:
    """Read-only access to Eastmoney vendor-derived flow data through AKShare."""

    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = max(1.0, min(float(timeout_seconds), 120.0))

    def fetch_market_flow(self) -> pd.DataFrame:
        import akshare as ak

        return self._bounded_request(ak.stock_market_fund_flow)

    def fetch_symbol_flow(self, stock: str, market: str) -> pd.DataFrame:
        import akshare as ak

        return self._bounded_request(
            lambda: ak.stock_individual_fund_flow(stock=stock, market=market)
        )

    def _bounded_request(self, operation: Any) -> pd.DataFrame:
        import requests
        from unittest.mock import patch

        original_get = requests.get

        def bounded_get(*args: Any, **kwargs: Any) -> Any:
            kwargs.setdefault("timeout", self.timeout_seconds)
            return original_get(*args, **kwargs)

        # AKShare's public functions do not currently expose a timeout.  This
        # worker is single-threaded, so a scoped patch keeps the long-running
        # collector retryable without changing process-wide networking.
        with patch.object(requests, "get", bounded_get):
            result = operation()
        if not isinstance(result, pd.DataFrame):
            raise TypeError("capital-flow provider must return a DataFrame")
        return result


class CapitalFlowService:
    """Normalize and retain auditable daily capital-flow snapshots.

    Capital-flow classifications are vendor-derived research evidence. This
    service writes research snapshots only and has no broker or order surface.
    """

    def __init__(
        self,
        *,
        store: SQLiteStore | None = None,
        provider: CapitalFlowProvider | None = None,
    ) -> None:
        self.store = store or SQLiteStore(settings.database_path)
        if store is None:
            self.store.init()
        self.provider = provider or AkshareEastmoneyCapitalFlowProvider()

    def refresh_market(
        self,
        *,
        now: datetime | None = None,
        trading_dates: Iterable[date] | None = None,
    ) -> dict[str, Any]:
        current = now or datetime.now()
        try:
            frame = self.provider.fetch_market_flow()
        except Exception as exc:
            return self._provider_failure(
                scope="market",
                symbol="",
                source=MARKET_SOURCE,
                now=current,
                error=exc,
                trading_dates=trading_dates,
            )
        return self._persist_frame(
            frame=frame,
            scope="market",
            symbol="",
            source=MARKET_SOURCE,
            now=current,
            trading_dates=trading_dates,
        )

    def refresh_symbol(
        self,
        symbol: str,
        *,
        now: datetime | None = None,
        trading_dates: Iterable[date] | None = None,
    ) -> dict[str, Any]:
        normalized_symbol = self._scope_symbol("symbol", symbol)
        current = now or datetime.now()
        try:
            frame = self.provider.fetch_symbol_flow(
                normalized_symbol[2:],
                normalized_symbol[:2].lower(),
            )
        except Exception as exc:
            return self._provider_failure(
                scope="symbol",
                symbol=normalized_symbol,
                source=SYMBOL_SOURCE,
                now=current,
                error=exc,
                trading_dates=trading_dates,
            )
        return self._persist_frame(
            frame=frame,
            scope="symbol",
            symbol=normalized_symbol,
            source=SYMBOL_SOURCE,
            now=current,
            trading_dates=trading_dates,
        )

    def latest(
        self,
        *,
        scope: str = "market",
        symbol: str | None = None,
        now: datetime | None = None,
        trading_dates: Iterable[date] | None = None,
    ) -> CapitalFlowSnapshot:
        symbol_key = self._scope_symbol(scope, symbol)
        row = self.store.fetch_one(
            """
            SELECT *
            FROM capital_flow_snapshots
            WHERE scope = ? AND symbol = ?
            ORDER BY trade_date DESC, id DESC
            LIMIT 1
            """,
            (scope, symbol_key),
        )
        if not row:
            return CapitalFlowSnapshot(
                symbol=symbol_key or None,
                scope=scope,
                reason="no_verified_capital_flow_source",
            )
        latest_run = self.store.fetch_one(
            """
            SELECT status, error_type, error_message
            FROM capital_flow_ingestion_runs
            WHERE scope = ? AND symbol = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (scope, symbol_key),
        )
        provider_failed = bool(
            latest_run and str(latest_run.get("status") or "") in {"degraded", "failed"}
        )
        return self._snapshot_from_row(
            row,
            scope=scope,
            symbol=symbol_key,
            now=now or datetime.now(),
            trading_dates=trading_dates,
            provider_failed=provider_failed,
        )

    def history(
        self,
        *,
        scope: str = "market",
        symbol: str | None = None,
        limit: int = 100,
        now: datetime | None = None,
        trading_dates: Iterable[date] | None = None,
    ) -> list[CapitalFlowSnapshot]:
        symbol_key = self._scope_symbol(scope, symbol)
        rows = self.store.fetch_all(
            """
            SELECT *
            FROM capital_flow_snapshots
            WHERE scope = ? AND symbol = ?
            ORDER BY trade_date DESC, id DESC
            LIMIT ?
            """,
            (scope, symbol_key, max(1, min(int(limit), 500))),
        )
        current = now or datetime.now()
        return [
            self._snapshot_from_row(
                row,
                scope=scope,
                symbol=symbol_key,
                now=current,
                trading_dates=trading_dates,
                provider_failed=False,
            )
            for row in rows
        ]

    def _snapshot_from_row(
        self,
        row: dict[str, Any],
        *,
        scope: str,
        symbol: str,
        now: datetime,
        trading_dates: Iterable[date] | None,
        provider_failed: bool,
    ) -> CapitalFlowSnapshot:
        freshness, calendar_source = self._freshness(
            date.fromisoformat(str(row["trade_date"])),
            now,
            trading_dates=trading_dates,
        )
        quality_status = (
            "degraded_last_known"
            if provider_failed
            else "ready" if freshness != "stale" else "stale"
        )
        return CapitalFlowSnapshot(
            symbol=symbol or None,
            status="available" if quality_status == "ready" else "degraded",
            scope=scope,
            source=str(row["source"]),
            provider=str(row["provider"]),
            upstream=str(row["upstream"]),
            endpoint=str(row["endpoint"]),
            source_url=str(row["source_url"]),
            source_semantics=str(row["source_semantics"]),
            as_of=str(row["trade_date"]),
            retrieved_at=str(row["retrieved_at"]),
            freshness=freshness,
            quality_status=quality_status,
            trading_calendar_source=calendar_source,
            last_known=provider_failed,
            unit=str(row["unit"]),
            main_net_inflow=row.get("main_net_inflow"),
            main_net_inflow_ratio=row.get("main_net_inflow_ratio"),
            super_large_order_net=row.get("super_large_order_net"),
            super_large_order_net_ratio=row.get("super_large_order_net_ratio"),
            large_order_net=row.get("large_order_net"),
            large_order_net_ratio=row.get("large_order_net_ratio"),
            medium_order_net=row.get("medium_order_net"),
            medium_order_net_ratio=row.get("medium_order_net_ratio"),
            small_order_net=row.get("small_order_net"),
            small_order_net_ratio=row.get("small_order_net_ratio"),
            content_hash=str(row["content_hash"]),
            reason=(
                "capital_flow_provider_failed"
                if provider_failed
                else "capital_flow_snapshot_stale" if quality_status == "stale" else None
            ),
        )

    def _provider_failure(
        self,
        *,
        scope: str,
        symbol: str,
        source: CapitalFlowSource,
        now: datetime,
        error: Exception,
        trading_dates: Iterable[date] | None,
    ) -> dict[str, Any]:
        retained_last_known = bool(
            self.store.fetch_one(
                """
                SELECT id
                FROM capital_flow_snapshots
                WHERE scope = ? AND symbol = ?
                ORDER BY trade_date DESC, id DESC
                LIMIT 1
                """,
                (scope, symbol),
            )
        )
        status = "degraded" if retained_last_known else "failed"
        timestamp = now.isoformat(timespec="seconds")
        with self.store.connect() as conn:
            conn.execute(
                """
                INSERT INTO capital_flow_ingestion_runs(
                    scope, symbol, status, provider, endpoint, started_at,
                    completed_at, fetched_count, accepted_count, duplicate_count,
                    rejected_count, error_type, error_message, details_json,
                    review_only, simulation_only, live_trading_enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, ?, ?, ?, 1, 1, 0)
                """,
                (
                    scope,
                    symbol,
                    status,
                    source.provider,
                    source.endpoint,
                    timestamp,
                    timestamp,
                    type(error).__name__,
                    str(error),
                    json.dumps(
                        {
                            "retained_last_known": retained_last_known,
                            "source_semantics": SOURCE_SEMANTICS,
                        },
                        sort_keys=True,
                    ),
                ),
            )
        snapshot = self.latest(
            scope=scope,
            symbol=symbol or None,
            now=now,
            trading_dates=trading_dates,
        )
        return {
            "status": status,
            "fetched_count": 0,
            "accepted_count": 0,
            "duplicate_count": 0,
            "rejected_count": 0,
            "retained_last_known": retained_last_known,
            "error_type": type(error).__name__,
            "error": str(error),
            "snapshot": snapshot.model_dump(mode="json"),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    def _persist_frame(
        self,
        *,
        frame: pd.DataFrame,
        scope: str,
        symbol: str,
        source: CapitalFlowSource,
        now: datetime,
        trading_dates: Iterable[date] | None,
    ) -> dict[str, Any]:
        started_at = now.isoformat(timespec="seconds")
        records = [] if frame is None else frame.to_dict(orient="records")
        accepted_count = 0
        duplicate_count = 0
        rejected_count = 0
        latest_trade_date: str | None = None
        with self.store.connect() as conn:
            for raw in records:
                normalized = self._normalize_row(raw)
                if normalized is None:
                    rejected_count += 1
                    continue
                trade_date = str(normalized["trade_date"])
                if date.fromisoformat(trade_date) > now.date():
                    rejected_count += 1
                    continue
                latest_trade_date = max(latest_trade_date or trade_date, trade_date)
                content_hash = self._content_hash(scope, symbol, source, normalized)
                freshness, _ = self._freshness(
                    date.fromisoformat(trade_date),
                    now,
                    trading_dates=trading_dates,
                )
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO capital_flow_snapshots(
                        scope, symbol, trade_date, retrieved_at, source, provider,
                        upstream, endpoint, source_url, source_semantics, unit,
                        main_net_inflow, main_net_inflow_ratio,
                        super_large_order_net, super_large_order_net_ratio,
                        large_order_net, large_order_net_ratio,
                        medium_order_net, medium_order_net_ratio,
                        small_order_net, small_order_net_ratio,
                        quality_status, content_hash, raw_payload_json,
                        normalized_payload_json, review_only, simulation_only,
                        live_trading_enabled
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CNY',
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 0
                    )
                    """,
                    (
                        scope,
                        symbol,
                        trade_date,
                        started_at,
                        source.source,
                        source.provider,
                        source.upstream,
                        source.endpoint,
                        source.source_url,
                        SOURCE_SEMANTICS,
                        normalized["main_net_inflow"],
                        normalized["main_net_inflow_ratio"],
                        normalized["super_large_order_net"],
                        normalized["super_large_order_net_ratio"],
                        normalized["large_order_net"],
                        normalized["large_order_net_ratio"],
                        normalized["medium_order_net"],
                        normalized["medium_order_net_ratio"],
                        normalized["small_order_net"],
                        normalized["small_order_net_ratio"],
                        "ready" if freshness != "stale" else "stale",
                        content_hash,
                        json.dumps(raw, ensure_ascii=False, default=str, sort_keys=True),
                        json.dumps(normalized, ensure_ascii=False, sort_keys=True),
                    ),
                )
                if cursor.rowcount:
                    accepted_count += 1
                else:
                    duplicate_count += 1
            conn.execute(
                """
                INSERT INTO capital_flow_ingestion_runs(
                    scope, symbol, status, provider, endpoint, started_at,
                    completed_at, fetched_count, accepted_count, duplicate_count,
                    rejected_count, latest_trade_date, details_json,
                    review_only, simulation_only, live_trading_enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 0)
                """,
                (
                    scope,
                    symbol,
                    "completed" if accepted_count or duplicate_count else "failed",
                    source.provider,
                    source.endpoint,
                    started_at,
                    now.isoformat(timespec="seconds"),
                    len(records),
                    accepted_count,
                    duplicate_count,
                    rejected_count,
                    latest_trade_date,
                    json.dumps({"source_semantics": SOURCE_SEMANTICS}, sort_keys=True),
                ),
            )
        snapshot = self.latest(
            scope=scope,
            symbol=symbol or None,
            now=now,
            trading_dates=trading_dates,
        )
        status = "completed" if accepted_count or duplicate_count else "failed"
        return {
            "status": status,
            "fetched_count": len(records),
            "accepted_count": accepted_count,
            "duplicate_count": duplicate_count,
            "rejected_count": rejected_count,
            "snapshot": snapshot.model_dump(mode="json"),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }

    @staticmethod
    def _normalize_row(raw: dict[str, Any]) -> dict[str, Any] | None:
        raw_date = raw.get("日期")
        try:
            trade_date = date.fromisoformat(str(raw_date)[:10])
        except (TypeError, ValueError):
            return None
        normalized = {
            "trade_date": trade_date.isoformat(),
            "main_net_inflow": _finite_number(raw.get("主力净流入-净额")),
            "main_net_inflow_ratio": _finite_number(raw.get("主力净流入-净占比")),
            "super_large_order_net": _finite_number(raw.get("超大单净流入-净额")),
            "super_large_order_net_ratio": _finite_number(raw.get("超大单净流入-净占比")),
            "large_order_net": _finite_number(raw.get("大单净流入-净额")),
            "large_order_net_ratio": _finite_number(raw.get("大单净流入-净占比")),
            "medium_order_net": _finite_number(raw.get("中单净流入-净额")),
            "medium_order_net_ratio": _finite_number(raw.get("中单净流入-净占比")),
            "small_order_net": _finite_number(raw.get("小单净流入-净额")),
            "small_order_net_ratio": _finite_number(raw.get("小单净流入-净占比")),
        }
        if all(
            normalized[key] is None
            for key in (
                "main_net_inflow",
                "super_large_order_net",
                "large_order_net",
                "medium_order_net",
                "small_order_net",
            )
        ):
            return None
        return normalized

    @staticmethod
    def _content_hash(
        scope: str,
        symbol: str,
        source: CapitalFlowSource,
        normalized: dict[str, Any],
    ) -> str:
        canonical = json.dumps(
            {
                "scope": scope,
                "symbol": symbol,
                "source": source.source,
                "data": normalized,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _scope_symbol(scope: str, symbol: str | None) -> str:
        if scope == "market":
            if symbol:
                raise ValueError("market scope must not include a symbol")
            return ""
        if scope != "symbol":
            raise ValueError("unsupported capital-flow scope")
        normalized = str(symbol or "").strip().upper()
        if not re.fullmatch(r"(?:SH|SZ|BJ)\d{6}", normalized):
            raise ValueError("unsupported A-share symbol")
        return normalized

    @staticmethod
    def _freshness(
        trade_date: date,
        now: datetime,
        *,
        trading_dates: Iterable[date] | None,
    ) -> tuple[str, str]:
        target_date = now.date()
        if trade_date > target_date:
            return "stale", "future_date_rejected"
        if trade_date == target_date:
            return (
                ("intraday_vendor_snapshot", "same_session")
                if now.time() < time(15, 0)
                else ("end_of_day", "same_session")
            )
        if trading_dates is not None:
            sessions = set(trading_dates)
            age = sum(1 for item in sessions if trade_date < item <= target_date)
            if now.time() < time(15, 0) and target_date in sessions:
                age = max(0, age - 1)
            calendar_source = "injected"
        else:
            age, calendar_source = trading_session_age(
                trade_date,
                target_date,
                exclude_target_session=now.time() < time(15, 0),
            )
        return ("latest_session", calendar_source) if age == 0 else ("stale", calendar_source)


def _finite_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None
