from app.screen_monitoring.service import ScreenMonitoringService


def _reset_screen_monitoring(store) -> None:
    with store.connect() as conn:
        conn.execute("DELETE FROM screen_observations")
        conn.execute("DELETE FROM screen_monitoring_sessions")


def test_screen_monitoring_capabilities_are_read_only(test_db):
    _reset_screen_monitoring(test_db)
    capabilities = ScreenMonitoringService().capabilities()

    assert capabilities["stage"] == "V4.5-P0"
    assert capabilities["capture_provider"] == "manual_or_mock_only"
    assert capabilities["ocr_provider"] == "not_configured"
    assert capabilities["review_only"] is True
    assert capabilities["simulation_only"] is True
    assert capabilities["live_trading_enabled"] is False
    assert "screen_click" in capabilities["forbidden_modes"]
    assert "order_action" in capabilities["forbidden_modes"]


def test_screen_observation_creates_session_and_summary(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()

    observation = service.record_observation(
        source="mock",
        app_status="online",
        window_title="Mock Trading Client",
        confidence=0.8,
        detected_items=[{"type": "window_status", "value": "online"}],
        raw_payload={"fixture": True, "read_only": True},
    )
    latest = service.latest_session()
    observations = service.list_observations()

    assert observation["inserted"] is True
    assert observation["app_status"] == "online"
    assert observation["live_trading_enabled"] is False
    assert latest["status"] == "running"
    assert latest["summary"]["observation_count"] == 1
    assert latest["summary"]["status_counts"]["online"] == 1
    assert observations[0]["id"] == observation["id"]


def test_screen_observation_dedupes_same_observation(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()
    session = service.start_session(window_title="Mock Trading Client")

    first = service.record_observation(
        session_id=session["id"],
        source="mock",
        app_status="online",
        window_title="Mock Trading Client",
        confidence=0.8,
        observed_at="2026-05-31T10:00:00",
        detected_items=[{"type": "window_status", "value": "online"}],
    )
    second = service.record_observation(
        session_id=session["id"],
        source="mock",
        app_status="online",
        window_title="Mock Trading Client",
        confidence=0.8,
        observed_at="2026-05-31T10:00:00",
        detected_items=[{"type": "window_status", "value": "online"}],
    )

    assert first["inserted"] is True
    assert second["inserted"] is False
    assert len(service.list_observations()) == 1


def test_screen_observation_safety_blocks_dangerous_payload_terms(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()

    observation = service.record_observation(
        source="manual",
        app_status="online",
        raw_payload={"requested_action": "click submit_order"},
    )

    assert observation["live_trading_enabled"] is False
    assert observation["raw_payload"]["blocked_from_execution"] is True
    assert any("click" in item for item in observation["warnings"])
    assert any("submit_order" in item for item in observation["warnings"])


def test_screen_monitoring_api_smoke(client, test_db):
    _reset_screen_monitoring(test_db)

    capabilities_resp = client.get("/api/screen-monitoring/capabilities")
    empty_latest_resp = client.get("/api/screen-monitoring/sessions/latest")
    session_resp = client.post(
        "/api/screen-monitoring/sessions",
        json={"name": "test_screen_watch", "source": "mock", "window_title": "Mock Trading Client"},
    )
    observation_resp = client.post("/api/screen-monitoring/observations/mock")
    observations_resp = client.get("/api/screen-monitoring/observations?limit=5")
    latest_resp = client.get("/api/screen-monitoring/sessions/latest")

    assert capabilities_resp.status_code == 200
    assert empty_latest_resp.status_code == 200
    assert session_resp.status_code == 200
    assert observation_resp.status_code == 200
    assert observations_resp.status_code == 200
    assert latest_resp.status_code == 200
    assert capabilities_resp.json()["live_trading_enabled"] is False
    assert empty_latest_resp.json()["status"] == "empty"
    assert session_resp.json()["status"] == "running"
    assert observation_resp.json()["review_only"] is True
    assert observation_resp.json()["simulation_only"] is True
    assert observation_resp.json()["live_trading_enabled"] is False
    assert observations_resp.json()
    assert latest_resp.json()["summary"]["observation_count"] == 1
    assert client.get("/health").json()["live_trading_enabled"] is False
