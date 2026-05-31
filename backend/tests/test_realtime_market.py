from datetime import datetime, timedelta

from app.realtime.monitoring_bridge import RealtimeMonitoringBridge
from app.realtime.providers import MockRealtimeMarketProvider, RealtimeQuote
from app.realtime.service import RealtimeMarketService


def _reset_realtime(store) -> None:
    with store.connect() as conn:
        conn.execute("DELETE FROM monitoring_alerts")
        conn.execute("DELETE FROM monitoring_events")
        conn.execute("DELETE FROM monitoring_sessions")
        conn.execute("DELETE FROM realtime_cycle_runs")
        conn.execute("DELETE FROM realtime_market_events")
        conn.execute("DELETE FROM realtime_provider_health")


def _quote(
    symbol: str = "SZ002081",
    price: float = 10.0,
    seconds_ago: int = 1,
    provider_status: str = "ok",
) -> RealtimeQuote:
    return RealtimeQuote(
        symbol=symbol,
        name="金螳螂",
        price=price,
        volume=10000,
        amount=100000,
        source="mock_local_rule",
        event_ts=datetime.now() - timedelta(seconds=seconds_ago),
        quality_status="mock_realtime",
        provider_status=provider_status,
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


def test_refresh_symbols_disabled_provider_does_not_write_fake_events(test_db):
    _reset_realtime(test_db)
    service = RealtimeMarketService()

    result = service.refresh_symbols(["SZ002081", "SZ002115"], limit=20)
    events = service.list_events(limit=10)

    assert result["status"] == "fallback_required"
    assert result["configured"] is False
    assert result["refreshed_count"] == 0
    assert result["failed_count"] == 2
    assert events == []
    assert result["live_trading_enabled"] is False


def test_mock_refresh_symbols_writes_multi_symbol_events(test_db):
    _reset_realtime(test_db)
    provider = MockRealtimeMarketProvider(
        [
            _quote(symbol="SZ002081", price=10.0, seconds_ago=2),
            _quote(symbol="SZ002115", price=20.0, seconds_ago=2),
        ]
    )
    service = RealtimeMarketService(provider=provider)

    result = service.refresh_symbols(["SZ002081", "SZ002115"], limit=20)
    events = service.list_events(limit=10)

    assert result["status"] == "completed"
    assert result["refreshed_count"] == 2
    assert {event["symbol"] for event in events} == {"SZ002081", "SZ002115"}
    assert any(item["provider"] == "mock_local_rule" for item in service.provider_health())


def test_realtime_monitoring_bridge_creates_price_jump_alert(test_db):
    _reset_realtime(test_db)
    service = RealtimeMarketService(provider=MockRealtimeMarketProvider())
    base_ts = datetime.now() - timedelta(seconds=10)
    service.ingest_quote(
        RealtimeQuote(symbol="SZ002081", price=10.0, source="mock_local_rule", event_ts=base_ts)
    )
    second = service.ingest_quote(
        RealtimeQuote(
            symbol="SZ002081",
            price=10.4,
            source="mock_local_rule",
            event_ts=base_ts + timedelta(seconds=1),
        )
    )

    result = RealtimeMonitoringBridge().sync(limit=100)
    alerts = test_db.fetch_all("SELECT alert_type, payload_json FROM monitoring_alerts")

    assert result["created_event_count"] == 2
    assert result["created_alert_count"] == 1
    assert alerts[0]["alert_type"] == "realtime_price_jump"
    assert f'"source_event_id": {second["id"]}' in alerts[0]["payload_json"]


def test_realtime_monitoring_bridge_creates_stale_and_degraded_alerts(test_db):
    _reset_realtime(test_db)
    service = RealtimeMarketService(provider=MockRealtimeMarketProvider())
    service.ingest_quote(_quote(symbol="SZ002081", price=10.0, seconds_ago=120, provider_status="degraded"))

    result = RealtimeMonitoringBridge().sync(limit=100)
    alert_types = {row["alert_type"] for row in test_db.fetch_all("SELECT alert_type FROM monitoring_alerts")}

    assert result["created_alert_count"] == 2
    assert "realtime_stale_data" in alert_types
    assert "realtime_provider_degraded" in alert_types


def test_realtime_monitoring_bridge_dedupes_repeated_sync(test_db):
    _reset_realtime(test_db)
    service = RealtimeMarketService(provider=MockRealtimeMarketProvider())
    service.ingest_quote(_quote(symbol="SZ002081", price=10.0, seconds_ago=10))
    service.ingest_quote(_quote(symbol="SZ002081", price=10.4, seconds_ago=9))

    first = RealtimeMonitoringBridge().sync(limit=100)
    second = RealtimeMonitoringBridge().sync(limit=100)
    alerts = test_db.fetch_all("SELECT * FROM monitoring_alerts")

    assert first["created_alert_count"] == 1
    assert second["created_event_count"] == 0
    assert second["created_alert_count"] == 0
    assert len(alerts) == 1


def test_realtime_cycle_runs_refresh_sync_and_replay_summary(test_db):
    _reset_realtime(test_db)
    service = RealtimeMarketService(provider=MockRealtimeMarketProvider())
    service.ingest_quote(_quote(symbol="SZ002081", price=10.0, seconds_ago=10))
    cycle_service = RealtimeMarketService(
        provider=MockRealtimeMarketProvider(
            [_quote(symbol="SZ002081", price=10.4, seconds_ago=1)]
        )
    )

    result = cycle_service.run_cycle(symbols=["SZ002081"], refresh_limit=10, sync_limit=100, replay_limit=100)

    assert result["status"] == "review_required"
    assert result["summary"]["refreshed_count"] == 1
    assert result["summary"]["created_alert_count"] == 1
    assert result["summary"]["replay_event_count"] == 2
    assert result["summary"]["signal_counts"]["momentum_up"] == 1
    assert result["steps"]["replay"]["summary"]["symbol_count"] == 1
    assert result["live_trading_enabled"] is False
    assert isinstance(result["run_id"], int)
    latest = cycle_service.latest_cycle_run()
    runs = cycle_service.list_cycle_runs(limit=5)
    assert latest["id"] == result["run_id"]
    assert latest["summary"]["created_alert_count"] == 1
    assert latest["symbols"] == ["SZ002081"]
    assert len(runs) == 1


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
    assert replay["summary"]["signal_counts"]["momentum_up"] == 1
    assert replay["summary"]["signal_counts"]["momentum_down"] == 1
    assert replay["summary"]["quality_counts"]["mock_realtime"] == 3
    assert replay["live_trading_enabled"] is False


def test_realtime_api_smoke(client, test_db):
    _reset_realtime(test_db)
    RealtimeMarketService(provider=MockRealtimeMarketProvider()).ingest_quote(_quote(price=9.8))

    capabilities_resp = client.get("/api/realtime/capabilities")
    health_resp = client.get("/api/realtime/provider-health")
    snapshot_resp = client.get("/api/realtime/snapshot/SZ002081")
    events_resp = client.get("/api/realtime/events?symbol=SZ002081&limit=5")
    refresh_resp = client.post("/api/realtime/refresh?symbols=SZ002081,SZ002115&limit=5")
    sync_resp = client.post("/api/realtime/monitoring-sync?limit=5")
    alerts_resp = client.get("/api/monitoring/alerts?limit=5")
    cycle_resp = client.post("/api/realtime/cycle?symbols=SZ002081,SZ002115&refresh_limit=5&sync_limit=5&replay_limit=5")
    cycles_resp = client.get("/api/realtime/cycles?limit=5")
    latest_cycle_resp = client.get("/api/realtime/cycles/latest")
    replay_resp = client.post("/api/realtime/replay?symbol=SZ002081&limit=5")

    assert capabilities_resp.status_code == 200
    assert health_resp.status_code == 200
    assert snapshot_resp.status_code == 200
    assert events_resp.status_code == 200
    assert refresh_resp.status_code == 200
    assert sync_resp.status_code == 200
    assert alerts_resp.status_code == 200
    assert cycle_resp.status_code == 200
    assert cycles_resp.status_code == 200
    assert latest_cycle_resp.status_code == 200
    assert replay_resp.status_code == 200
    assert snapshot_resp.json()["event"]["symbol"] == "SZ002081"
    assert events_resp.json()
    assert refresh_resp.json()["live_trading_enabled"] is False
    assert sync_resp.json()["simulation_only"] is True
    assert isinstance(alerts_resp.json(), list)
    assert cycle_resp.json()["summary"]["fallback_required"] is True
    assert cycles_resp.json()[0]["id"] == cycle_resp.json()["run_id"]
    assert latest_cycle_resp.json()["id"] == cycle_resp.json()["run_id"]
    assert replay_resp.json()["simulation_only"] is True
    assert client.get("/health").json()["live_trading_enabled"] is False
