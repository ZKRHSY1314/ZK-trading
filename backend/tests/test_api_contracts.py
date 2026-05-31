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
    assert data["stage"] == "V5.5-P20"
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
    migration_approval_resp = client.post(
        "/api/trade-execution-gateway/audit-ledger-migration-spec/approve",
        json={"spec_text": None, "approved_by": "contract-test", "note": "contract smoke approval metadata"},
    )
    migration_approvals_resp = client.get("/api/trade-execution-gateway/audit-ledger-migration-spec/approvals?limit=5")
    migration_release_readiness_resp = client.get(
        "/api/trade-execution-gateway/audit-ledger-migration-release-readiness?limit=5"
    )
    migration_approval_review_resp = client.get(
        "/api/trade-execution-gateway/audit-ledger-migration-approval-review?limit=5&max_age_days=7"
    )
    migration_release_package_resp = client.get(
        "/api/trade-execution-gateway/audit-ledger-migration-release-package?limit=5&max_age_days=7"
    )
    migration_package_integrity_resp = client.get(
        "/api/trade-execution-gateway/audit-ledger-migration-release-package/integrity-review?limit=5&max_age_days=7&repeat_checks=2"
    )
    migration_release_rehearsal_resp = client.get(
        "/api/trade-execution-gateway/audit-ledger-migration-release-review/rehearsal?limit=5&max_age_days=7&repeat_checks=2"
    )
    rehearsal_json = migration_release_rehearsal_resp.json()
    evidence_payload = {
        "source_package_id": rehearsal_json["source_package_id"],
        "rehearsal_id": rehearsal_json["rehearsal_id"],
        "artifacts": [
            {
                "name": name,
                "present": True,
                "artifact_hash": f"contract-artifact-{index:02d}-0123456789abcdef",
                "reviewed_by": "contract-offline-operator",
                "reviewed_at": "2026-05-31T15:30:00",
            }
            for index, name in enumerate(rehearsal_json["required_offline_artifacts"], start=1)
        ],
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": False,
    }
    migration_release_evidence_resp = client.post(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/verify?limit=5&max_age_days=7&repeat_checks=2",
        json={"evidence": evidence_payload},
    )
    migration_release_evidence_comparison_resp = client.post(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/compare?limit=5&max_age_days=7&repeat_checks=2",
        json={"baseline_evidence": evidence_payload, "candidate_evidence": evidence_payload},
    )
    migration_release_health_digest_resp = client.post(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest?limit=5&max_age_days=7&repeat_checks=2",
        json={"baseline_evidence": evidence_payload, "candidate_evidence": evidence_payload},
    )
    migration_release_health_digest_history_resp = client.post(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-proposal?limit=5&max_age_days=7&repeat_checks=2",
        json={"baseline_evidence": evidence_payload, "candidate_evidence": evidence_payload},
    )
    migration_release_health_digest_history_checklist_resp = client.post(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-checklist?limit=5&max_age_days=7&repeat_checks=2",
        json={"baseline_evidence": evidence_payload, "candidate_evidence": evidence_payload},
    )
    migration_release_health_digest_history_spec_resp = client.post(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-spec/verify?limit=5&max_age_days=7&repeat_checks=2",
        json={"spec_text": None, "baseline_evidence": evidence_payload, "candidate_evidence": evidence_payload},
    )
    migration_release_health_digest_history_spec_approval_resp = client.post(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-spec/approve?limit=5&max_age_days=7&repeat_checks=2",
        json={
            "spec_text": None,
            "approved_by": "contract-test",
            "note": "contract smoke history migration spec approval metadata",
            "baseline_evidence": evidence_payload,
            "candidate_evidence": evidence_payload,
        },
    )
    migration_release_health_digest_history_spec_approvals_resp = client.get(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-spec/approvals?limit=5"
    )
    migration_release_health_digest_history_readiness_resp = client.get(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-release-readiness?limit=5&max_age_days=7&repeat_checks=2"
    )
    migration_release_health_digest_history_approval_review_resp = client.get(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-approval-review?limit=5&max_age_days=7&repeat_checks=2"
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
    assert migration_approval_resp.status_code == 200
    assert migration_approvals_resp.status_code == 200
    assert migration_release_readiness_resp.status_code == 200
    assert migration_approval_review_resp.status_code == 200
    assert migration_release_package_resp.status_code == 200
    assert migration_package_integrity_resp.status_code == 200
    assert migration_release_rehearsal_resp.status_code == 200
    assert migration_release_evidence_resp.status_code == 200
    assert migration_release_evidence_comparison_resp.status_code == 200
    assert migration_release_health_digest_resp.status_code == 200
    assert migration_release_health_digest_history_resp.status_code == 200
    assert migration_release_health_digest_history_checklist_resp.status_code == 200
    assert migration_release_health_digest_history_spec_resp.status_code == 200
    assert migration_release_health_digest_history_spec_approval_resp.status_code == 200
    assert migration_release_health_digest_history_spec_approvals_resp.status_code == 200
    assert migration_release_health_digest_history_readiness_resp.status_code == 200
    assert migration_release_health_digest_history_approval_review_resp.status_code == 200
    assert contract_resp.json()["stage"] == "V5.5-P20"
    assert contract_resp.json()["decision"]["contract_allows_execution_now"] is False
    assert audit_resp.json()["stage"] == "V5.5-P20"
    assert audit_resp.json()["writes_database_now"] is False
    assert audit_resp.json()["decision"]["schema_persistence_enabled_now"] is False
    assert risk_resp.json()["stage"] == "V5.5-P20"
    assert risk_resp.json()["decision"]["contract_allows_execution_now"] is False
    assert risk_resp.json()["integration_notes"]["manual_confirmation_override_allowed"] is False
    assert rollback_resp.json()["stage"] == "V5.5-P20"
    assert rollback_resp.json()["decision"]["runbook_allows_execution_now"] is False
    assert pre_live_resp.json()["stage"] == "V5.5-P20"
    assert pre_live_resp.json()["decision"]["ready_for_live_enablement"] is False
    assert pre_live_resp.json()["decision"]["gateway_can_execute"] is False
    assert checklist_resp.json()["stage"] == "V5.5-P20"
    assert checklist_resp.json()["decision"]["acceptance_allows_enablement_now"] is False
    assert release_gate_resp.json()["stage"] == "V5.5-P20"
    assert release_gate_resp.json()["default_state"] == "disabled"
    assert release_gate_resp.json()["decision"]["release_gate_allows_enablement_now"] is False
    assert final_report_resp.json()["stage"] == "V5.5-P20"
    assert final_report_resp.json()["decision"]["v5_review_only_baseline_complete"] is True
    assert final_report_resp.json()["decision"]["ready_for_live_enablement"] is False
    assert final_report_resp.json()["decision"]["gateway_can_execute"] is False
    assert threat_model_resp.json()["stage"] == "V5.5-P20"
    assert threat_model_resp.json()["decision"]["broker_adapter_allowed_now"] is False
    assert interface_draft_resp.json()["stage"] == "V5.5-P20"
    assert interface_draft_resp.json()["decision"]["interface_implemented_now"] is False
    assert interface_draft_resp.json()["decision"]["adapter_can_execute_now"] is False
    assert contract_verification_resp.json()["stage"] == "V5.5-P20"
    assert contract_verification_resp.json()["status"] == "fixture_contract_verification_passed"
    assert contract_verification_resp.json()["decision"]["adapter_can_connect_now"] is False
    assert contract_verification_resp.json()["summary"]["network_calls"] is False
    assert order_failure_resp.json()["stage"] == "V5.5-P20"
    assert order_failure_resp.json()["status"] == "order_failure_fixtures_ready"
    assert order_failure_resp.json()["decision"]["can_submit_order_now"] is False
    assert order_failure_resp.json()["summary"]["places_order"] is False
    assert runbook_mapping_resp.json()["stage"] == "V5.5-P20"
    assert runbook_mapping_resp.json()["status"] == "order_failure_runbook_mapping_ready"
    assert runbook_mapping_resp.json()["decision"]["can_execute_runbook_now"] is False
    assert runbook_mapping_resp.json()["summary"]["writes_database_now"] is False
    assert storage_plan_resp.json()["stage"] == "V5.5-P20"
    assert storage_plan_resp.json()["status"] == "disabled_audit_ledger_storage_plan_ready"
    assert storage_plan_resp.json()["decision"]["can_create_table_now"] is False
    assert storage_plan_resp.json()["summary"]["runs_migration_now"] is False
    assert migration_spec_resp.json()["stage"] == "V5.5-P20"
    assert migration_spec_resp.json()["status"] == "spec_verification_passed"
    assert migration_spec_resp.json()["decision"]["can_execute_sql_now"] is False
    assert migration_spec_resp.json()["decision"]["can_write_audit_row_now"] is False
    assert migration_spec_resp.json()["summary"]["executes_sql"] is False
    assert migration_spec_resp.json()["summary"]["writes_migration_file_now"] is False
    assert migration_approval_resp.json()["stage"] == "V5.5-P20"
    assert migration_approval_resp.json()["status"] == "approval_metadata_recorded"
    assert migration_approval_resp.json()["safety_summary"]["writes_existing_event_now"] is True
    assert migration_approval_resp.json()["safety_summary"]["writes_audit_ledger_row_now"] is False
    assert migration_approval_resp.json()["safety_summary"]["executes_sql"] is False
    assert migration_approval_resp.json()["migration_allowed_now"] is False
    assert migration_approvals_resp.json()[0]["event_id"] == migration_approval_resp.json()["event_id"]
    assert migration_release_readiness_resp.json()["stage"] == "V5.5-P20"
    assert migration_release_readiness_resp.json()["status"] == "release_evidence_ready"
    assert migration_release_readiness_resp.json()["decision"]["go_no_go"] == "go_for_manual_release_review"
    assert migration_release_readiness_resp.json()["decision"]["migration_allowed_now"] is False
    assert migration_release_readiness_resp.json()["decision"]["release_approved_now"] is False
    assert migration_release_readiness_resp.json()["evidence"]["latest_approval_event_id"] == migration_approval_resp.json()["event_id"]
    assert migration_release_readiness_resp.json()["safety_summary"]["writes_audit_ledger_row_now"] is False
    assert migration_release_readiness_resp.json()["safety_summary"]["executes_sql"] is False
    assert migration_approval_review_resp.json()["stage"] == "V5.5-P20"
    assert migration_approval_review_resp.json()["status"] == "approval_current"
    assert migration_approval_review_resp.json()["latest_approval"]["event_id"] == migration_approval_resp.json()["event_id"]
    assert migration_approval_review_resp.json()["decision"]["approval_can_be_reused_for_manual_release_review"] is True
    assert migration_approval_review_resp.json()["decision"]["migration_allowed_now"] is False
    assert migration_approval_review_resp.json()["safety_summary"]["writes_audit_ledger_row_now"] is False
    assert migration_approval_review_resp.json()["safety_summary"]["executes_sql"] is False
    assert migration_release_package_resp.json()["stage"] == "V5.5-P20"
    assert migration_release_package_resp.json()["status"] == "release_package_ready_for_manual_review"
    assert migration_release_package_resp.json()["decision"]["go_no_go"] == "ready_for_manual_release_review"
    assert migration_release_package_resp.json()["decision"]["execution_allowed_now"] is False
    assert migration_release_package_resp.json()["decision"]["release_approved_now"] is False
    assert migration_release_package_resp.json()["manifest"]["writes_file"] is False
    assert migration_release_package_resp.json()["manifest"]["download_created"] is False
    assert migration_release_package_resp.json()["safety_summary"]["writes_audit_ledger_row_now"] is False
    assert migration_release_package_resp.json()["safety_summary"]["writes_file"] is False
    assert migration_package_integrity_resp.json()["stage"] == "V5.5-P20"
    assert migration_package_integrity_resp.json()["status"] == "integrity_review_passed"
    assert migration_package_integrity_resp.json()["source_package_id"] == migration_package_integrity_resp.json()["recomputed_package_id"]
    assert migration_package_integrity_resp.json()["decision"]["package_id_stable"] is True
    assert migration_package_integrity_resp.json()["decision"]["manifest_integrity_passed"] is True
    assert migration_package_integrity_resp.json()["decision"]["execution_allowed_now"] is False
    assert migration_package_integrity_resp.json()["decision"]["release_approved_now"] is False
    assert migration_package_integrity_resp.json()["safety_summary"]["writes_file"] is False
    assert migration_package_integrity_resp.json()["safety_summary"]["mutates_source_package"] is False
    assert migration_release_rehearsal_resp.json()["stage"] == "V5.5-P20"
    assert migration_release_rehearsal_resp.json()["status"] == "manual_release_rehearsal_ready"
    assert migration_release_rehearsal_resp.json()["decision"]["go_no_go"] == "ready_for_offline_manual_review"
    assert migration_release_rehearsal_resp.json()["decision"]["manual_review_recorded_now"] is False
    assert migration_release_rehearsal_resp.json()["decision"]["release_approved_now"] is False
    assert migration_release_rehearsal_resp.json()["decision"]["execution_allowed_now"] is False
    assert migration_release_rehearsal_resp.json()["operator_rehearsal_policy"]["api_can_record_operator_review"] is False
    assert migration_release_rehearsal_resp.json()["safety_summary"]["records_manual_review_now"] is False
    assert migration_release_evidence_resp.json()["stage"] == "V5.5-P20"
    assert migration_release_evidence_resp.json()["status"] == "manual_release_evidence_verification_passed"
    assert migration_release_evidence_resp.json()["decision"]["evidence_complete"] is True
    assert migration_release_evidence_resp.json()["decision"]["manual_review_recorded_now"] is False
    assert migration_release_evidence_resp.json()["decision"]["release_approved_now"] is False
    assert migration_release_evidence_resp.json()["decision"]["execution_allowed_now"] is False
    assert migration_release_evidence_resp.json()["safety_summary"]["persists_manual_release_evidence"] is False
    assert migration_release_evidence_resp.json()["safety_summary"]["writes_database_now"] is False
    assert migration_release_evidence_comparison_resp.json()["stage"] == "V5.5-P20"
    assert migration_release_evidence_comparison_resp.json()["status"] == "manual_release_evidence_comparison_stable"
    assert migration_release_evidence_comparison_resp.json()["decision"]["evidence_pair_stable"] is True
    assert migration_release_evidence_comparison_resp.json()["decision"]["release_approved_now"] is False
    assert migration_release_evidence_comparison_resp.json()["decision"]["execution_allowed_now"] is False
    assert migration_release_evidence_comparison_resp.json()["safety_summary"]["persists_manual_release_evidence_comparison"] is False
    assert migration_release_evidence_comparison_resp.json()["safety_summary"]["writes_database_now"] is False
    assert migration_release_health_digest_resp.json()["stage"] == "V5.5-P20"
    assert migration_release_health_digest_resp.json()["status"] == "manual_release_health_digest_healthy"
    assert migration_release_health_digest_resp.json()["decision"]["digest_healthy"] is True
    assert migration_release_health_digest_resp.json()["decision"]["release_approved_now"] is False
    assert migration_release_health_digest_resp.json()["decision"]["execution_allowed_now"] is False
    assert migration_release_health_digest_resp.json()["safety_summary"]["persists_manual_release_health_digest"] is False
    assert migration_release_health_digest_resp.json()["safety_summary"]["writes_database_now"] is False
    assert migration_release_health_digest_history_resp.json()["stage"] == "V5.5-P20"
    assert migration_release_health_digest_history_resp.json()["status"] == "history_retention_proposal_ready"
    assert migration_release_health_digest_history_resp.json()["decision"]["history_persistence_enabled_now"] is False
    assert migration_release_health_digest_history_resp.json()["safety_summary"]["persists_manual_release_health_digest_history"] is False
    assert migration_release_health_digest_history_resp.json()["safety_summary"]["writes_database_now"] is False
    assert migration_release_health_digest_history_checklist_resp.json()["stage"] == "V5.5-P20"
    assert migration_release_health_digest_history_checklist_resp.json()["status"] == "history_migration_readiness_review_ready"
    assert migration_release_health_digest_history_checklist_resp.json()["decision"]["migration_allowed_now"] is False
    assert migration_release_health_digest_history_checklist_resp.json()["safety_summary"]["persists_manual_release_health_digest_history"] is False
    assert migration_release_health_digest_history_checklist_resp.json()["safety_summary"]["writes_database_now"] is False
    assert migration_release_health_digest_history_checklist_resp.json()["safety_summary"]["writes_file"] is False
    assert migration_release_health_digest_history_spec_resp.json()["stage"] == "V5.5-P20"
    assert migration_release_health_digest_history_spec_resp.json()["status"] == "spec_verification_passed"
    assert migration_release_health_digest_history_spec_resp.json()["decision"]["can_execute_sql_now"] is False
    assert migration_release_health_digest_history_spec_resp.json()["decision"]["can_write_history_row_now"] is False
    assert migration_release_health_digest_history_spec_resp.json()["safety_summary"]["persists_manual_release_health_digest_history"] is False
    assert migration_release_health_digest_history_spec_resp.json()["safety_summary"]["writes_database_now"] is False
    assert migration_release_health_digest_history_spec_resp.json()["safety_summary"]["writes_file"] is False
    assert migration_release_health_digest_history_spec_approval_resp.json()["stage"] == "V5.5-P20"
    assert migration_release_health_digest_history_spec_approval_resp.json()["status"] == "approval_metadata_recorded"
    assert migration_release_health_digest_history_spec_approval_resp.json()["safety_summary"]["writes_existing_event_now"] is True
    assert migration_release_health_digest_history_spec_approval_resp.json()["safety_summary"]["writes_history_row_now"] is False
    assert migration_release_health_digest_history_spec_approval_resp.json()["safety_summary"]["executes_sql"] is False
    assert (
        migration_release_health_digest_history_spec_approvals_resp.json()[0]["event_id"]
        == migration_release_health_digest_history_spec_approval_resp.json()["event_id"]
    )
    assert migration_release_health_digest_history_readiness_resp.json()["stage"] == "V5.5-P20"
    assert migration_release_health_digest_history_readiness_resp.json()["status"] == "release_evidence_ready"
    assert migration_release_health_digest_history_readiness_resp.json()["decision"]["go_no_go"] == "go_for_manual_release_review"
    assert migration_release_health_digest_history_readiness_resp.json()["decision"]["migration_allowed_now"] is False
    assert migration_release_health_digest_history_readiness_resp.json()["decision"]["release_approved_now"] is False
    assert migration_release_health_digest_history_readiness_resp.json()["evidence"]["latest_approval_event_id"] == migration_release_health_digest_history_spec_approval_resp.json()["event_id"]
    assert migration_release_health_digest_history_readiness_resp.json()["safety_summary"]["writes_history_row_now"] is False
    assert migration_release_health_digest_history_readiness_resp.json()["safety_summary"]["executes_sql"] is False
    assert migration_release_health_digest_history_approval_review_resp.json()["stage"] == "V5.5-P20"
    assert migration_release_health_digest_history_approval_review_resp.json()["status"] == "approval_current"
    assert migration_release_health_digest_history_approval_review_resp.json()["latest_approval"]["event_id"] == migration_release_health_digest_history_spec_approval_resp.json()["event_id"]
    assert migration_release_health_digest_history_approval_review_resp.json()["decision"]["approval_can_be_reused_for_manual_release_review"] is True
    assert migration_release_health_digest_history_approval_review_resp.json()["decision"]["migration_allowed_now"] is False
    assert migration_release_health_digest_history_approval_review_resp.json()["decision"]["release_approved_now"] is False
    assert migration_release_health_digest_history_approval_review_resp.json()["safety_summary"]["writes_history_row_now"] is False
    assert migration_release_health_digest_history_approval_review_resp.json()["safety_summary"]["executes_sql"] is False

def test_learning_summary(client):
    resp = client.get("/api/learning/summary")
    assert resp.status_code == 200
    assert "sample_counts" in resp.json()
