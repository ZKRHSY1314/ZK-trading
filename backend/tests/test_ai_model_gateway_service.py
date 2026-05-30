from app.ai.model_gateway import ModelGatewayResult
from app.ai.model_service import AIModelGatewayService
from app.experience.code_evolution import CodeEvolutionService
from app.storage.sqlite_store import SQLiteStore
from test_code_evolution import _seed_v3_evidence


def _reset_audit_logs(store: SQLiteStore) -> None:
    with store.connect() as conn:
        conn.execute("DELETE FROM ai_model_audit_logs")


def test_ai_model_gateway_capabilities_are_review_only(test_db):
    service = AIModelGatewayService()

    capabilities = service.capabilities()

    assert capabilities["provider"] == "mock_local_rule"
    assert capabilities["external_network"] is False
    assert capabilities["api_key_required"] is False
    assert capabilities["review_only"] is True
    assert capabilities["simulation_only"] is True
    assert capabilities["live_trading_enabled"] is False
    assert "patch" in capabilities["forbidden_outputs"]


def test_explain_code_evolution_writes_audit_and_model_review(test_db):
    _seed_v3_evidence(test_db)
    _reset_audit_logs(test_db)
    record = CodeEvolutionService().generate_review_items(limit=1)["created"][0]

    result = AIModelGatewayService().explain_code_evolution(record["id"])
    updated = CodeEvolutionService().get_record(record["id"])
    audit_logs = AIModelGatewayService().audit_logs(operation="code_evolution_explanation", limit=5)

    assert result["model_review"]["provider"] == "mock_local_rule"
    assert result["model_review"]["response"]["review_only"] is True
    assert "explanation" in result["model_review"]["response"]
    assert "attribution" in result["model_review"]["response"]
    assert "similar_groups" in result["model_review"]["response"]
    assert "validation_request" in result["model_review"]["response"]
    assert updated["status"] == record["status"]
    assert updated["rationale"]["model_review"]["operation"] == "code_evolution_explanation"
    assert audit_logs
    assert audit_logs[0]["operation"] == "code_evolution_explanation"


def test_ai_model_gateway_safety_filter_blocks_dangerous_output(test_db):
    _seed_v3_evidence(test_db)
    record = CodeEvolutionService().generate_review_items(limit=1)["created"][0]

    class DangerousGateway:
        def explain_code_evolution(self, record, context):
            return ModelGatewayResult(
                provider="mock_local_rule",
                operation="code_evolution_explanation",
                prompt={"record_id": record["id"]},
                response={
                    "explanation": {
                        "summary": "run shell apply_patch then git push broker order credential live_trading"
                    },
                    "attribution": {"tags": ["unsafe"]},
                    "similar_groups": [],
                    "validation_request": {"required_checks": ["pytest"]},
                    "patch": {"unsafe": True},
                },
                safety={"safety_blocks_applied": [], "live_trading_enabled": False},
            )

    result = AIModelGatewayService(gateway=DangerousGateway()).explain_code_evolution(record["id"])
    model_review = result["model_review"]

    assert model_review["response"]["explanation"]["summary"] == "[blocked by V3.5 safety filter]"
    assert "patch" not in model_review["response"]
    assert "apply_patch" in model_review["safety"]["blocked_terms"]
    assert any("unexpected_output_keys_removed:patch" in block for block in model_review["safety"]["safety_blocks_applied"])


def test_ai_model_gateway_api_smoke(client, test_db):
    _seed_v3_evidence(test_db)
    record = CodeEvolutionService().generate_review_items(limit=1)["created"][0]

    capabilities_resp = client.get("/api/ai/model/capabilities")
    explain_resp = client.post(f"/api/ai/model/explain-code-evolution/{record['id']}")
    audit_resp = client.get("/api/ai/model/audit-logs?operation=code_evolution_explanation&limit=5")

    assert capabilities_resp.status_code == 200
    assert capabilities_resp.json()["provider"] == "mock_local_rule"
    assert explain_resp.status_code == 200
    assert explain_resp.json()["model_review"]["response"]["simulation_only"] is True
    assert audit_resp.status_code == 200
    assert audit_resp.json()
    assert client.get("/health").json()["live_trading_enabled"] is False
