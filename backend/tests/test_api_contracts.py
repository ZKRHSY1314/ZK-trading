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
    assert data["stage"] == "V5.5-P5"
    assert data["review_only"] is True
    assert data["simulation_only"] is True
    assert data["execution_enabled"] is False
    assert data["live_trading_enabled"] is False

def test_trade_execution_gateway_p1_v55_contracts(client):
    contract_resp = client.get("/api/trade-execution-gateway/manual-confirmation-contract")
    audit_resp = client.get("/api/trade-execution-gateway/audit-evidence-schema")
    risk_resp = client.get("/api/trade-execution-gateway/risk-gate-contract")
    rollback_resp = client.get("/api/trade-execution-gateway/rollback-runbook")
    pre_live_resp = client.get("/api/trade-execution-gateway/pre-live-review-package")
    checklist_resp = client.get("/api/trade-execution-gateway/operator-acceptance-checklist")
    release_gate_resp = client.get("/api/trade-execution-gateway/disabled-release-gate")
    final_report_resp = client.get("/api/trade-execution-gateway/final-readiness-report")
    threat_model_resp = client.get("/api/trade-execution-gateway/broker-adapter-threat-model")
    interface_draft_resp = client.get("/api/trade-execution-gateway/broker-adapter-interface-draft")
    contract_verification_resp = client.get("/api/trade-execution-gateway/broker-adapter-contract-verification")
    order_failure_resp = client.get("/api/trade-execution-gateway/order-lifecycle-failure-fixtures")
    runbook_mapping_resp = client.get("/api/trade-execution-gateway/order-failure-runbook-mapping")
    storage_plan_resp = client.get("/api/trade-execution-gateway/audit-ledger-storage-plan")
    migration_spec_resp = client.post(
        "/api/trade-execution-gateway/audit-ledger-migration-spec/verify",
        json={"spec_text": None},
    )
    assert contract_resp.status_code == 200
    assert audit_resp.status_code == 200
    assert risk_resp.status_code == 200
    assert rollback_resp.status_code == 200
    assert pre_live_resp.status_code == 200
    assert checklist_resp.status_code == 200
    assert release_gate_resp.status_code == 200
    assert final_report_resp.status_code == 200
    assert threat_model_resp.status_code == 200
    assert interface_draft_resp.status_code == 200
    assert contract_verification_resp.status_code == 200
    assert order_failure_resp.status_code == 200
    assert runbook_mapping_resp.status_code == 200
    assert storage_plan_resp.status_code == 200
    assert migration_spec_resp.status_code == 200
    assert contract_resp.json()["stage"] == "V5.5-P5"
    assert contract_resp.json()["decision"]["contract_allows_execution_now"] is False
    assert audit_resp.json()["stage"] == "V5.5-P5"
    assert audit_resp.json()["writes_database_now"] is False
    assert audit_resp.json()["decision"]["schema_persistence_enabled_now"] is False
    assert risk_resp.json()["stage"] == "V5.5-P5"
    assert risk_resp.json()["decision"]["contract_allows_execution_now"] is False
    assert risk_resp.json()["integration_notes"]["manual_confirmation_override_allowed"] is False
    assert rollback_resp.json()["stage"] == "V5.5-P5"
    assert rollback_resp.json()["decision"]["runbook_allows_execution_now"] is False
    assert pre_live_resp.json()["stage"] == "V5.5-P5"
    assert pre_live_resp.json()["decision"]["ready_for_live_enablement"] is False
    assert pre_live_resp.json()["decision"]["gateway_can_execute"] is False
    assert checklist_resp.json()["stage"] == "V5.5-P5"
    assert checklist_resp.json()["decision"]["acceptance_allows_enablement_now"] is False
    assert release_gate_resp.json()["stage"] == "V5.5-P5"
    assert release_gate_resp.json()["default_state"] == "disabled"
    assert release_gate_resp.json()["decision"]["release_gate_allows_enablement_now"] is False
    assert final_report_resp.json()["stage"] == "V5.5-P5"
    assert final_report_resp.json()["decision"]["v5_review_only_baseline_complete"] is True
    assert final_report_resp.json()["decision"]["ready_for_live_enablement"] is False
    assert final_report_resp.json()["decision"]["gateway_can_execute"] is False
    assert threat_model_resp.json()["stage"] == "V5.5-P5"
    assert threat_model_resp.json()["decision"]["broker_adapter_allowed_now"] is False
    assert interface_draft_resp.json()["stage"] == "V5.5-P5"
    assert interface_draft_resp.json()["decision"]["interface_implemented_now"] is False
    assert interface_draft_resp.json()["decision"]["adapter_can_execute_now"] is False
    assert contract_verification_resp.json()["stage"] == "V5.5-P5"
    assert contract_verification_resp.json()["status"] == "fixture_contract_verification_passed"
    assert contract_verification_resp.json()["decision"]["adapter_can_connect_now"] is False
    assert contract_verification_resp.json()["summary"]["network_calls"] is False
    assert order_failure_resp.json()["stage"] == "V5.5-P5"
    assert order_failure_resp.json()["status"] == "order_failure_fixtures_ready"
    assert order_failure_resp.json()["decision"]["can_submit_order_now"] is False
    assert order_failure_resp.json()["summary"]["places_order"] is False
    assert runbook_mapping_resp.json()["stage"] == "V5.5-P5"
    assert runbook_mapping_resp.json()["status"] == "order_failure_runbook_mapping_ready"
    assert runbook_mapping_resp.json()["decision"]["can_execute_runbook_now"] is False
    assert runbook_mapping_resp.json()["summary"]["writes_database_now"] is False
    assert storage_plan_resp.json()["stage"] == "V5.5-P5"
    assert storage_plan_resp.json()["status"] == "disabled_audit_ledger_storage_plan_ready"
    assert storage_plan_resp.json()["decision"]["can_create_table_now"] is False
    assert storage_plan_resp.json()["summary"]["runs_migration_now"] is False
    assert migration_spec_resp.json()["stage"] == "V5.5-P5"
    assert migration_spec_resp.json()["status"] == "spec_verification_passed"
    assert migration_spec_resp.json()["decision"]["can_execute_sql_now"] is False
    assert migration_spec_resp.json()["decision"]["can_write_audit_row_now"] is False
    assert migration_spec_resp.json()["summary"]["executes_sql"] is False
    assert migration_spec_resp.json()["summary"]["writes_migration_file_now"] is False

def test_learning_summary(client):
    resp = client.get("/api/learning/summary")
    assert resp.status_code == 200
    assert "sample_counts" in resp.json()
