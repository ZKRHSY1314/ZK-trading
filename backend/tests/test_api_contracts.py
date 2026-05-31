def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "live_trading_enabled" in data

def test_knowledge_summary(client):
    resp = client.get("/api/knowledge/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "principles" in data

def test_candidates_scores(client):
    resp = client.get("/api/candidates/scores?limit=10")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

def test_automation_capabilities(client):
    resp = client.get("/api/automation/capabilities")
    assert resp.status_code == 200
    data = resp.json()
    assert data["live_trading_enabled"] is False

def test_trade_execution_gateway_capabilities(client):
    resp = client.get("/api/trade-execution-gateway/capabilities")
    assert resp.status_code == 200
    data = resp.json()
    assert data["stage"] == "V5.0-P0"
    assert data["review_only"] is True
    assert data["simulation_only"] is True
    assert data["execution_enabled"] is False
    assert data["live_trading_enabled"] is False

def test_learning_summary(client):
    resp = client.get("/api/learning/summary")
    assert resp.status_code == 200
    assert "sample_counts" in resp.json()
