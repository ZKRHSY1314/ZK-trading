from __future__ import annotations

from datetime import date, datetime
import sys
from types import SimpleNamespace

import pandas as pd
import requests

from app.data.capital_flow import (
    AkshareEastmoneyCapitalFlowProvider,
    CapitalFlowService,
)


class StubCapitalFlowProvider:
    def __init__(
        self,
        *,
        market_rows: list[dict] | None = None,
        symbol_rows: list[dict] | None = None,
        market_error: Exception | None = None,
    ) -> None:
        self.market_rows = market_rows or []
        self.symbol_rows = symbol_rows or []
        self.market_error = market_error
        self.symbol_calls: list[tuple[str, str]] = []

    def fetch_market_flow(self) -> pd.DataFrame:
        if self.market_error is not None:
            raise self.market_error
        return pd.DataFrame(self.market_rows)

    def fetch_symbol_flow(self, stock: str, market: str) -> pd.DataFrame:
        self.symbol_calls.append((stock, market))
        return pd.DataFrame(self.symbol_rows)


def _clear_capital_flow_tables(test_db) -> None:
    with test_db.connect() as conn:
        conn.execute("DELETE FROM capital_flow_ingestion_runs")
        conn.execute("DELETE FROM capital_flow_snapshots")


def test_akshare_provider_applies_a_bounded_http_timeout(monkeypatch) -> None:
    captured: dict[str, float] = {}

    def fake_get(*_args, **kwargs):
        captured["timeout"] = kwargs["timeout"]
        return object()

    def fetch_market_flow() -> pd.DataFrame:
        requests.get("https://example.invalid/vendor")
        return pd.DataFrame()

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setitem(
        sys.modules,
        "akshare",
        SimpleNamespace(stock_market_fund_flow=fetch_market_flow),
    )

    frame = AkshareEastmoneyCapitalFlowProvider(
        timeout_seconds=7,
    ).fetch_market_flow()

    assert frame.empty
    assert captured["timeout"] == 7


def test_market_refresh_normalizes_vendor_data_with_code_owned_provenance(test_db):
    _clear_capital_flow_tables(test_db)
    provider = StubCapitalFlowProvider(
        market_rows=[
            {
                "日期": "2026-07-17",
                "主力净流入-净额": 120_000_000,
                "主力净流入-净占比": 1.25,
                "超大单净流入-净额": 80_000_000,
                "超大单净流入-净占比": 0.8,
                "大单净流入-净额": 40_000_000,
                "大单净流入-净占比": 0.45,
                "中单净流入-净额": -20_000_000,
                "中单净流入-净占比": -0.2,
                "小单净流入-净额": -100_000_000,
                "小单净流入-净占比": -1.05,
                "source": "forged-provider",
                "verified": True,
            }
        ]
    )
    service = CapitalFlowService(store=test_db, provider=provider)

    result = service.refresh_market(
        now=datetime(2026, 7, 19, 10, 0),
        trading_dates={date(2026, 7, 17)},
    )

    assert result["status"] == "completed"
    snapshot = result["snapshot"]
    assert snapshot["status"] == "available"
    assert snapshot["scope"] == "market"
    assert snapshot["symbol"] is None
    assert snapshot["as_of"] == "2026-07-17"
    assert snapshot["freshness"] == "latest_session"
    assert snapshot["source"] == "akshare.eastmoney.stock_market_fund_flow"
    assert snapshot["provider"] == "akshare"
    assert snapshot["upstream"] == "eastmoney"
    assert snapshot["endpoint"] == "stock_market_fund_flow"
    assert snapshot["source_semantics"] == "vendor_derived_order_size_classification"
    assert snapshot["unit"] == "CNY"
    assert snapshot["main_net_inflow"] == 120_000_000
    assert snapshot["super_large_order_net"] == 80_000_000
    assert snapshot["large_order_net"] == 40_000_000
    assert snapshot["medium_order_net"] == -20_000_000
    assert snapshot["small_order_net"] == -100_000_000
    assert snapshot["review_only"] is True
    assert snapshot["simulation_only"] is True
    assert snapshot["live_trading_enabled"] is False


def test_identical_content_is_deduplicated_and_same_day_revision_is_retained(test_db):
    _clear_capital_flow_tables(test_db)
    provider = StubCapitalFlowProvider(
        market_rows=[
            {
                "日期": "2026-07-17",
                "主力净流入-净额": 120_000_000,
                "大单净流入-净额": 40_000_000,
            }
        ]
    )
    service = CapitalFlowService(store=test_db, provider=provider)
    trading_dates = {date(2026, 7, 17)}

    first = service.refresh_market(
        now=datetime(2026, 7, 17, 16, 0),
        trading_dates=trading_dates,
    )
    duplicate = service.refresh_market(
        now=datetime(2026, 7, 17, 16, 5),
        trading_dates=trading_dates,
    )
    provider.market_rows[0]["主力净流入-净额"] = 135_000_000
    revision = service.refresh_market(
        now=datetime(2026, 7, 17, 16, 10),
        trading_dates=trading_dates,
    )

    assert first["accepted_count"] == 1
    assert duplicate["accepted_count"] == 0
    assert duplicate["duplicate_count"] == 1
    assert revision["accepted_count"] == 1
    history = service.history(scope="market", limit=10)
    assert len(history) == 2
    assert history[0].main_net_inflow == 135_000_000
    assert history[1].main_net_inflow == 120_000_000
    assert history[0].content_hash != history[1].content_hash


def test_provider_failure_retains_last_known_snapshot_as_degraded(test_db):
    _clear_capital_flow_tables(test_db)
    provider = StubCapitalFlowProvider(
        market_rows=[
            {
                "日期": "2026-07-17",
                "主力净流入-净额": 88_000_000,
                "小单净流入-净额": -88_000_000,
            }
        ]
    )
    service = CapitalFlowService(store=test_db, provider=provider)
    trading_dates = {date(2026, 7, 17)}
    service.refresh_market(
        now=datetime(2026, 7, 17, 16, 0),
        trading_dates=trading_dates,
    )
    provider.market_error = RuntimeError("proxy disconnected")

    failed = service.refresh_market(
        now=datetime(2026, 7, 19, 10, 0),
        trading_dates=trading_dates,
    )
    latest = service.latest(
        scope="market",
        now=datetime(2026, 7, 19, 10, 1),
        trading_dates=trading_dates,
    )

    assert failed["status"] == "degraded"
    assert failed["retained_last_known"] is True
    assert failed["error_type"] == "RuntimeError"
    assert failed["snapshot"]["main_net_inflow"] == 88_000_000
    assert failed["snapshot"]["status"] == "degraded"
    assert failed["snapshot"]["last_known"] is True
    assert failed["snapshot"]["reason"] == "capital_flow_provider_failed"
    assert latest.status == "degraded"
    assert latest.last_known is True
    assert latest.reason == "capital_flow_provider_failed"
    assert len(service.history(scope="market", limit=10)) == 1


def test_symbol_refresh_uses_exchange_mapping_and_daily_session_freshness(test_db):
    _clear_capital_flow_tables(test_db)
    provider = StubCapitalFlowProvider(
        symbol_rows=[
            {
                "日期": "2026-07-17",
                "主力净流入-净额": 9_000_000,
                "主力净流入-净占比": 2.1,
                "小单净流入-净额": -9_000_000,
            }
        ]
    )
    service = CapitalFlowService(store=test_db, provider=provider)
    trading_dates = {date(2026, 7, 17), date(2026, 7, 20)}

    intraday = service.refresh_symbol(
        "sh600519",
        now=datetime(2026, 7, 17, 10, 30),
        trading_dates=trading_dates,
    )
    end_of_day = service.latest(
        scope="symbol",
        symbol="SH600519",
        now=datetime(2026, 7, 17, 16, 0),
        trading_dates=trading_dates,
    )
    next_session_before_close = service.latest(
        scope="symbol",
        symbol="SH600519",
        now=datetime(2026, 7, 20, 10, 0),
        trading_dates=trading_dates,
    )
    next_session_after_close = service.latest(
        scope="symbol",
        symbol="SH600519",
        now=datetime(2026, 7, 20, 16, 0),
        trading_dates=trading_dates,
    )

    assert provider.symbol_calls == [("600519", "sh")]
    assert intraday["snapshot"]["freshness"] == "intraday_vendor_snapshot"
    assert intraday["snapshot"]["source"] == "akshare.eastmoney.stock_individual_fund_flow"
    assert intraday["snapshot"]["endpoint"] == "stock_individual_fund_flow"
    assert end_of_day.freshness == "end_of_day"
    assert end_of_day.status == "available"
    assert next_session_before_close.freshness == "latest_session"
    assert next_session_before_close.status == "available"
    assert next_session_after_close.freshness == "stale"
    assert next_session_after_close.status == "degraded"
    assert next_session_after_close.reason == "capital_flow_snapshot_stale"


def test_future_dated_or_value_less_rows_are_rejected_as_unverified(test_db):
    _clear_capital_flow_tables(test_db)
    provider = StubCapitalFlowProvider(
        market_rows=[
            {"日期": "2026-07-20", "主力净流入-净额": 1_000_000},
            {"日期": "2026-07-17", "主力净流入-净占比": 1.2},
        ]
    )
    service = CapitalFlowService(store=test_db, provider=provider)

    result = service.refresh_market(
        now=datetime(2026, 7, 17, 16, 0),
        trading_dates={date(2026, 7, 17), date(2026, 7, 20)},
    )

    assert result["status"] == "failed"
    assert result["accepted_count"] == 0
    assert result["rejected_count"] == 2
    assert result["snapshot"]["status"] == "unavailable"
    assert result["snapshot"]["reason"] == "no_verified_capital_flow_source"
    assert service.history(scope="market") == []
