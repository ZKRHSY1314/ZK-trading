from app.config import settings
from app.trade_execution.gateway import TradeExecutionGatewayService


def test_trade_execution_gateway_capabilities_are_review_only():
    data = TradeExecutionGatewayService().capabilities()

    assert data["stage"] == "V5.0-P0"
    assert data["status"] == "review_only_ready"
    assert data["gateway_enabled"] is False
    assert data["execution_enabled"] is False
    assert data["real_money_execution_enabled"] is False
    assert data["broker_adapter_enabled"] is False
    assert data["credential_storage_enabled"] is False
    assert data["screen_click_trading_enabled"] is False
    assert data["live_trading_enabled"] is False
    assert data["review_only"] is True
    assert data["simulation_only"] is True
    assert "architecture_review" in data["allowed_modes"]
    assert "place_real_trade" in data["forbidden_modes"]
    assert data["safety_summary"]["places_real_trade"] is False
    assert data["safety_summary"]["connects_broker"] is False


def test_trade_execution_gateway_review_gates_require_future_contracts():
    data = TradeExecutionGatewayService().review_gates()
    gates = {gate["name"]: gate for gate in data["gates"]}

    assert data["stage"] == "V5.0-P0"
    assert data["status"] == "review_required"
    assert gates["live_trading_disabled"]["status"] == "passed"
    assert gates["broker_adapter_absent"]["status"] == "passed"
    assert gates["credential_storage_absent"]["status"] == "passed"
    assert gates["human_confirmation_required"]["status"] == "review_required"
    assert gates["risk_gate_contract_required"]["status"] == "review_required"
    assert data["decision"]["gateway_can_execute"] is False
    assert data["decision"]["live_trading_enabled"] is False
    assert data["safety_summary"]["real_money_execution_enabled"] is False


def test_trade_execution_gateway_blocks_if_live_trading_flag_is_enabled():
    original = settings.enable_live_trading
    try:
        settings.enable_live_trading = True
        data = TradeExecutionGatewayService().capabilities()
        gates = {gate["name"]: gate for gate in TradeExecutionGatewayService().review_gates()["gates"]}
    finally:
        settings.enable_live_trading = original

    assert data["status"] == "blocked_by_safety_gate"
    assert data["live_trading_enabled"] is True
    assert gates["live_trading_disabled"]["status"] == "blocked"


def test_trade_execution_gateway_api_smoke(client):
    caps_resp = client.get("/api/trade-execution-gateway/capabilities")
    gates_resp = client.get("/api/trade-execution-gateway/review-gates")
    health_resp = client.get("/health")

    assert caps_resp.status_code == 200
    assert gates_resp.status_code == 200
    assert health_resp.status_code == 200
    assert caps_resp.json()["status"] == "review_only_ready"
    assert caps_resp.json()["execution_enabled"] is False
    assert caps_resp.json()["broker_adapter_enabled"] is False
    assert gates_resp.json()["decision"]["gateway_can_execute"] is False
    assert gates_resp.json()["blocked_gate_count"] == 0
    assert health_resp.json()["live_trading_enabled"] is False
