from app.screen_monitoring.providers import LocalSafeScreenCaptureProvider
from app.screen_monitoring.service import ScreenMonitoringService


def _reset_screen_monitoring(store) -> None:
    with store.connect() as conn:
        conn.execute("DELETE FROM screen_observations")
        conn.execute("DELETE FROM screen_monitoring_sessions")


def test_screen_monitoring_capabilities_are_read_only(test_db):
    _reset_screen_monitoring(test_db)
    capabilities = ScreenMonitoringService().capabilities()

    assert capabilities["stage"] == "V4.5-P1"
    assert capabilities["capture_provider"] == "disabled"
    assert capabilities["provider_status"] == "disabled"
    assert capabilities["provider_configured"] is False
    assert capabilities["ocr_provider"] == "not_configured"
    assert capabilities["provider_capabilities"]["capture_supported"] is False
    assert capabilities["review_only"] is True
    assert capabilities["simulation_only"] is True
    assert capabilities["live_trading_enabled"] is False
    assert "screen_click" in capabilities["forbidden_modes"]
    assert "order_action" in capabilities["forbidden_modes"]
    assert "fixture_replay" in capabilities["allowed_modes"]


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


def test_screen_fixture_replay_records_observation_without_real_capture(test_db):
    _reset_screen_monitoring(test_db)
    service = ScreenMonitoringService()

    result = service.replay_fixture("trading_client_warning_popup")
    latest = service.latest_session()

    assert result["status"] == "replayed"
    assert result["provider"] == "fixture"
    assert result["real_screen_capture"] is False
    assert result["ocr_executed"] is False
    assert result["live_trading_enabled"] is False
    assert result["observation"]["app_status"] == "attention_required"
    assert result["observation"]["raw_payload"]["fixture_replay"] is True
    assert result["observation"]["raw_payload"]["ocr_executed"] is False
    assert latest["summary"]["observation_count"] == 1
    assert latest["summary"]["status_counts"]["attention_required"] == 1


def test_screen_provider_capabilities_include_fixture_but_default_disabled(test_db):
    _reset_screen_monitoring(test_db)
    providers = ScreenMonitoringService().provider_capabilities()
    by_provider = {item["provider"]: item for item in providers}

    assert by_provider["disabled"]["configured"] is False
    assert by_provider["disabled"]["capture_supported"] is False
    assert by_provider["fixture"]["configured"] is True
    assert by_provider["fixture"]["fixture_replay_supported"] is True
    assert by_provider["fixture"]["details"]["real_screen_capture"] is False
    assert all(item["live_trading_enabled"] is False for item in providers)


def test_local_safe_preflight_requires_explicit_config(test_db):
    _reset_screen_monitoring(test_db)
    provider = LocalSafeScreenCaptureProvider(
        allow_real_capture=False,
        allowed_windows=["Notepad"],
        broker_window_terms=["trading", "证券"],
    )
    service = ScreenMonitoringService(provider=provider)

    result = service.capture_preflight("Notepad")

    assert result["status"] == "blocked"
    assert result["reason"] == "real_capture_not_explicitly_enabled"
    assert result["capture_would_be_allowed"] is False
    assert result["real_screen_capture"] is False
    assert result["ocr_executed"] is False
    assert result["observation"]["app_status"] == "capture_preflight_blocked"
    assert result["live_trading_enabled"] is False


def test_local_safe_preflight_blocks_broker_windows_even_if_allowlisted(test_db):
    _reset_screen_monitoring(test_db)
    provider = LocalSafeScreenCaptureProvider(
        allow_real_capture=True,
        allowed_windows=["Mock", "Trading"],
        broker_window_terms=["trading", "证券"],
    )
    service = ScreenMonitoringService(provider=provider)

    result = service.capture_preflight("Mock Trading Client")

    assert result["status"] == "blocked"
    assert result["reason"] == "broker_or_trading_window_blocked"
    assert "trading" in result["matched_terms"]
    assert result["capture_would_be_allowed"] is False
    assert result["real_screen_capture"] is False
    assert result["observation"]["warnings"] == ["broker_or_trading_window_blocked"]


def test_local_safe_preflight_passes_harmless_allowlisted_window(test_db):
    _reset_screen_monitoring(test_db)
    provider = LocalSafeScreenCaptureProvider(
        allow_real_capture=True,
        allowed_windows=["Notepad", "Calculator"],
        broker_window_terms=["trading", "证券"],
    )
    service = ScreenMonitoringService(provider=provider)

    result = service.capture_preflight("Untitled - Notepad")
    latest = service.latest_session()

    assert result["status"] == "preflight_passed"
    assert result["reason"] == "harmless_window_allowlisted"
    assert result["capture_would_be_allowed"] is True
    assert result["real_screen_capture"] is False
    assert result["ocr_executed"] is False
    assert result["redaction_required"] is True
    assert result["operator_review_required"] is True
    assert result["observation"]["app_status"] == "capture_preflight_ready"
    assert latest["summary"]["status_counts"]["capture_preflight_ready"] == 1


def test_screen_monitoring_api_smoke(client, test_db):
    _reset_screen_monitoring(test_db)

    capabilities_resp = client.get("/api/screen-monitoring/capabilities")
    providers_resp = client.get("/api/screen-monitoring/providers")
    empty_latest_resp = client.get("/api/screen-monitoring/sessions/latest")
    session_resp = client.post(
        "/api/screen-monitoring/sessions",
        json={"name": "test_screen_watch", "source": "mock", "window_title": "Mock Trading Client"},
    )
    observation_resp = client.post("/api/screen-monitoring/observations/mock")
    fixture_resp = client.post(
        "/api/screen-monitoring/observations/fixture-replay",
        json={"fixture_name": "trading_client_online"},
    )
    preflight_resp = client.post(
        "/api/screen-monitoring/capture-preflight",
        json={"target_window_title": "Mock Trading Client"},
    )
    observations_resp = client.get("/api/screen-monitoring/observations?limit=5")
    latest_resp = client.get("/api/screen-monitoring/sessions/latest")

    assert capabilities_resp.status_code == 200
    assert providers_resp.status_code == 200
    assert empty_latest_resp.status_code == 200
    assert session_resp.status_code == 200
    assert observation_resp.status_code == 200
    assert fixture_resp.status_code == 200
    assert preflight_resp.status_code == 200
    assert observations_resp.status_code == 200
    assert latest_resp.status_code == 200
    assert capabilities_resp.json()["live_trading_enabled"] is False
    assert capabilities_resp.json()["provider_configured"] is False
    assert any(item["provider"] == "fixture" for item in providers_resp.json())
    assert empty_latest_resp.json()["status"] == "empty"
    assert session_resp.json()["status"] == "running"
    assert observation_resp.json()["review_only"] is True
    assert observation_resp.json()["simulation_only"] is True
    assert observation_resp.json()["live_trading_enabled"] is False
    assert fixture_resp.json()["real_screen_capture"] is False
    assert fixture_resp.json()["ocr_executed"] is False
    assert fixture_resp.json()["observation"]["raw_payload"]["fixture_replay"] is True
    assert preflight_resp.json()["status"] == "blocked"
    assert preflight_resp.json()["capture_would_be_allowed"] is False
    assert preflight_resp.json()["real_screen_capture"] is False
    assert observations_resp.json()
    assert latest_resp.json()["summary"]["observation_count"] == 3
    assert client.get("/health").json()["live_trading_enabled"] is False
