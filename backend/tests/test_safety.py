from app.config import settings

def test_live_trading_is_disabled():
    assert settings.enable_live_trading is False

def test_health_reports_safe_state(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["live_trading_enabled"] is False

def test_capabilities_report_safe_state(client):
    resp = client.get("/api/automation/capabilities")
    assert resp.status_code == 200
    data = resp.json()
    assert data["live_trading_enabled"] is False

def test_start_automation_with_live_trading_fails(client):
    resp = client.post("/api/automation/runs/start?mode=live_trading")
    # Our API doesn't support live_trading mode
    assert resp.status_code in (400, 422, 500)
    
    if resp.status_code == 400:
        assert "live" in resp.json().get("detail", "").lower() or "not supported" in resp.json().get("detail", "").lower()
