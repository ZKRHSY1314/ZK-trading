from datetime import datetime, timedelta

from app.realtime.providers import MockRealtimeMarketProvider, RealtimeQuote
from app.realtime.service import RealtimeMarketService


def _reset_realtime(store) -> None:
    with store.connect() as conn:
        conn.execute("DELETE FROM realtime_market_events")
        conn.execute("DELETE FROM realtime_provider_health")


def _quote(symbol: str = "SZ002081", price: float = 10.0, seconds_ago: int = 1) -> RealtimeQuote:
    return RealtimeQuote(
        symbol=symbol,
        name="金螳螂",
        price=price,
        volume=10000,
        amount=100000,
        source="mock_local_rule",
        event_ts=datetime.now() - timedelta(seconds=seconds_ago),
        quality_status="mock_realtime",
        payload={"fixture": True},
    )


def test_realtime_capabilities_are_disabled_by_default(test_db):
    _reset_realtime(test_db)
    service = RealtimeMarketService()

    capabilities = service.capabilities()
    health = service.provider_health()

    assert capabilities["active_provider"] == "disabled"
    assert capabilities["review_only"] is True
    assert capabilities["simulation_only"] is True
    assert capabilities["live_trading_enabled"] is False
    assert "order_action" in capabilities["forbidden_modes"]
    assert any(item["provider"] == "asharehub" and item["quality_status"] == "needs_config" for item in health)
    assert any(item["provider"] == "akshare_fallback" for item in health)


def test_mock_realtime_event_updates_cache_and_latency(test_db):
    _reset_realtime(test_db)
    service = RealtimeMarketService(provider=MockRealtimeMarketProvider())

    event = service.ingest_quote(_quote(price=10.5))
    snapshot = service.latest_snapshot("SZ002081")
    events = service.list_events(symbol="SZ002081")

    assert event["inserted"] is True
    assert event["quality_status"] == "mock_realtime"
    assert event["latency_ms"] >= 0
    assert snapshot["status"] == "degraded"
    assert snapshot["event"]["price"] == 10.5
    assert len(events) == 1


def test_realtime_event_dedupe_blocks_same_source_symbol_second(test_db):
    _reset_realtime(test_db)
    service = RealtimeMarketService(provider=MockRealtimeMarketProvider())
    first = _quote(price=10.0)
    duplicate = RealtimeQuote(
        symbol=first.symbol,
        name=first.name,
        price=10.2,
        volume=first.volume,
        amount=first.amount,
        source=first.source,
        event_ts=first.event_ts,
        quality_status=first.quality_status,
    )

    first_event = service.ingest_quote(first)
    duplicate_event = service.ingest_quote(duplicate)

    assert first_event["inserted"] is True
    assert duplicate_event["inserted"] is False
    assert len(service.list_events(symbol=first.symbol)) == 1


def test_realtime_provider_failure_records_fallback_status(test_db):
    _reset_realtime(test_db)

    class FailingProvider:
        name = "failing_provider"

        def configured(self):
            return True

        def health(self):
            return {
                "provider": self.name,
                "status": "ready",
                "configured": True,
                "quality_status": "ready",
                "last_error": None,
                "details": {},
            }

        def fetch_quote(self, symbol: str):
            raise RuntimeError("upstream timeout")

    service = RealtimeMarketService(provider=FailingProvider())

    result = service.refresh_quote("SZ002081")
    health = service.provider_health()

    assert result["status"] == "degraded"
    assert result["quality_status"] == "fallback_required"
    assert result["fallback_provider"] == "akshare_fallback"
    assert any(item["provider"] == "failing_provider" and item["status"] == "degraded" for item in health)


def test_realtime_replay_orders_events_and_generates_signals(test_db):
    _reset_realtime(test_db)
    service = RealtimeMarketService(provider=MockRealtimeMarketProvider())
    base_ts = datetime.now() - timedelta(seconds=10)
    for idx, price in enumerate([10.0, 10.5, 10.1]):
        service.ingest_quote(
            RealtimeQuote(
                symbol="SZ002081",
                price=price,
                source="mock_local_rule",
                event_ts=base_ts + timedelta(seconds=idx),
                quality_status="mock_realtime",
            )
        )

    replay = service.replay(symbol="SZ002081")

    assert replay["status"] == "replayed"
    assert replay["event_count"] == 3
    assert [signal["signal_type"] for signal in replay["signals"]] == [
        "observe",
        "momentum_up",
        "momentum_down",
    ]
    assert replay["live_trading_enabled"] is False


def test_realtime_api_smoke(client, test_db):
    _reset_realtime(test_db)
    RealtimeMarketService(provider=MockRealtimeMarketProvider()).ingest_quote(_quote(price=9.8))

    capabilities_resp = client.get("/api/realtime/capabilities")
    health_resp = client.get("/api/realtime/provider-health")
    snapshot_resp = client.get("/api/realtime/snapshot/SZ002081")
    events_resp = client.get("/api/realtime/events?symbol=SZ002081&limit=5")
    replay_resp = client.post("/api/realtime/replay?symbol=SZ002081&limit=5")

    assert capabilities_resp.status_code == 200
    assert health_resp.status_code == 200
    assert snapshot_resp.status_code == 200
    assert events_resp.status_code == 200
    assert replay_resp.status_code == 200
    assert snapshot_resp.json()["event"]["symbol"] == "SZ002081"
    assert events_resp.json()
    assert replay_resp.json()["simulation_only"] is True
    assert client.get("/health").json()["live_trading_enabled"] is False
