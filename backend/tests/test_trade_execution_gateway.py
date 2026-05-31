from app.config import settings
from app.trade_execution.gateway import TradeExecutionGatewayService


def test_trade_execution_gateway_capabilities_are_review_only():
    data = TradeExecutionGatewayService().capabilities()

    assert data["stage"] == "V5.0-P1"
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
    assert "manual_confirmation_contract_review" in data["allowed_modes"]
    assert "place_real_trade" in data["forbidden_modes"]
    components = {item["name"]: item for item in data["required_future_components"]}
    assert components["ManualConfirmationContract"]["status"] == "review_contract_defined"
    assert components["ExecutionAuditLedger"]["status"] == "review_schema_defined_not_persisted"
    assert data["safety_summary"]["places_real_trade"] is False
    assert data["safety_summary"]["connects_broker"] is False


def test_trade_execution_gateway_review_gates_require_future_contracts():
    data = TradeExecutionGatewayService().review_gates()
    gates = {gate["name"]: gate for gate in data["gates"]}

    assert data["stage"] == "V5.0-P1"
    assert data["status"] == "review_required"
    assert gates["live_trading_disabled"]["status"] == "passed"
    assert gates["broker_adapter_absent"]["status"] == "passed"
    assert gates["credential_storage_absent"]["status"] == "passed"
    assert gates["human_confirmation_required"]["status"] == "passed"
    assert gates["risk_gate_contract_required"]["status"] == "review_required"
    assert gates["audit_and_rollback_required"]["value"] == "audit_schema_review_ready_without_rollback"
    assert data["decision"]["gateway_can_execute"] is False
    assert data["decision"]["manual_confirmation_contract_ready"] is True
    assert data["decision"]["audit_contract_ready"] is True
    assert data["decision"]["live_trading_enabled"] is False
    assert data["safety_summary"]["real_money_execution_enabled"] is False


def test_manual_confirmation_contract_is_review_only():
    data = TradeExecutionGatewayService().manual_confirmation_contract()
    input_names = {item["name"] for item in data["required_operator_inputs"]}

    assert data["schema_version"] == "trade_execution_manual_confirmation_contract.v1"
    assert data["stage"] == "V5.0-P1"
    assert data["status"] == "confirmation_contract_review_ready"
    assert data["contract_state"] == "defined_for_review_only"
    assert "operator_id" in input_names
    assert "confirmation_phrase" in input_names
    assert "proposal_hash" in input_names
    assert "risk_snapshot_hash" in input_names
    assert data["expiry_policy"]["confirmation_ttl_seconds"] == 120
    assert data["decision"]["contract_ready_for_review"] is True
    assert data["decision"]["contract_allows_execution_now"] is False
    assert "broker_password" in data["forbidden_inputs"]
    assert data["safety_summary"]["places_real_trade"] is False
    assert data["live_trading_enabled"] is False


def test_audit_evidence_schema_is_not_persisted_or_migrated():
    data = TradeExecutionGatewayService().audit_evidence_schema()
    fields = {item["name"]: item for item in data["fields"]}

    assert data["schema_version"] == "trade_execution_audit_evidence_schema.v1"
    assert data["stage"] == "V5.0-P1"
    assert data["status"] == "audit_schema_review_ready"
    assert data["storage_state"] == "not_persisted"
    assert data["target_future_table"] == "trade_execution_audit_ledger"
    assert data["create_table_now"] is False
    assert data["writes_database_now"] is False
    assert "event_hash" in fields
    assert "previous_event_hash" in fields
    assert "operator_id_hash" in fields
    assert "broker_password" in data["excluded_sensitive_fields"]
    assert "previous_event_hash_chain" in data["immutability_rules"]
    assert data["decision"]["schema_ready_for_review"] is True
    assert data["decision"]["schema_allows_execution_now"] is False
    assert data["decision"]["migration_allowed_now"] is False
    assert data["safety_summary"]["runs_migration_now"] is False
    assert data["safety_summary"]["writes_database_now"] is False


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
    contract_resp = client.get("/api/trade-execution-gateway/manual-confirmation-contract")
    audit_schema_resp = client.get("/api/trade-execution-gateway/audit-evidence-schema")
    health_resp = client.get("/health")

    assert caps_resp.status_code == 200
    assert gates_resp.status_code == 200
    assert contract_resp.status_code == 200
    assert audit_schema_resp.status_code == 200
    assert health_resp.status_code == 200
    assert caps_resp.json()["status"] == "review_only_ready"
    assert caps_resp.json()["execution_enabled"] is False
    assert caps_resp.json()["broker_adapter_enabled"] is False
    assert gates_resp.json()["decision"]["gateway_can_execute"] is False
    assert gates_resp.json()["decision"]["manual_confirmation_contract_ready"] is True
    assert contract_resp.json()["decision"]["contract_allows_execution_now"] is False
    assert audit_schema_resp.json()["writes_database_now"] is False
    assert audit_schema_resp.json()["decision"]["migration_allowed_now"] is False
    assert gates_resp.json()["blocked_gate_count"] == 0
    assert health_resp.json()["live_trading_enabled"] is False
