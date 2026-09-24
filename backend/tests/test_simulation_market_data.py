from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from app.simulation.broker import SimulatedBroker
from app.storage.sqlite_store import SQLiteStore


def _reset_symbol(store, symbol: str) -> None:
    with store.connect() as conn:
        conn.execute("DELETE FROM realtime_market_events WHERE symbol = ?", (symbol,))
        conn.execute("DELETE FROM daily_bar_cache WHERE symbol = ?", (symbol,))


def _reset_account(store, name: str) -> None:
    account = store.fetch_one("SELECT id FROM simulation_accounts WHERE name = ?", (name,))
    if not account:
        return
    with store.connect() as conn:
        conn.execute("DELETE FROM simulation_fills WHERE account_id = ?", (account["id"],))
        conn.execute("DELETE FROM simulation_positions WHERE account_id = ?", (account["id"],))
        conn.execute("DELETE FROM simulation_accounts WHERE id = ?", (account["id"],))


def _seed_account(store, *, name: str, symbol: str, cash: float = 5_000.0, avg_cost: float = 8.0) -> None:
    _reset_account(store, name)
    with store.connect() as conn:
        cursor = conn.execute(
            "INSERT INTO simulation_accounts(name, cash, initial_cash) VALUES (?, ?, ?)",
            (name, cash, 10_000.0),
        )
        conn.execute(
            """
            INSERT INTO simulation_positions(
                account_id, symbol, name, quantity, sellable_quantity, avg_cost
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (int(cursor.lastrowid), symbol, "估值测试", 100, 100, avg_cost),
        )


def _insert_daily(store, symbol: str, trade_date: str, close: float) -> None:
    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO daily_bar_cache(
                symbol, trade_date, close, source, adjustment_mode, volume_unit, quality_status
            )
            VALUES (?, ?, ?, 'test_daily', 'qfq', 'shares', 'ready')
            """,
            (symbol, trade_date, close),
        )


def _insert_realtime(
    store,
    *,
    symbol: str,
    price: float,
    payload: dict,
    source: str = "asharehub",
    quality_status: str = "realtime_ok",
    fallback_used: int = 0,
) -> str:
    event_ts = datetime.now().isoformat(timespec="seconds")
    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO realtime_market_events(
                symbol, price, source, provider_status, event_ts, received_ts,
                quality_status, fallback_used, payload_json, dedupe_key
            )
            VALUES (?, ?, ?, 'ok', ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol,
                price,
                source,
                event_ts,
                event_ts,
                quality_status,
                fallback_used,
                json.dumps(payload, ensure_ascii=False),
                f"test:{symbol}:{event_ts}:{source}",
            ),
        )
    return event_ts


def _insert_capital_flow_snapshot(
    store,
    *,
    scope: str = "market",
    symbol: str = "",
    main_net: float = 188_000_000,
) -> None:
    trade_date = datetime.now().date().isoformat()
    retrieved_at = datetime.now().astimezone().isoformat(timespec="seconds")
    content_hash = f"pytest:{scope}:{symbol}:{main_net}"
    with store.connect() as conn:
        conn.execute(
            "DELETE FROM capital_flow_ingestion_runs WHERE scope = ? AND symbol = ?",
            (scope, symbol),
        )
        conn.execute(
            "DELETE FROM capital_flow_snapshots WHERE scope = ? AND symbol = ?",
            (scope, symbol),
        )
        conn.execute(
            """
            INSERT INTO capital_flow_snapshots(
                scope, symbol, trade_date, retrieved_at, source, provider,
                upstream, endpoint, source_url, source_semantics, unit,
                main_net_inflow, super_large_order_net, large_order_net,
                medium_order_net, small_order_net, quality_status, content_hash,
                raw_payload_json, normalized_payload_json, review_only,
                simulation_only, live_trading_enabled
            ) VALUES (
                ?, ?, ?, ?, 'akshare.eastmoney.stock_market_fund_flow',
                'akshare', 'eastmoney', 'stock_market_fund_flow',
                'https://data.eastmoney.com/zjlx/dpzjlx.html',
                'vendor_derived_order_size_classification', 'CNY',
                ?, 100000000, 88000000, -60000000, -128000000,
                'ready', ?, '{}', '{}', 1, 1, 0
            )
            """,
            (scope, symbol, trade_date, retrieved_at, main_net, content_hash),
        )


def _insert_screen_positions(
    store,
    *,
    positions: list[dict],
    created_at: datetime | None = None,
    status: str = "positions_parsed",
    parsed: bool = True,
    verified: bool = True,
) -> None:
    observed_at = created_at or datetime.now(timezone.utc)
    created_text = observed_at.astimezone(timezone.utc).replace(tzinfo=None).isoformat(
        sep=" ", timespec="seconds"
    )
    with store.connect() as conn:
        conn.execute("DELETE FROM sim_cockpit_readbacks WHERE readback_type = 'screen_positions'")
        conn.execute("DELETE FROM sim_cockpit_window_verifications WHERE verified_by = 'pytest'")
        verification = conn.execute(
            """
            INSERT INTO sim_cockpit_window_verifications(
                status, window_title, positive_terms_json, process_terms_json,
                blocked_reasons_json, detected_items_json, raw_payload_json,
                verified_by, confidence, simulation_mode_detected,
                real_trading_blocked, live_trading_enabled, created_at
            )
            VALUES (?, '同花顺模拟炒股', '["mncg"]', '["xiadan"]',
                    '[]', '[]', '{}', 'pytest', 0.99, ?, 1, 0, ?)
            """,
            ("verified" if verified else "needs_verification", int(verified), created_text),
        )
        payload = {
            "window_verification_id": int(verification.lastrowid),
            "screen_readback": {
                "status": status,
                "readback_type": "positions",
                "parsed": parsed,
                "requires_visual_or_ocr_review": not parsed,
                "positions": positions,
            },
            "simulation_only": True,
            "live_trading_enabled": False,
        }
        conn.execute(
            """
            INSERT INTO sim_cockpit_readbacks(
                readback_type, status, payload_json, simulation_only,
                live_trading_enabled, created_at
            )
            VALUES ('screen_positions', ?, ?, 1, 0, ?)
            """,
            (status, json.dumps(payload, ensure_ascii=False), created_text),
        )


def test_simulation_account_uses_latest_daily_close_for_mark_to_market(test_db):
    symbol = "SZ009901"
    account_name = "valuation-daily"
    _reset_symbol(test_db, symbol)
    _seed_account(test_db, name=account_name, symbol=symbol)
    today = datetime.now().date()
    _insert_daily(test_db, symbol, (today - timedelta(days=1)).isoformat(), 9.0)
    _insert_daily(test_db, symbol, today.isoformat(), 10.0)

    account = SimulatedBroker(account_name=account_name).account()
    position = account.positions[0]

    assert account.market_value == 1_000.0
    assert account.total_assets == 6_000.0
    assert account.unrealized_pnl == 200.0
    assert account.today_pnl == 100.0
    assert account.position_ratio == pytest.approx(16.67)
    assert account.valuation_status == "complete"
    assert account.simulation_only is True
    assert account.live_trading_enabled is False
    assert position.mark_price == 10.0
    assert position.previous_close == 9.0
    assert position.mark_source.startswith("daily_bar_cache:test_daily")
    assert position.freshness == "end_of_day"


def test_simulation_account_prefers_current_realtime_snapshot(test_db):
    symbol = "SZ009902"
    account_name = "valuation-realtime"
    _reset_symbol(test_db, symbol)
    _seed_account(test_db, name=account_name, symbol=symbol, avg_cost=9.5)
    today = datetime.now().date()
    _insert_daily(test_db, symbol, (today - timedelta(days=2)).isoformat(), 9.0)
    _insert_daily(test_db, symbol, (today - timedelta(days=1)).isoformat(), 10.0)
    event_ts = _insert_realtime(test_db, symbol=symbol, price=11.0, payload={"price": 11.0})

    account = SimulatedBroker(account_name=account_name).account()
    position = account.positions[0]

    assert position.mark_price == 11.0
    assert position.previous_close == 10.0
    assert position.mark_as_of == event_ts
    assert position.mark_source == "realtime_market_events:asharehub"
    assert position.freshness == "fresh"
    assert account.market_value == 1_100.0
    assert account.total_assets == 6_100.0
    assert account.unrealized_pnl == 150.0
    assert account.today_pnl == 100.0


def test_simulation_account_rejects_stale_realtime_mark_when_ready_daily_exists(test_db):
    symbol = "SZ009906"
    account_name = "valuation-stale-realtime"
    _reset_symbol(test_db, symbol)
    _seed_account(test_db, name=account_name, symbol=symbol, avg_cost=9.5)
    today = datetime.now().date()
    _insert_daily(test_db, symbol, (today - timedelta(days=1)).isoformat(), 9.0)
    _insert_daily(test_db, symbol, today.isoformat(), 10.0)
    _insert_realtime(
        test_db,
        symbol=symbol,
        price=11.0,
        payload={"price": 11.0},
        quality_status="stale",
    )

    account = SimulatedBroker(account_name=account_name).account()

    assert account.positions[0].mark_price == 10.0
    assert account.positions[0].mark_source.startswith("daily_bar_cache:")
    assert account.market_value == 1_000.0


def test_simulation_account_prefers_ready_same_day_close_over_realtime_event(test_db):
    symbol = "SZ009907"
    account_name = "valuation-same-day-close"
    _reset_symbol(test_db, symbol)
    _seed_account(test_db, name=account_name, symbol=symbol, avg_cost=9.5)
    today = datetime.now().date()
    _insert_daily(test_db, symbol, (today - timedelta(days=1)).isoformat(), 9.0)
    _insert_daily(test_db, symbol, today.isoformat(), 10.0)
    _insert_realtime(test_db, symbol=symbol, price=11.0, payload={"price": 11.0})

    account = SimulatedBroker(account_name=account_name).account()

    assert account.positions[0].mark_price == 10.0
    assert account.positions[0].previous_close == 9.0
    assert account.positions[0].mark_source.startswith("daily_bar_cache:")


def test_simulation_account_rejects_future_dated_realtime_mark(test_db):
    symbol = "SZ009910"
    account_name = "valuation-future-realtime"
    _reset_symbol(test_db, symbol)
    _seed_account(test_db, name=account_name, symbol=symbol, avg_cost=9.5)
    today = datetime.now().date()
    _insert_daily(test_db, symbol, (today - timedelta(days=2)).isoformat(), 9.0)
    _insert_daily(test_db, symbol, (today - timedelta(days=1)).isoformat(), 10.0)
    _insert_realtime(test_db, symbol=symbol, price=99.0, payload={"price": 99.0})
    future = (datetime.now() + timedelta(minutes=5)).isoformat(timespec="seconds")
    with test_db.connect() as conn:
        conn.execute(
            """
            UPDATE realtime_market_events
            SET event_ts = ?, received_ts = ?
            WHERE symbol = ?
            """,
            (future, future, symbol),
        )

    account = SimulatedBroker(account_name=account_name).account()

    assert account.positions[0].mark_price == 10.0
    assert account.positions[0].mark_source.startswith("daily_bar_cache:")


def test_simulation_account_does_not_use_cost_as_fake_market_price(test_db):
    symbol = "SZ009903"
    account_name = "valuation-unavailable"
    _reset_symbol(test_db, symbol)
    _seed_account(test_db, name=account_name, symbol=symbol, avg_cost=12.5)

    account = SimulatedBroker(account_name=account_name).account()
    position = account.positions[0]

    assert position.mark_price is None
    assert position.market_value is None
    assert position.mark_source == "unavailable"
    assert account.total_assets is None
    assert account.market_value is None
    assert account.position_ratio is None
    assert account.valuation_status == "unavailable"
    assert f"missing_mark_price:{symbol}" in account.valuation_warnings


def test_simulation_account_rejects_ready_but_non_qfq_daily_stock_marks(test_db):
    symbol = "SZ009908"
    account_name = "valuation-non-qfq"
    _reset_symbol(test_db, symbol)
    _seed_account(test_db, name=account_name, symbol=symbol, avg_cost=12.5)
    today = datetime.now().date()
    with test_db.connect() as conn:
        for trade_date, close in (
            ((today - timedelta(days=1)).isoformat(), 11.0),
            (today.isoformat(), 12.0),
        ):
            conn.execute(
                """
                INSERT INTO daily_bar_cache(
                    symbol, trade_date, close, source, adjustment_mode,
                    volume_unit, quality_status
                )
                VALUES (?, ?, ?, 'unadjusted_fixture', 'none', 'shares', 'ready')
                """,
                (symbol, trade_date, close),
            )

    account = SimulatedBroker(account_name=account_name).account()

    assert account.positions[0].mark_price is None
    assert account.positions[0].mark_source == "unavailable"
    assert account.valuation_status == "unavailable"


def test_simulation_account_valuation_timestamp_uses_oldest_position_mark(test_db):
    account_name = "valuation-oldest-mark"
    first_symbol = "SZ009909"
    second_symbol = "SH609909"
    _reset_symbol(test_db, first_symbol)
    _reset_symbol(test_db, second_symbol)
    _seed_account(test_db, name=account_name, symbol=first_symbol)
    account_row = test_db.fetch_one(
        "SELECT id FROM simulation_accounts WHERE name = ?",
        (account_name,),
    )
    with test_db.connect() as conn:
        conn.execute(
            """
            INSERT INTO simulation_positions(
                account_id, symbol, name, quantity, sellable_quantity, avg_cost
            )
            VALUES (?, ?, '第二持仓', 100, 100, 8.0)
            """,
            (account_row["id"], second_symbol),
        )
    today = datetime.now().date()
    _insert_daily(test_db, first_symbol, (today - timedelta(days=1)).isoformat(), 9.0)
    _insert_daily(test_db, first_symbol, today.isoformat(), 10.0)
    _insert_daily(test_db, second_symbol, (today - timedelta(days=2)).isoformat(), 7.0)
    _insert_daily(test_db, second_symbol, (today - timedelta(days=1)).isoformat(), 8.0)

    account = SimulatedBroker(account_name=account_name).account()

    assert account.valuation_as_of == (today - timedelta(days=1)).isoformat()


def test_simulation_account_api_keeps_original_fields_and_adds_safety_contract(client, test_db):
    _reset_account(test_db, "default")

    response = client.get("/api/simulation/account")

    assert response.status_code == 200
    body = response.json()
    assert {"account_id", "name", "cash", "initial_cash", "positions"} <= body.keys()
    assert body["total_assets"] == body["cash"]
    assert body["market_value"] == 0.0
    assert body["position_ratio"] == 0.0
    assert body["valuation_status"] == "complete"
    assert body["today_pnl_scope"] == "open_positions_mark_to_previous_close"
    assert body["simulation_only"] is True
    assert body["live_trading_enabled"] is False


def test_simulation_account_exposes_verified_parsed_fresh_screen_positions(client, test_db):
    _insert_screen_positions(
        test_db,
        positions=[
            {
                "symbol": "SZ300166",
                "name": "东方国信",
                "quantity": 100,
                "sellable_quantity": 100,
                "avg_cost": 18.7,
                "mark_price": 19.2,
                "market_value": 1_920.0,
                "today_pnl": 50.0,
            }
        ],
    )

    body = client.get("/api/simulation/account").json()

    assert body["screen_snapshot_status"] == "available"
    assert body["screen_snapshot_reason"] is None
    assert body["screen_snapshot_scope"] == "full_account"
    assert body["screen_snapshot_as_of"] is not None
    assert body["screen_positions"] == [
        {
            "symbol": "SZ300166",
            "name": "东方国信",
            "quantity": 100,
            "sellable_quantity": 100,
            "avg_cost": 18.7,
            "mark_price": 19.2,
            "market_value": 1_920.0,
            "today_pnl": 50.0,
        }
    ]


@pytest.mark.parametrize(
    ("created_at", "status", "parsed", "expected_reason"),
    [
        (
            datetime.now(timezone.utc) - timedelta(minutes=16),
            "positions_parsed",
            True,
            "screen_positions_evidence_expired",
        ),
        (
            datetime.now(timezone.utc),
            "screen_table_unparsed",
            False,
            "screen_positions_not_parsed",
        ),
    ],
)
def test_simulation_account_does_not_claim_expired_or_unparsed_screen_holdings(
    client,
    test_db,
    created_at,
    status,
    parsed,
    expected_reason,
):
    _insert_screen_positions(
        test_db,
        positions=[{"symbol": "SZ300166", "quantity": 100}],
        created_at=created_at,
        status=status,
        parsed=parsed,
    )

    body = client.get("/api/simulation/account").json()

    assert body["screen_snapshot_status"] == "unavailable"
    assert body["screen_snapshot_reason"] == expected_reason
    assert body["screen_positions"] == []


def test_simulation_account_rejects_malformed_window_verification_json(client, test_db):
    _insert_screen_positions(
        test_db,
        positions=[{"symbol": "SZ300166", "quantity": 100}],
    )
    with test_db.connect() as conn:
        conn.execute(
            """
            UPDATE sim_cockpit_window_verifications
            SET blocked_reasons_json = 'not-json'
            WHERE id = (SELECT MAX(id) FROM sim_cockpit_window_verifications)
            """
        )

    body = client.get("/api/simulation/account").json()

    assert body["screen_snapshot_status"] == "unavailable"
    assert body["screen_snapshot_reason"] == "screen_positions_verification_failed"


def test_simulation_market_read_requests_do_not_run_database_initialization(
    client,
    monkeypatch,
):
    def unexpected_init(_store: SQLiteStore) -> None:
        raise AssertionError("request-time database initialization is forbidden")

    monkeypatch.setattr(SQLiteStore, "init", unexpected_init)

    account_response = client.get("/api/simulation/account")
    flow_response = client.get("/api/market/flow")

    assert account_response.status_code == 200
    assert flow_response.status_code == 200


def test_market_flow_is_unavailable_for_plain_quote_and_never_inferred(client, test_db):
    symbol = "SZ009904"
    _reset_symbol(test_db, symbol)
    with test_db.connect() as conn:
        conn.execute("DELETE FROM capital_flow_snapshots")
    _insert_realtime(
        test_db,
        symbol=symbol,
        price=10.5,
        payload={"price": 10.5, "pct_change": 3.2, "amount": 50_000_000},
    )

    response = client.get("/api/market/flow", params={"symbol": symbol})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["scope"] == "symbol"
    assert body["source"] == "unavailable"
    assert body["as_of"] is None
    assert body["freshness"] == "unavailable"
    assert body["unit"] is None
    assert body["net_inflow"] is None
    assert body["main_inflow"] is None
    assert body["reason"] == "no_verified_capital_flow_source"
    assert body["simulation_only"] is True
    assert body["live_trading_enabled"] is False


def test_market_flow_rejects_self_verified_realtime_payload(client, test_db):
    with test_db.connect() as conn:
        conn.execute("DELETE FROM realtime_market_events")
        conn.execute("DELETE FROM capital_flow_snapshots")
    _insert_realtime(
        test_db,
        symbol="SH000001",
        price=3_500.0,
        payload={
            "event_type": "capital_flow",
            "capital_flow": {
                "scope": "market",
                "unit": "CNY",
                "net_inflow": 188_000_000,
                "main_inflow": 200_000_000,
                "main_outflow": 12_000_000,
            },
        },
    )

    body = client.get("/api/market/flow").json()

    assert body["status"] == "unavailable"
    assert body["reason"] == "no_verified_capital_flow_source"


def test_market_flow_returns_dedicated_auditable_snapshot(client, test_db):
    symbol = "SZ009905"
    _insert_capital_flow_snapshot(
        test_db,
        scope="symbol",
        symbol=symbol,
        main_net=12_000_000,
    )

    response = client.get(f"/api/market/capital-flow/{symbol}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "available"
    assert body["scope"] == "symbol"
    assert body["symbol"] == symbol
    assert body["source"] == "akshare.eastmoney.stock_market_fund_flow"
    assert body["provider"] == "akshare"
    assert body["upstream"] == "eastmoney"
    assert body["endpoint"] == "stock_market_fund_flow"
    assert body["source_semantics"] == "vendor_derived_order_size_classification"
    assert body["freshness"] in {"intraday_vendor_snapshot", "end_of_day"}
    assert body["unit"] == "CNY"
    assert body["main_net_inflow"] == 12_000_000
    assert body["super_large_order_net"] == 100_000_000
    assert body["review_only"] is True
    assert body["simulation_only"] is True
    assert body["live_trading_enabled"] is False


def test_market_flow_query_is_not_displaced_by_ordinary_quote_events(client, test_db):
    with test_db.connect() as conn:
        conn.execute("DELETE FROM realtime_market_events")
    _insert_capital_flow_snapshot(test_db)
    event_ts = datetime.now().isoformat(timespec="seconds")
    with test_db.connect() as conn:
        for index in range(250):
            conn.execute(
                """
                INSERT INTO realtime_market_events(
                    symbol, price, source, provider_status, event_ts, received_ts,
                    quality_status, fallback_used, payload_json, dedupe_key
                )
                VALUES (?, 10.0, 'asharehub', 'ok', ?, ?, 'realtime_ok', 0, '{}', ?)
                """,
                (f"SZ{100000 + index}", event_ts, event_ts, f"ordinary:{index}"),
            )

    body = client.get("/api/market/flow").json()

    assert body["status"] == "available"
    assert body["scope"] == "market"
    assert body["main_net_inflow"] == 188_000_000


def test_market_flow_without_symbol_requires_explicit_market_scope(client, test_db):
    with test_db.connect() as conn:
        conn.execute("DELETE FROM realtime_market_events")
        conn.execute("DELETE FROM capital_flow_snapshots")
    _insert_capital_flow_snapshot(
        test_db,
        scope="symbol",
        symbol="SH000001",
        main_net=99_000_000,
    )

    unavailable = client.get("/api/market/flow").json()

    assert unavailable["status"] == "unavailable"
    assert unavailable["scope"] == "market"
    assert unavailable["main_net_inflow"] is None

    _insert_capital_flow_snapshot(test_db)

    available = client.get("/api/market/flow").json()

    assert available["status"] == "available"
    assert available["scope"] == "market"
    assert available["symbol"] is None
    assert available["main_net_inflow"] == 188_000_000


def test_market_flow_rejects_invalid_symbol(client):
    response = client.get("/api/market/capital-flow/not-a-symbol")

    assert response.status_code == 400
    assert "unsupported A-share symbol" in response.json()["detail"]
