import json
from datetime import datetime, timedelta

from app.config import settings
from app.trade_execution.gateway import TradeExecutionGatewayService


def _complete_manual_release_evidence(service: TradeExecutionGatewayService, reviewed_by: str = "offline-operator") -> dict:
    rehearsal = service.audit_ledger_migration_manual_release_review_rehearsal(
        limit=5,
        max_age_days=7,
        repeat_checks=2,
    )
    return {
        "source_package_id": rehearsal["source_package_id"],
        "rehearsal_id": rehearsal["rehearsal_id"],
        "artifacts": [
            {
                "name": name,
                "present": True,
                "artifact_hash": f"artifact-{index:02d}-0123456789abcdef",
                "reviewed_by": reviewed_by,
                "reviewed_at": "2026-05-31T15:00:00",
                "review_note": "offline evidence reviewed",
            }
            for index, name in enumerate(rehearsal["required_offline_artifacts"], start=1)
        ],
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": False,
    }


def _complete_health_digest_history_release_evidence(
    service: TradeExecutionGatewayService,
    reviewed_by: str = "offline-history-operator",
) -> dict:
    rehearsal = service.audit_ledger_migration_manual_release_health_digest_history_release_rehearsal(
        limit=5,
        max_age_days=7,
        repeat_checks=2,
    )
    return {
        "source_package_id": rehearsal["source_package_id"],
        "rehearsal_id": rehearsal["rehearsal_id"],
        "artifacts": [
            {
                "name": name,
                "present": True,
                "artifact_hash": f"history-artifact-{index:02d}-0123456789abcdef",
                "reviewed_by": reviewed_by,
                "reviewed_at": "2026-06-01T15:00:00",
                "review_note": "offline health digest history release evidence reviewed",
            }
            for index, name in enumerate(rehearsal["required_offline_artifacts"], start=1)
        ],
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": False,
    }


def test_trade_execution_gateway_capabilities_are_review_only():
    data = TradeExecutionGatewayService().capabilities()

    assert data["stage"] == "V5.5-P24"
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
    assert "portfolio_symbol_risk_gate_contract_review" in data["allowed_modes"]
    assert "rollback_runbook_review" in data["allowed_modes"]
    assert "pre_live_review_package_review" in data["allowed_modes"]
    assert "operator_acceptance_checklist_review" in data["allowed_modes"]
    assert "disabled_release_gate_review" in data["allowed_modes"]
    assert "final_readiness_report_review" in data["allowed_modes"]
    assert "broker_adapter_threat_model_review" in data["allowed_modes"]
    assert "broker_adapter_interface_draft_review" in data["allowed_modes"]
    assert "broker_adapter_contract_verification_review" in data["allowed_modes"]
    assert "order_failure_runbook_mapping_review" in data["allowed_modes"]
    assert "disabled_audit_ledger_storage_plan_review" in data["allowed_modes"]
    assert "audit_ledger_migration_spec_dry_run_review" in data["allowed_modes"]
    assert "audit_ledger_migration_spec_approval_metadata_review" in data["allowed_modes"]
    assert "audit_ledger_migration_release_readiness_review" in data["allowed_modes"]
    assert "audit_ledger_migration_approval_freshness_review" in data["allowed_modes"]
    assert "audit_ledger_migration_manual_release_package_review" in data["allowed_modes"]
    assert "audit_ledger_migration_release_package_integrity_review" in data["allowed_modes"]
    assert "audit_ledger_migration_manual_release_review_rehearsal" in data["allowed_modes"]
    assert "audit_ledger_migration_manual_release_evidence_verification" in data["allowed_modes"]
    assert "audit_ledger_migration_manual_release_evidence_comparison" in data["allowed_modes"]
    assert "audit_ledger_migration_manual_release_health_digest" in data["allowed_modes"]
    assert "audit_ledger_migration_manual_release_health_digest_history_retention_proposal" in data["allowed_modes"]
    assert "audit_ledger_migration_manual_release_health_digest_history_migration_readiness_checklist" in data["allowed_modes"]
    assert "audit_ledger_migration_manual_release_health_digest_history_migration_spec_verifier" in data["allowed_modes"]
    assert "audit_ledger_migration_manual_release_health_digest_history_migration_spec_approval_metadata" in data["allowed_modes"]
    assert "audit_ledger_migration_manual_release_health_digest_history_release_readiness_review" in data["allowed_modes"]
    assert "audit_ledger_migration_manual_release_health_digest_history_approval_freshness_review" in data["allowed_modes"]
    assert "audit_ledger_migration_manual_release_health_digest_history_release_package_review" in data["allowed_modes"]
    assert "audit_ledger_migration_manual_release_health_digest_history_release_package_integrity_review" in data["allowed_modes"]
    assert "audit_ledger_migration_manual_release_health_digest_history_release_rehearsal" in data["allowed_modes"]
    assert "audit_ledger_migration_manual_release_health_digest_history_release_evidence_verification" in data["allowed_modes"]
    assert "place_real_trade" in data["forbidden_modes"]
    assert "enable_gateway_by_api" in data["forbidden_modes"]
    assert "instantiate_broker_adapter" in data["forbidden_modes"]
    assert "broker_network_call" in data["forbidden_modes"]
    assert "execute_failure_runbook" in data["forbidden_modes"]
    assert "create_audit_ledger_table" in data["forbidden_modes"]
    assert "write_audit_ledger_row" in data["forbidden_modes"]
    assert "execute_sql" in data["forbidden_modes"]
    assert "write_migration_file" in data["forbidden_modes"]
    assert "approve_migration_as_execution" in data["forbidden_modes"]
    assert "approve_release_from_summary" in data["forbidden_modes"]
    assert "reuse_expired_approval_as_current" in data["forbidden_modes"]
    assert "write_release_package_file" in data["forbidden_modes"]
    assert "approve_release_from_integrity_review" in data["forbidden_modes"]
    assert "record_manual_release_review_by_api" in data["forbidden_modes"]
    assert "persist_manual_release_evidence" in data["forbidden_modes"]
    assert "persist_manual_release_evidence_comparison" in data["forbidden_modes"]
    assert "persist_manual_release_health_digest" in data["forbidden_modes"]
    assert "persist_manual_release_health_digest_history" in data["forbidden_modes"]
    assert "create_manual_release_health_digest_history_table" in data["forbidden_modes"]
    assert "run_manual_release_health_digest_history_migration" in data["forbidden_modes"]
    assert "write_manual_release_health_digest_history_migration_file" in data["forbidden_modes"]
    assert "execute_manual_release_health_digest_history_migration_spec" in data["forbidden_modes"]
    assert "approve_manual_release_health_digest_history_migration_as_execution" in data["forbidden_modes"]
    assert "approve_manual_release_health_digest_history_release_from_readiness" in data["forbidden_modes"]
    assert "reuse_expired_manual_release_health_digest_history_approval_as_current" in data["forbidden_modes"]
    assert "treat_manual_release_health_digest_history_package_as_release_approval" in data["forbidden_modes"]
    assert "approve_manual_release_health_digest_history_release_from_integrity_review" in data["forbidden_modes"]
    assert "record_manual_release_health_digest_history_review_by_api" in data["forbidden_modes"]
    assert "persist_manual_release_health_digest_history_evidence" in data["forbidden_modes"]
    components = {item["name"]: item for item in data["required_future_components"]}
    assert components["ManualConfirmationContract"]["status"] == "review_contract_defined"
    assert components["PortfolioRiskGateContract"]["status"] == "review_contract_defined"
    assert components["ExecutionAuditLedger"]["status"] == "review_schema_defined_not_persisted"
    assert components["ManualRollbackRunbook"]["status"] == "review_runbook_defined"
    assert components["PreLiveReviewPackage"]["status"] == "review_package_defined"
    assert components["OperatorAcceptanceChecklist"]["status"] == "review_checklist_defined"
    assert components["DisabledByDefaultReleaseGate"]["status"] == "review_gate_defined"
    assert components["FinalReadinessReport"]["status"] == "review_report_defined"
    assert components["BrokerAdapterThreatModel"]["status"] == "review_threat_model_defined"
    assert components["BrokerAdapterInterfaceDraft"]["status"] == "review_interface_draft_defined"
    assert components["BrokerAdapterContractVerifier"]["status"] == "review_fixture_contract_verified"
    assert components["OrderLifecycleFailureFixtures"]["status"] == "review_failure_fixtures_defined"
    assert components["OrderFailureRunbookMapping"]["status"] == "review_runbook_mapping_defined"
    assert components["DisabledAuditLedgerStoragePlan"]["status"] == "review_storage_plan_defined_not_persisted"
    assert components["AuditLedgerMigrationSpecDryRunVerifier"]["status"] == "review_dry_run_spec_verifier_defined"
    assert components["AuditLedgerMigrationSpecApprovalMetadata"]["status"] == "review_approval_metadata_defined_existing_events_only"
    assert components["AuditLedgerMigrationReleaseReadinessSummary"]["status"] == "review_release_readiness_summary_defined"
    assert components["AuditLedgerMigrationApprovalFreshnessReview"]["status"] == "review_approval_freshness_defined"
    assert components["AuditLedgerMigrationManualReleasePackageManifest"]["status"] == "review_manual_release_package_defined"
    assert components["AuditLedgerMigrationReleasePackageIntegrityReview"]["status"] == "review_release_package_integrity_defined"
    assert components["AuditLedgerMigrationManualReleaseReviewRehearsal"]["status"] == "review_manual_release_rehearsal_defined"
    assert components["AuditLedgerMigrationManualReleaseEvidenceVerifier"]["status"] == "review_manual_release_evidence_verifier_defined"
    assert components["AuditLedgerMigrationManualReleaseEvidenceComparison"]["status"] == "review_manual_release_evidence_comparison_defined"
    assert components["AuditLedgerMigrationManualReleaseHealthDigest"]["status"] == "review_manual_release_health_digest_defined"
    assert components["AuditLedgerMigrationManualReleaseHealthDigestHistoryRetentionProposal"]["status"] == "review_manual_release_health_digest_history_retention_proposal_defined"
    assert components["AuditLedgerMigrationManualReleaseHealthDigestHistoryMigrationReadinessChecklist"]["status"] == "review_manual_release_health_digest_history_migration_readiness_checklist_defined"
    assert components["AuditLedgerMigrationManualReleaseHealthDigestHistoryMigrationSpecVerifier"]["status"] == "review_manual_release_health_digest_history_migration_spec_verifier_defined"
    assert components["AuditLedgerMigrationManualReleaseHealthDigestHistoryMigrationSpecApprovalMetadata"]["status"] == "review_manual_release_health_digest_history_migration_spec_approval_metadata_defined"
    assert components["AuditLedgerMigrationManualReleaseHealthDigestHistoryReleaseReadiness"]["status"] == "review_manual_release_health_digest_history_release_readiness_defined"
    assert components["AuditLedgerMigrationManualReleaseHealthDigestHistoryApprovalFreshnessReview"]["status"] == "review_manual_release_health_digest_history_approval_freshness_defined"
    assert components["AuditLedgerMigrationManualReleaseHealthDigestHistoryReleasePackageManifest"]["status"] == "review_manual_release_health_digest_history_release_package_defined"
    assert components["AuditLedgerMigrationManualReleaseHealthDigestHistoryReleasePackageIntegrityReview"]["status"] == "review_manual_release_health_digest_history_release_package_integrity_defined"
    assert components["AuditLedgerMigrationManualReleaseHealthDigestHistoryReleaseRehearsal"]["status"] == "review_manual_release_health_digest_history_release_rehearsal_defined"
    assert components["AuditLedgerMigrationManualReleaseHealthDigestHistoryReleaseEvidenceVerifier"]["status"] == "review_manual_release_health_digest_history_release_evidence_verifier_defined"
    assert data["safety_summary"]["places_real_trade"] is False
    assert data["safety_summary"]["connects_broker"] is False


def test_trade_execution_gateway_review_gates_are_pre_live_metadata_only():
    data = TradeExecutionGatewayService().review_gates()
    gates = {gate["name"]: gate for gate in data["gates"]}

    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "audit_ledger_migration_manual_release_health_digest_history_release_evidence_verifier_ready"
    assert gates["live_trading_disabled"]["status"] == "passed"
    assert gates["broker_adapter_absent"]["status"] == "passed"
    assert gates["credential_storage_absent"]["status"] == "passed"
    assert gates["human_confirmation_required"]["status"] == "passed"
    assert gates["risk_gate_contract_required"]["status"] == "passed"
    assert gates["audit_and_rollback_required"]["status"] == "passed"
    assert gates["audit_and_rollback_required"]["value"] == "audit_schema_and_rollback_runbook_review_ready"
    assert gates["pre_live_review_package_required"]["status"] == "passed"
    assert gates["operator_acceptance_checklist_required"]["status"] == "passed"
    assert gates["disabled_release_gate_required"]["status"] == "passed"
    assert gates["final_readiness_report_required"]["status"] == "passed"
    assert gates["broker_adapter_threat_model_required"]["status"] == "passed"
    assert gates["broker_adapter_interface_draft_required"]["status"] == "passed"
    assert gates["broker_adapter_contract_verification_required"]["status"] == "passed"
    assert gates["order_lifecycle_failure_fixtures_required"]["status"] == "passed"
    assert gates["order_failure_runbook_mapping_required"]["status"] == "passed"
    assert gates["disabled_audit_ledger_storage_plan_required"]["status"] == "passed"
    assert gates["audit_ledger_migration_spec_dry_run_required"]["status"] == "passed"
    assert gates["audit_ledger_migration_spec_approval_metadata_required"]["status"] == "passed"
    assert gates["audit_ledger_migration_release_readiness_required"]["status"] == "passed"
    assert gates["audit_ledger_migration_approval_freshness_required"]["status"] == "passed"
    assert gates["audit_ledger_migration_manual_release_package_required"]["status"] == "passed"
    assert gates["audit_ledger_migration_release_package_integrity_review_required"]["status"] == "passed"
    assert gates["audit_ledger_migration_manual_release_rehearsal_required"]["status"] == "passed"
    assert gates["audit_ledger_migration_manual_release_evidence_verifier_required"]["status"] == "passed"
    assert gates["audit_ledger_migration_manual_release_evidence_comparison_required"]["status"] == "passed"
    assert gates["audit_ledger_migration_manual_release_health_digest_required"]["status"] == "passed"
    assert gates["audit_ledger_migration_manual_release_health_digest_history_retention_proposal_required"]["status"] == "passed"
    assert gates["audit_ledger_migration_manual_release_health_digest_history_migration_readiness_checklist_required"]["status"] == "passed"
    assert gates["audit_ledger_migration_manual_release_health_digest_history_migration_spec_verifier_required"]["status"] == "passed"
    assert gates["audit_ledger_migration_manual_release_health_digest_history_migration_spec_approval_metadata_required"]["status"] == "passed"
    assert gates["audit_ledger_migration_manual_release_health_digest_history_release_readiness_required"]["status"] == "passed"
    assert gates["audit_ledger_migration_manual_release_health_digest_history_approval_freshness_required"]["status"] == "passed"
    assert gates["audit_ledger_migration_manual_release_health_digest_history_release_package_required"]["status"] == "passed"
    assert gates["audit_ledger_migration_manual_release_health_digest_history_release_package_integrity_review_required"]["status"] == "passed"
    assert gates["audit_ledger_migration_manual_release_health_digest_history_release_rehearsal_required"]["status"] == "passed"
    assert gates["audit_ledger_migration_manual_release_health_digest_history_release_evidence_verifier_required"]["status"] == "passed"
    assert data["decision"]["gateway_can_execute"] is False
    assert data["decision"]["manual_confirmation_contract_ready"] is True
    assert data["decision"]["risk_contract_ready"] is True
    assert data["decision"]["audit_contract_ready"] is True
    assert data["decision"]["rollback_runbook_ready"] is True
    assert data["decision"]["pre_live_package_ready"] is True
    assert data["decision"]["operator_acceptance_checklist_ready"] is True
    assert data["decision"]["disabled_release_gate_ready"] is True
    assert data["decision"]["final_readiness_report_ready"] is True
    assert data["decision"]["broker_adapter_threat_model_ready"] is True
    assert data["decision"]["broker_adapter_interface_draft_ready"] is True
    assert data["decision"]["broker_adapter_contract_verification_ready"] is True
    assert data["decision"]["order_lifecycle_failure_fixtures_ready"] is True
    assert data["decision"]["order_failure_runbook_mapping_ready"] is True
    assert data["decision"]["disabled_audit_ledger_storage_plan_ready"] is True
    assert data["decision"]["audit_ledger_migration_spec_dry_run_ready"] is True
    assert data["decision"]["audit_ledger_migration_spec_approval_metadata_ready"] is True
    assert data["decision"]["audit_ledger_migration_release_readiness_ready"] is True
    assert data["decision"]["audit_ledger_migration_approval_freshness_ready"] is True
    assert data["decision"]["audit_ledger_migration_manual_release_package_ready"] is True
    assert data["decision"]["audit_ledger_migration_release_package_integrity_review_ready"] is True
    assert data["decision"]["audit_ledger_migration_manual_release_rehearsal_ready"] is True
    assert data["decision"]["audit_ledger_migration_manual_release_evidence_verifier_ready"] is True
    assert data["decision"]["audit_ledger_migration_manual_release_evidence_comparison_ready"] is True
    assert data["decision"]["audit_ledger_migration_manual_release_health_digest_ready"] is True
    assert data["decision"]["audit_ledger_migration_manual_release_health_digest_history_retention_proposal_ready"] is True
    assert data["decision"]["audit_ledger_migration_manual_release_health_digest_history_migration_readiness_checklist_ready"] is True
    assert data["decision"]["audit_ledger_migration_manual_release_health_digest_history_migration_spec_verifier_ready"] is True
    assert data["decision"]["audit_ledger_migration_manual_release_health_digest_history_migration_spec_approval_metadata_ready"] is True
    assert data["decision"]["audit_ledger_migration_manual_release_health_digest_history_release_readiness_ready"] is True
    assert data["decision"]["audit_ledger_migration_manual_release_health_digest_history_approval_freshness_ready"] is True
    assert data["decision"]["audit_ledger_migration_manual_release_health_digest_history_release_package_ready"] is True
    assert data["decision"]["audit_ledger_migration_manual_release_health_digest_history_release_package_integrity_review_ready"] is True
    assert data["decision"]["audit_ledger_migration_manual_release_health_digest_history_release_rehearsal_ready"] is True
    assert data["decision"]["audit_ledger_migration_manual_release_health_digest_history_release_evidence_verifier_ready"] is True
    assert data["decision"]["next_required_action"] == "review_audit_ledger_migration_manual_release_health_digest_history_release_evidence_verifier"
    assert data["decision"]["ready_for_live_enablement"] is False
    assert data["decision"]["live_trading_enabled"] is False
    assert data["safety_summary"]["real_money_execution_enabled"] is False


def test_manual_confirmation_contract_is_review_only():
    data = TradeExecutionGatewayService().manual_confirmation_contract()
    input_names = {item["name"] for item in data["required_operator_inputs"]}

    assert data["schema_version"] == "trade_execution_manual_confirmation_contract.v1"
    assert data["stage"] == "V5.5-P24"
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
    assert data["stage"] == "V5.5-P24"
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


def test_risk_gate_contract_is_review_only_and_blocks_overrides():
    data = TradeExecutionGatewayService().risk_gate_contract()
    portfolio_gates = {item["name"]: item for item in data["portfolio_gates"]}
    symbol_gates = {item["name"]: item for item in data["symbol_gates"]}

    assert data["schema_version"] == "trade_execution_risk_gate_contract.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "risk_gate_contract_review_ready"
    assert data["contract_state"] == "defined_for_review_only"
    assert portfolio_gates["total_exposure"]["limit"] == 0.60
    assert portfolio_gates["single_position"]["limit"] == 0.20
    assert portfolio_gates["max_daily_loss"]["failure_status"] == "blocked"
    assert symbol_gates["symbol_price_quality"]["failure_status"] == "blocked"
    assert symbol_gates["limit_up_down_state"]["manual_override_allowed"] is False
    assert "portfolio_risk_snapshot_hash" in data["required_evidence_hashes"]
    assert data["decision"]["contract_ready_for_review"] is True
    assert data["decision"]["contract_allows_execution_now"] is False
    assert data["decision"]["risk_gate_can_override_manual_confirmation"] is True
    assert data["integration_notes"]["manual_confirmation_override_allowed"] is False
    assert data["integration_notes"]["ai_override_allowed"] is False
    assert data["safety_summary"]["gateway_can_execute"] is False
    assert data["safety_summary"]["places_real_trade"] is False


def test_rollback_runbook_is_review_only_and_non_executable():
    data = TradeExecutionGatewayService().rollback_runbook()
    step_names = {item["step"] for item in data["rollback_steps"]}

    assert data["schema_version"] == "trade_execution_rollback_runbook.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "rollback_runbook_review_ready"
    assert data["runbook_state"] == "defined_for_review_only"
    assert "risk_gate_blocked" in data["trigger_events"]
    assert "unexpected_gateway_enablement" in data["trigger_events"]
    assert "freeze_new_gateway_reviews" in step_names
    assert "verify_live_trading_disabled" in step_names
    assert all(step["executes_commands"] is False for step in data["rollback_steps"])
    assert data["decision"]["runbook_ready_for_review"] is True
    assert data["decision"]["runbook_allows_execution_now"] is False
    assert data["decision"]["ready_for_live_enablement"] is False
    assert data["safety_summary"]["executes_commands"] is False
    assert data["safety_summary"]["writes_database_now"] is False
    assert data["safety_summary"]["connects_broker"] is False
    assert data["safety_summary"]["places_real_trade"] is False
    assert data["live_trading_enabled"] is False


def test_pre_live_review_package_assembles_contracts_without_enablement():
    data = TradeExecutionGatewayService().pre_live_review_package()
    manifest = {item["name"]: item for item in data["manifest"]}

    assert data["schema_version"] == "trade_execution_pre_live_review_package.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "pre_live_review_package_ready"
    assert len(data["package_id"]) == 64
    assert set(manifest) == {
        "capabilities",
        "manual_confirmation_contract",
        "audit_evidence_schema",
        "risk_gate_contract",
        "rollback_runbook",
        "review_gates",
        "operator_acceptance_checklist",
        "disabled_release_gate",
    }
    assert manifest["rollback_runbook"]["status"] == "rollback_runbook_review_ready"
    assert manifest["review_gates"]["status"] == "audit_ledger_migration_manual_release_health_digest_history_release_evidence_verifier_ready"
    assert manifest["operator_acceptance_checklist"]["status"] == "operator_acceptance_checklist_review_ready"
    assert manifest["disabled_release_gate"]["status"] == "disabled_release_gate_review_ready"
    assert "rollback_drill_evidence" in data["required_manual_artifacts"]
    assert data["included_safety_evidence"]["blocked_gate_count"] == 0
    assert data["decision"]["package_ready_for_manual_review"] is True
    assert data["decision"]["ready_for_live_enablement"] is False
    assert data["decision"]["gateway_can_execute"] is False
    assert data["safety_summary"]["writes_database_now"] is False
    assert data["safety_summary"]["runs_migration_now"] is False
    assert data["safety_summary"]["stores_credentials"] is False
    assert data["safety_summary"]["connects_broker"] is False
    assert data["safety_summary"]["places_real_trade"] is False


def test_final_readiness_report_closes_v5_review_baseline_without_enablement():
    data = TradeExecutionGatewayService().final_readiness_report()
    manifest = {item["name"]: item for item in data["manifest"]}

    assert data["schema_version"] == "trade_execution_final_readiness_report.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "v5_review_only_gateway_baseline_ready"
    assert len(data["report_id"]) == 64
    assert data["report_state"] == "final_v5_review_only_baseline"
    assert set(manifest) == {
        "capabilities",
        "review_gates",
        "manual_confirmation_contract",
        "audit_evidence_schema",
        "risk_gate_contract",
        "rollback_runbook",
        "pre_live_review_package",
        "operator_acceptance_checklist",
        "disabled_release_gate",
    }
    assert manifest["disabled_release_gate"]["status"] == "disabled_release_gate_review_ready"
    assert data["summary"]["completed_review_modules"] == 9
    assert data["summary"]["blocked_gate_count"] == 0
    assert data["summary"]["default_release_state"] == "disabled"
    assert data["safety_matrix"]["gateway_enabled"] is False
    assert data["safety_matrix"]["execution_enabled"] is False
    assert data["safety_matrix"]["broker_adapter_enabled"] is False
    assert data["safety_matrix"]["api_can_enable_gateway"] is False
    assert data["safety_matrix"]["live_trading_enabled"] is False
    assert "separate_live_integration_project_required" in data["remaining_blockers"]
    assert data["decision"]["v5_review_only_baseline_complete"] is True
    assert data["decision"]["ready_for_v5_5_threat_modeling"] is True
    assert data["decision"]["ready_for_live_enablement"] is False
    assert data["decision"]["gateway_can_execute"] is False
    assert data["decision"]["api_can_enable_gateway"] is False
    assert data["safety_summary"]["writes_database_now"] is False
    assert data["safety_summary"]["connects_broker"] is False
    assert data["safety_summary"]["places_real_trade"] is False


def test_broker_adapter_threat_model_is_review_only_and_blocks_live_surfaces():
    data = TradeExecutionGatewayService().broker_adapter_threat_model()
    categories = {item["name"]: item for item in data["threat_categories"]}

    assert data["schema_version"] == "trade_execution_broker_adapter_threat_model.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "broker_adapter_threat_model_review_ready"
    assert data["model_state"] == "review_only_no_adapter"
    assert "broker_credentials" in data["protected_assets"]
    assert "backend_to_future_broker_adapter" in data["trust_boundaries"]
    assert categories["credential_exposure"]["status"] == "blocked_by_design"
    assert categories["unauthorized_order_execution"]["status"] == "blocked_by_design"
    assert data["decision"]["threat_model_ready_for_review"] is True
    assert data["decision"]["broker_adapter_allowed_now"] is False
    assert data["decision"]["credential_handling_allowed_now"] is False
    assert data["decision"]["account_read_allowed_now"] is False
    assert data["decision"]["order_execution_allowed_now"] is False
    assert data["decision"]["ready_for_live_enablement"] is False
    assert data["safety_summary"]["broker_adapter_enabled"] is False
    assert data["safety_summary"]["credential_storage_enabled"] is False
    assert data["safety_summary"]["connects_broker"] is False
    assert data["safety_summary"]["places_real_trade"] is False


def test_broker_adapter_interface_draft_is_not_implemented_or_executable():
    data = TradeExecutionGatewayService().broker_adapter_interface_draft()
    method_names = {item["name"] for item in data["draft_methods"]}

    assert data["schema_version"] == "trade_execution_broker_adapter_interface_draft.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "broker_adapter_interface_draft_review_ready"
    assert data["interface_state"] == "draft_only_not_implemented"
    assert "describe_capabilities" in method_names
    assert "build_order_preview" in method_names
    assert all(item["implemented_now"] is False for item in data["draft_methods"])
    assert all(item["calls_broker_now"] is False for item in data["draft_methods"])
    assert all(item["places_order_now"] is False for item in data["draft_methods"])
    assert all(item["reads_account_now"] is False for item in data["draft_methods"])
    assert "submit_order" in data["forbidden_methods"]
    assert "read_account_funds" in data["forbidden_methods"]
    assert data["required_inputs_policy"]["allows_credentials"] is False
    assert data["decision"]["interface_implemented_now"] is False
    assert data["decision"]["adapter_can_connect_now"] is False
    assert data["decision"]["adapter_can_execute_now"] is False
    assert data["decision"]["adapter_can_read_account_now"] is False
    assert data["decision"]["ready_for_live_enablement"] is False
    assert data["safety_summary"]["implements_adapter_now"] is False
    assert data["safety_summary"]["makes_network_calls"] is False
    assert data["safety_summary"]["connects_broker"] is False
    assert data["safety_summary"]["places_real_trade"] is False


def test_broker_adapter_contract_verification_is_fixture_only_and_non_executable():
    data = TradeExecutionGatewayService().broker_adapter_contract_verification()
    checks = {item["name"]: item for item in data["checks"]}

    assert data["schema_version"] == "trade_execution_broker_adapter_contract_verification.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "fixture_contract_verification_passed"
    assert data["verification_state"] == "fixture_only_no_adapter"
    assert data["fixture_name"] == "broker_adapter_boundary_contract_v1"
    assert checks["draft_method_surface_present"]["status"] == "passed"
    assert checks["credential_inputs_rejected"]["status"] == "passed"
    assert checks["forbidden_methods_absent"]["status"] == "passed"
    assert checks["order_preview_non_executable"]["status"] == "passed"
    assert checks["network_and_state_mutation_blocked"]["fixture_evidence"]["makes_network_calls"] is False
    assert data["summary"]["total_checks"] == 8
    assert data["summary"]["blocked_checks"] == 0
    assert data["summary"]["fixture_only"] is True
    assert data["summary"]["network_calls"] is False
    assert data["summary"]["adapter_instantiated"] is False
    assert data["decision"]["fixture_contract_tests_passed"] is True
    assert data["decision"]["adapter_implemented_now"] is False
    assert data["decision"]["adapter_can_connect_now"] is False
    assert data["decision"]["adapter_can_execute_now"] is False
    assert data["decision"]["adapter_can_read_account_now"] is False
    assert data["decision"]["credentials_allowed_now"] is False
    assert data["decision"]["ready_for_live_enablement"] is False
    assert data["safety_summary"]["fixture_only_contract_verifier"] is True
    assert data["safety_summary"]["instantiates_adapter"] is False
    assert data["safety_summary"]["makes_network_calls"] is False
    assert data["safety_summary"]["writes_database_now"] is False
    assert data["safety_summary"]["connects_broker"] is False
    assert data["safety_summary"]["places_real_trade"] is False


def test_order_lifecycle_failure_fixtures_are_review_only_and_non_executable():
    data = TradeExecutionGatewayService().order_lifecycle_failure_fixtures()
    fixtures = {item["name"]: item for item in data["fixtures"]}

    assert data["schema_version"] == "trade_execution_order_lifecycle_failure_fixtures.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "order_failure_fixtures_ready"
    assert data["fixture_state"] == "review_only_no_order_lifecycle_engine"
    assert data["fixture_suite"] == "broker_order_lifecycle_failure_modes_v1"
    assert set(fixtures) == {
        "broker_rejected_order_preview",
        "partial_fill_preview",
        "stale_market_data_before_confirmation",
        "manual_confirmation_expired",
        "risk_gate_changed_after_preview",
        "limit_down_sell_blocked",
    }
    assert fixtures["broker_rejected_order_preview"]["expected_status"] == "rejected"
    assert fixtures["partial_fill_preview"]["expected_status"] == "partial"
    assert fixtures["stale_market_data_before_confirmation"]["expected_status"] == "blocked"
    assert fixtures["manual_confirmation_expired"]["fixture_payload"]["confirmation_ttl_seconds"] == 120
    assert fixtures["limit_down_sell_blocked"]["fixture_payload"]["side"] == "sell"
    assert all(item["can_submit_order"] is False for item in data["fixtures"])
    assert all(item["can_cancel_order"] is False for item in data["fixtures"])
    assert all(item["can_modify_order"] is False for item in data["fixtures"])
    assert all(item["connects_broker"] is False for item in data["fixtures"])
    assert all(item["requires_credentials"] is False for item in data["fixtures"])
    assert data["summary"]["fixture_count"] == 6
    assert data["summary"]["blocked_count"] == 4
    assert data["summary"]["partial_count"] == 1
    assert data["summary"]["rejected_count"] == 1
    assert data["summary"]["places_order"] is False
    assert data["summary"]["connects_broker"] is False
    assert data["summary"]["reads_account"] is False
    assert data["summary"]["requires_credentials"] is False
    assert data["decision"]["failure_fixtures_ready_for_review"] is True
    assert data["decision"]["can_replay_as_real_order"] is False
    assert data["decision"]["can_submit_order_now"] is False
    assert data["decision"]["can_cancel_order_now"] is False
    assert data["decision"]["can_modify_order_now"] is False
    assert data["decision"]["requires_broker_connection"] is False
    assert data["decision"]["requires_credentials"] is False
    assert data["decision"]["ready_for_live_enablement"] is False
    assert data["safety_summary"]["fixture_only_failure_modes"] is True
    assert data["safety_summary"]["order_lifecycle_engine_implemented"] is False
    assert data["safety_summary"]["connects_broker"] is False
    assert data["safety_summary"]["places_real_trade"] is False


def test_order_failure_runbook_mapping_is_review_only_and_non_executable():
    data = TradeExecutionGatewayService().order_failure_runbook_mapping()
    mappings = {item["fixture_name"]: item for item in data["mappings"]}

    assert data["schema_version"] == "trade_execution_order_failure_runbook_mapping.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "order_failure_runbook_mapping_ready"
    assert data["mapping_state"] == "review_only_no_runbook_execution"
    assert data["source_fixture_suite"] == "broker_order_lifecycle_failure_modes_v1"
    assert set(mappings) == {
        "broker_rejected_order_preview",
        "partial_fill_preview",
        "stale_market_data_before_confirmation",
        "manual_confirmation_expired",
        "risk_gate_changed_after_preview",
        "limit_down_sell_blocked",
    }
    assert mappings["broker_rejected_order_preview"]["manual_decision"] == "reject_preview_and_record_reason"
    assert mappings["partial_fill_preview"]["manual_decision"] == "reduce_or_cancel_preview"
    assert mappings["limit_down_sell_blocked"]["manual_decision"] == "block_sell_and_escalate_risk_review"
    assert "operator_review_note" in mappings["broker_rejected_order_preview"]["required_audit_evidence"]
    assert "proposal_hash" in mappings["broker_rejected_order_preview"]["required_hashes"]
    assert all(item["can_execute_runbook"] is False for item in data["mappings"])
    assert all(item["can_submit_order"] is False for item in data["mappings"])
    assert all(item["writes_database_now"] is False for item in data["mappings"])
    assert all(item["connects_broker"] is False for item in data["mappings"])
    assert data["summary"]["mapping_count"] == 6
    assert data["summary"]["manual_review_required_count"] == 6
    assert data["summary"]["audit_evidence_field_count"] >= 30
    assert data["summary"]["writes_database_now"] is False
    assert data["summary"]["executes_runbook_now"] is False
    assert data["decision"]["runbook_mapping_ready_for_review"] is True
    assert data["decision"]["can_execute_runbook_now"] is False
    assert data["decision"]["can_record_audit_now"] is False
    assert data["decision"]["can_submit_order_now"] is False
    assert data["decision"]["requires_broker_connection"] is False
    assert data["decision"]["requires_credentials"] is False
    assert data["decision"]["ready_for_live_enablement"] is False
    assert data["safety_summary"]["writes_database_now"] is False
    assert data["safety_summary"]["executes_runbook_now"] is False
    assert data["safety_summary"]["connects_broker"] is False
    assert data["safety_summary"]["places_real_trade"] is False


def test_audit_ledger_storage_plan_is_disabled_and_review_only():
    data = TradeExecutionGatewayService().audit_ledger_storage_plan()
    columns = {item["name"]: item for item in data["planned_columns"]}
    indexes = {item["name"]: item for item in data["proposed_indexes"]}

    assert data["schema_version"] == "trade_execution_audit_ledger_storage_plan.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "disabled_audit_ledger_storage_plan_ready"
    assert data["storage_state"] == "disabled_not_persisted"
    assert data["target_future_table"] == "trade_execution_audit_ledger"
    assert data["source_schema"] == "trade_execution_audit_evidence_schema.v1"
    assert data["source_runbook_mapping"] == "trade_execution_order_failure_runbook_mapping.v1"
    assert "audit_id" in columns
    assert "event_hash" in columns
    assert "previous_event_hash" in columns
    assert "runbook_reference" in columns
    assert columns["event_hash"]["create_now"] is False
    assert all(item["stores_sensitive_plaintext"] is False for item in data["planned_columns"])
    assert "idx_trade_execution_audit_ledger_event_hash" in indexes
    assert all(item["create_now"] is False for item in data["proposed_indexes"])
    assert data["hash_chain_policy"]["algorithm"] == "sha256"
    assert data["hash_chain_policy"]["previous_event_hash_required_after_first_row"] is True
    assert data["retention_policy"]["prune_api_enabled_now"] is False
    assert data["redaction_policy"]["raw_payload_storage_allowed"] is False
    assert "broker_password" in data["redaction_policy"]["excluded_sensitive_fields"]
    assert "dry_run_migration_spec_verifier_passed" in data["migration_preconditions"]
    assert "hash_chain_verifier_must_pass_after_restore" in data["rollback_requirements"]
    assert "create_table" in data["blocked_actions"]
    assert "write_audit_row" in data["blocked_actions"]
    assert data["summary"]["planned_column_count"] >= 12
    assert data["summary"]["proposed_index_count"] == 4
    assert data["summary"]["create_table_now"] is False
    assert data["summary"]["writes_database_now"] is False
    assert data["summary"]["runs_migration_now"] is False
    assert data["summary"]["writes_migration_file_now"] is False
    assert data["summary"]["records_audit_rows_now"] is False
    assert data["decision"]["storage_plan_ready_for_review"] is True
    assert data["decision"]["can_create_table_now"] is False
    assert data["decision"]["can_write_audit_row_now"] is False
    assert data["decision"]["can_run_migration_now"] is False
    assert data["decision"]["can_write_migration_file_now"] is False
    assert data["decision"]["requires_operator_approval_before_migration"] is True
    assert data["decision"]["requires_dry_run_verifier_before_migration"] is True
    assert data["decision"]["ready_for_live_enablement"] is False
    assert data["safety_summary"]["storage_plan_only"] is True
    assert data["safety_summary"]["writes_database_now"] is False
    assert data["safety_summary"]["runs_migration_now"] is False
    assert data["safety_summary"]["records_audit_rows_now"] is False
    assert data["safety_summary"]["connects_broker"] is False
    assert data["safety_summary"]["places_real_trade"] is False


def test_audit_ledger_migration_spec_verifier_is_dry_run_and_blocks_dangerous_specs():
    data = TradeExecutionGatewayService().verify_audit_ledger_migration_spec()
    checks = {item["name"]: item for item in data["checks"]}

    assert data["schema_version"] == "trade_execution_audit_ledger_migration_spec_verifier.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "spec_verification_passed"
    assert data["verification_state"] == "dry_run_in_memory_only"
    assert data["target_table"] == "trade_execution_audit_ledger"
    assert len(data["spec_hash"]) == 64
    assert data["failed_count"] == 0
    assert data["missing_columns"] == []
    assert data["missing_indexes"] == []
    assert checks["target_table_named"]["status"] == "passed"
    assert checks["required_columns_covered"]["status"] == "passed"
    assert checks["proposed_indexes_covered"]["status"] == "passed"
    assert checks["sensitive_fields_absent"]["status"] == "passed"
    assert checks["dangerous_sql_absent"]["status"] == "passed"
    assert data["migration_allowed_now"] is False
    assert data["summary"]["executes_sql"] is False
    assert data["summary"]["creates_table_now"] is False
    assert data["summary"]["writes_database_now"] is False
    assert data["summary"]["runs_migration_now"] is False
    assert data["summary"]["writes_migration_file_now"] is False
    assert data["summary"]["records_audit_rows_now"] is False
    assert data["decision"]["spec_verification_passed"] is True
    assert data["decision"]["can_execute_sql_now"] is False
    assert data["decision"]["can_create_table_now"] is False
    assert data["decision"]["can_run_migration_now"] is False
    assert data["decision"]["can_write_migration_file_now"] is False
    assert data["decision"]["can_write_audit_row_now"] is False
    assert data["safety_summary"]["dry_run_verifier_only"] is True
    assert data["safety_summary"]["executes_sql"] is False
    assert data["safety_summary"]["creates_table_now"] is False
    assert data["safety_summary"]["writes_database_now"] is False
    assert data["safety_summary"]["records_audit_rows_now"] is False
    assert data["allowed_output"] == "review_only_audit_ledger_migration_spec_verifier"
    assert data["review_only"] is True
    assert data["simulation_only"] is True
    assert data["live_trading_enabled"] is False

    dangerous = TradeExecutionGatewayService().verify_audit_ledger_migration_spec(
        "DROP TABLE trade_execution_audit_ledger; broker_password TEXT"
    )

    assert dangerous["status"] == "spec_verification_failed"
    assert "drop" in dangerous["dangerous_matches"]
    assert "broker_password" in dangerous["sensitive_matches"]
    assert dangerous["decision"]["can_execute_sql_now"] is False
    assert dangerous["decision"]["can_create_table_now"] is False
    assert dangerous["decision"]["can_write_audit_row_now"] is False
    assert dangerous["summary"]["executes_sql"] is False
    assert dangerous["summary"]["writes_database_now"] is False
    assert dangerous["live_trading_enabled"] is False


def test_audit_ledger_migration_spec_approval_is_existing_event_metadata_only(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")

    approval = service.approve_audit_ledger_migration_spec(
        approved_by="tester",
        note="reviewed verified dry-run spec",
    )
    approvals = service.list_audit_ledger_migration_spec_approvals(limit=5)

    assert approval["schema_version"] == "trade_execution_audit_ledger_migration_spec_approval.v1"
    assert approval["status"] == "approval_metadata_recorded"
    assert approval["stage"] == "V5.5-P24"
    assert approval["event_id"] is not None
    assert approval["approved_by"] == "tester"
    assert approval["approval_effect"] == "existing_event_metadata_only"
    assert approval["verification_status"] == "spec_verification_passed"
    assert approval["verification_failed_count"] == 0
    assert approval["target_table"] == "trade_execution_audit_ledger"
    assert len(approval["spec_hash"]) == 64
    assert approval["migration_allowed_now"] is False
    assert approval["safety_summary"]["writes_existing_event_now"] is True
    assert approval["safety_summary"]["writes_audit_ledger_row_now"] is False
    assert approval["safety_summary"]["creates_table_now"] is False
    assert approval["safety_summary"]["runs_migration_now"] is False
    assert approval["safety_summary"]["executes_sql"] is False
    assert approval["safety_summary"]["writes_migration_file_now"] is False
    assert approval["safety_summary"]["connects_broker"] is False
    assert approval["safety_summary"]["places_real_trade"] is False
    assert approval["allowed_output"] == "review_only_audit_ledger_migration_spec_approval_metadata"
    assert "reviewed_sqlite_migration_file" in approval["future_migration_still_requires"]
    assert "write_audit_ledger_row_now" in approval["forbidden_actions"]
    assert approval["review_only"] is True
    assert approval["simulation_only"] is True
    assert approval["live_trading_enabled"] is False
    assert approvals[0]["event_id"] == approval["event_id"]
    assert approvals[0]["event_type"] == "trade_audit_ledger_migration_spec_approval"
    assert approvals[0]["approval_effect"] == "existing_event_metadata_only"


def test_audit_ledger_migration_spec_approval_blocks_failed_spec(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")

    approval = service.approve_audit_ledger_migration_spec(
        spec_text="DROP TABLE trade_execution_audit_ledger; broker_password TEXT",
        approved_by="tester",
        note="unsafe spec should not be approved",
    )
    approvals = service.list_audit_ledger_migration_spec_approvals(limit=5)

    assert approval["status"] == "approval_blocked"
    assert approval["event_id"] is None
    assert approval["verification_status"] == "spec_verification_failed"
    assert approval["verification"]["status"] == "spec_verification_failed"
    assert approval["safety_summary"]["writes_existing_event_now"] is False
    assert approval["safety_summary"]["writes_audit_ledger_row_now"] is False
    assert approval["safety_summary"]["executes_sql"] is False
    assert approval["migration_allowed_now"] is False
    assert approvals == []
    assert approval["live_trading_enabled"] is False


def test_audit_ledger_migration_release_readiness_requires_approval(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")

    data = service.audit_ledger_migration_release_readiness(limit=5)
    gates = {gate["name"]: gate for gate in data["gates"]}

    assert data["schema_version"] == "trade_execution_audit_ledger_migration_release_readiness.v1"
    assert data["status"] == "release_review_required"
    assert data["stage"] == "V5.5-P24"
    assert data["decision"]["go_no_go"] == "no_go"
    assert data["decision"]["migration_allowed_now"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["decision"]["requires_human_release_approval"] is True
    assert data["evidence"]["storage_plan_status"] == "disabled_audit_ledger_storage_plan_ready"
    assert data["evidence"]["verification_status"] == "spec_verification_passed"
    assert data["evidence"]["approval_count"] == 0
    assert gates["storage_plan_ready"]["status"] == "passed"
    assert gates["migration_spec_verified"]["status"] == "passed"
    assert gates["operator_approval_metadata_recorded"]["status"] == "review_required"
    assert gates["latest_approval_matches_current_spec"]["status"] == "review_required"
    assert data["safety_summary"]["executes_sql"] is False
    assert data["safety_summary"]["runs_migration_now"] is False
    assert data["safety_summary"]["writes_audit_ledger_row_now"] is False
    assert data["safety_summary"]["approves_release_now"] is False
    assert data["safety_summary"]["connects_broker"] is False
    assert data["allowed_output"] == "review_only_audit_ledger_migration_release_readiness"
    assert "execute_sql" in data["forbidden_actions"]
    assert data["review_only"] is True
    assert data["simulation_only"] is True
    assert data["live_trading_enabled"] is False


def test_audit_ledger_migration_release_readiness_summarizes_approved_spec(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
    approval = service.approve_audit_ledger_migration_spec(
        approved_by="release-reviewer",
        note="ready for manual release review evidence",
    )

    data = service.audit_ledger_migration_release_readiness(limit=5)
    gates = {gate["name"]: gate for gate in data["gates"]}

    assert data["status"] == "release_evidence_ready"
    assert data["decision"]["go_no_go"] == "go_for_manual_release_review"
    assert data["decision"]["migration_allowed_now"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["evidence"]["approval_count"] == 1
    assert data["evidence"]["latest_approval_event_id"] == approval["event_id"]
    assert data["evidence"]["spec_hash"] == approval["spec_hash"]
    assert data["evidence"]["approved_spec_hash"] == approval["spec_hash"]
    assert all(gate["status"] == "passed" for gate in data["gates"])
    assert gates["no_migration_execution_enabled"]["status"] == "passed"
    assert gates["safety_summary_clean"]["status"] == "passed"
    assert data["blocked_gates"] == []
    assert data["review_required_gates"] == []
    assert "explicit_operator_release_approval" in data["required_before_actual_migration"]
    assert data["safety_summary"]["writes_database_now"] is False
    assert data["safety_summary"]["writes_migration_file_now"] is False
    assert data["safety_summary"]["writes_audit_ledger_row_now"] is False
    assert data["safety_summary"]["enables_gateway_now"] is False
    assert data["safety_summary"]["places_real_trade"] is False


def test_audit_ledger_migration_approval_review_requires_approval(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")

    data = service.audit_ledger_migration_approval_review(limit=5, max_age_days=7)
    gates = {gate["name"]: gate for gate in data["gates"]}

    assert data["schema_version"] == "trade_execution_audit_ledger_migration_approval_review.v1"
    assert data["status"] == "approval_review_required"
    assert data["stage"] == "V5.5-P24"
    assert data["review_policy"]["max_age_days"] == 7
    assert data["latest_approval"]["event_id"] is None
    assert data["latest_approval"]["is_expired"] is False
    assert data["latest_approval"]["matches_current_spec"] is False
    assert data["release_readiness"]["status"] == "release_review_required"
    assert gates["approval_recorded"]["status"] == "review_required"
    assert gates["approval_within_validity_window"]["status"] == "review_required"
    assert gates["approval_matches_current_spec"]["status"] == "review_required"
    assert data["decision"]["next_required_action"] == "record_operator_approval_metadata"
    assert data["decision"]["approval_can_be_reused_for_manual_release_review"] is False
    assert data["decision"]["migration_allowed_now"] is False
    assert data["safety_summary"]["executes_sql"] is False
    assert data["safety_summary"]["writes_audit_ledger_row_now"] is False
    assert data["safety_summary"]["approves_release_now"] is False
    assert data["allowed_output"] == "review_only_audit_ledger_migration_approval_review"
    assert "reuse_expired_approval_as_current" in data["forbidden_actions"]
    assert data["live_trading_enabled"] is False


def test_audit_ledger_migration_approval_review_accepts_current_approval(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
    approval = service.approve_audit_ledger_migration_spec(
        approved_by="freshness-reviewer",
        note="fresh approval metadata",
    )

    data = service.audit_ledger_migration_approval_review(limit=5, max_age_days=7)

    assert data["status"] == "approval_current"
    assert data["latest_approval"]["event_id"] == approval["event_id"]
    assert data["latest_approval"]["is_expired"] is False
    assert data["latest_approval"]["matches_current_spec"] is True
    assert data["current_spec"]["spec_hash"] == approval["spec_hash"]
    assert data["release_readiness"]["status"] == "release_evidence_ready"
    assert data["decision"]["next_required_action"] == "none"
    assert data["decision"]["approval_can_be_reused_for_manual_release_review"] is True
    assert all(gate["status"] == "passed" for gate in data["gates"])
    assert data["blocked_gates"] == []
    assert data["review_required_gates"] == []
    assert data["safety_summary"]["runs_migration_now"] is False
    assert data["safety_summary"]["enables_gateway_now"] is False
    assert data["safety_summary"]["places_real_trade"] is False


def test_audit_ledger_migration_approval_review_requires_rotation_for_expired_metadata(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
    approval = service.approve_audit_ledger_migration_spec(
        approved_by="stale-reviewer",
        note="stale approval metadata",
    )
    old_approved_at = (datetime.now() - timedelta(days=10)).isoformat(timespec="seconds")
    with service.store.connect() as conn:
        row = conn.execute(
            "SELECT payload_json FROM events WHERE id = ?",
            (approval["event_id"],),
        ).fetchone()
        payload = json.loads(row["payload_json"])
        payload["approved_at"] = old_approved_at
        conn.execute(
            "UPDATE events SET payload_json = ? WHERE id = ?",
            (json.dumps(payload, ensure_ascii=False, sort_keys=True), approval["event_id"]),
        )

    data = service.audit_ledger_migration_approval_review(limit=5, max_age_days=7)
    gates = {gate["name"]: gate for gate in data["gates"]}

    assert data["status"] == "approval_rotation_required"
    assert data["latest_approval"]["event_id"] == approval["event_id"]
    assert data["latest_approval"]["is_expired"] is True
    assert data["latest_approval"]["approval_age_days"] is not None
    assert data["latest_approval"]["approval_age_days"] > 7
    assert data["latest_approval"]["matches_current_spec"] is True
    assert gates["approval_within_validity_window"]["status"] == "review_required"
    assert data["decision"]["next_required_action"] == "refresh_operator_approval_metadata"
    assert data["decision"]["approval_can_be_reused_for_manual_release_review"] is False
    assert data["safety_summary"]["executes_sql"] is False
    assert data["safety_summary"]["writes_migration_file_now"] is False
    assert data["live_trading_enabled"] is False


def test_audit_ledger_migration_release_package_requires_complete_evidence(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")

    data = service.audit_ledger_migration_release_package(limit=5, max_age_days=7)
    gates = {gate["name"]: gate for gate in data["gates"]}
    items = {item["name"]: item for item in data["manifest"]["items"]}

    assert data["schema_version"] == "trade_execution_audit_ledger_migration_release_package.v1"
    assert data["status"] == "release_package_review_required"
    assert data["stage"] == "V5.5-P24"
    assert len(data["package_id"]) == 64
    assert data["manifest"]["delivery"] == "api_response_only"
    assert data["manifest"]["writes_file"] is False
    assert data["manifest"]["download_created"] is False
    assert items["P4_disabled_audit_ledger_storage_plan"]["safety_passed"] is True
    assert items["P5_migration_spec_verifier"]["safety_passed"] is True
    assert items["P6_approval_metadata"]["status"] == "missing"
    assert gates["approval_current"]["status"] == "review_required"
    assert data["decision"]["go_no_go"] == "no_go"
    assert data["decision"]["migration_allowed_now"] is False
    assert data["decision"]["execution_allowed_now"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["decision"]["next_required_action"] == "complete_missing_release_evidence"
    assert data["safety_summary"]["writes_file"] is False
    assert data["safety_summary"]["download_created"] is False
    assert data["safety_summary"]["writes_audit_ledger_row_now"] is False
    assert "write_release_package_file" in data["forbidden_actions"]
    assert data["live_trading_enabled"] is False


def test_audit_ledger_migration_release_package_ready_after_current_approval(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
    approval = service.approve_audit_ledger_migration_spec(
        approved_by="package-reviewer",
        note="package-ready approval metadata",
    )

    data = service.audit_ledger_migration_release_package(limit=5, max_age_days=7)
    items = {item["name"]: item for item in data["manifest"]["items"]}

    assert data["status"] == "release_package_ready_for_manual_review"
    assert data["decision"]["go_no_go"] == "ready_for_manual_release_review"
    assert data["decision"]["next_required_action"] == "manual_release_review"
    assert data["decision"]["execution_allowed_now"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["evidence"]["latest_approval_event_id"] == approval["event_id"]
    assert data["evidence"]["spec_hash"] == approval["spec_hash"]
    assert data["evidence"]["approved_spec_hash"] == approval["spec_hash"]
    assert all(item["safety_passed"] is True for item in items.values())
    assert all(gate["status"] == "passed" for gate in data["gates"])
    assert data["blocked_gates"] == []
    assert data["review_required_gates"] == []
    assert "explicit_operator_release_approval" in data["manifest"]["required_manual_artifacts_before_execution"]
    assert data["safety_summary"]["executes_sql"] is False
    assert data["safety_summary"]["runs_migration_now"] is False
    assert data["safety_summary"]["writes_migration_file_now"] is False
    assert data["safety_summary"]["writes_audit_ledger_row_now"] is False
    assert data["safety_summary"]["enables_gateway_now"] is False
    assert data["safety_summary"]["places_real_trade"] is False


def test_audit_ledger_migration_release_package_integrity_passes_with_pending_evidence(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")

    data = service.audit_ledger_migration_release_package_integrity_review(
        limit=5,
        max_age_days=7,
        repeat_checks=3,
    )
    checks = {check["name"]: check for check in data["checks"]}

    assert data["schema_version"] == "trade_execution_audit_ledger_migration_release_package_integrity_review.v1"
    assert data["status"] == "integrity_review_passed_release_evidence_pending"
    assert data["stage"] == "V5.5-P24"
    assert data["source_package_status"] == "release_package_review_required"
    assert data["source_package_id"] == data["recomputed_package_id"]
    assert data["repeat_checks"] == 3
    assert len(set(data["repeated_package_ids"])) == 1
    assert data["failed_check_count"] == 0
    assert checks["package_id_recomputable"]["status"] == "passed"
    assert checks["package_id_stable_across_reads"]["status"] == "passed"
    assert checks["required_manifest_items_present"]["status"] == "passed"
    assert checks["api_response_only_delivery"]["status"] == "passed"
    assert data["manifest_summary"]["item_count"] == 5
    assert data["manifest_summary"]["writes_file"] is False
    assert data["manifest_summary"]["download_created"] is False
    assert data["decision"]["manifest_integrity_passed"] is True
    assert data["decision"]["release_package_ready"] is False
    assert data["decision"]["go_no_go"] == "no_go"
    assert data["decision"]["execution_allowed_now"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["decision"]["next_required_action"] == "complete_missing_release_evidence"
    assert data["safety_summary"]["mutates_source_package"] is False
    assert data["safety_summary"]["writes_file"] is False
    assert "approve_release_from_integrity_review" in data["forbidden_actions"]
    assert "persist_integrity_snapshot" in data["forbidden_actions"]
    assert data["live_trading_enabled"] is False


def test_audit_ledger_migration_release_package_integrity_passes_when_package_ready(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
    approval = service.approve_audit_ledger_migration_spec(
        approved_by="integrity-reviewer",
        note="integrity package-ready approval metadata",
    )

    data = service.audit_ledger_migration_release_package_integrity_review(
        limit=5,
        max_age_days=7,
        repeat_checks=2,
    )
    checks = {check["name"]: check for check in data["checks"]}

    assert data["status"] == "integrity_review_passed"
    assert data["source_package_status"] == "release_package_ready_for_manual_review"
    assert data["source_package_id"] == data["recomputed_package_id"]
    assert len(set(data["repeated_package_ids"])) == 1
    assert data["failed_checks"] == []
    assert all(check["status"] == "passed" for check in data["checks"])
    assert checks["evidence_matches_package_inputs"]["status"] == "passed"
    assert checks["safety_summary_allows_no_mutation"]["status"] == "passed"
    assert data["decision"]["package_id_stable"] is True
    assert data["decision"]["manifest_integrity_passed"] is True
    assert data["decision"]["release_package_ready"] is True
    assert data["decision"]["go_no_go"] == "ready_for_manual_release_review"
    assert data["decision"]["migration_allowed_now"] is False
    assert data["decision"]["execution_allowed_now"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["decision"]["next_required_action"] == "manual_release_review"
    assert approval["event_id"] is not None
    assert data["safety_summary"]["executes_sql"] is False
    assert data["safety_summary"]["writes_audit_ledger_row_now"] is False
    assert data["safety_summary"]["enables_gateway_now"] is False
    assert data["safety_summary"]["places_real_trade"] is False


def test_audit_ledger_migration_manual_release_rehearsal_waits_for_release_evidence(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")

    data = service.audit_ledger_migration_manual_release_review_rehearsal(
        limit=5,
        max_age_days=7,
        repeat_checks=2,
    )
    steps = {step["name"]: step for step in data["steps"]}

    assert data["schema_version"] == "trade_execution_audit_ledger_migration_manual_release_rehearsal.v1"
    assert data["status"] == "manual_release_rehearsal_waiting_for_evidence"
    assert data["stage"] == "V5.5-P24"
    assert len(data["rehearsal_id"]) == 64
    assert data["integrity_status"] == "integrity_review_passed_release_evidence_pending"
    assert data["source_package_status"] == "release_package_review_required"
    assert steps["confirm_package_identity"]["status"] == "ready_for_manual_review"
    assert steps["review_integrity_checks"]["status"] == "ready_for_manual_review"
    assert steps["confirm_release_evidence_ready"]["status"] == "pending_evidence"
    assert all(step["api_can_mark_complete"] is False for step in data["steps"])
    assert all(step["api_can_record_approval"] is False for step in data["steps"])
    assert data["pending_steps"]
    assert data["failed_steps"] == []
    assert data["operator_rehearsal_policy"]["api_can_record_operator_review"] is False
    assert data["operator_rehearsal_policy"]["api_can_approve_release"] is False
    assert data["decision"]["rehearsal_ready_for_operator"] is False
    assert data["decision"]["go_no_go"] == "no_go"
    assert data["decision"]["manual_review_recorded_now"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["decision"]["migration_allowed_now"] is False
    assert data["decision"]["execution_allowed_now"] is False
    assert data["safety_summary"]["records_manual_review_now"] is False
    assert data["safety_summary"]["writes_database_now"] is False
    assert "record_manual_release_review_by_api" in data["forbidden_actions"]
    assert "approve_release_from_rehearsal" in data["forbidden_actions"]
    assert data["live_trading_enabled"] is False


def test_audit_ledger_migration_manual_release_rehearsal_ready_after_approval(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
    approval = service.approve_audit_ledger_migration_spec(
        approved_by="rehearsal-reviewer",
        note="manual release rehearsal approval metadata",
    )

    data = service.audit_ledger_migration_manual_release_review_rehearsal(
        limit=5,
        max_age_days=7,
        repeat_checks=2,
    )
    steps = {step["name"]: step for step in data["steps"]}

    assert data["status"] == "manual_release_rehearsal_ready"
    assert data["source_package_status"] == "release_package_ready_for_manual_review"
    assert data["integrity_status"] == "integrity_review_passed"
    assert all(step["status"] == "ready_for_manual_review" for step in data["steps"])
    assert steps["verify_no_api_release_approval"]["evidence"]["release_approved_now"] is False
    assert data["pending_steps"] == []
    assert data["failed_steps"] == []
    assert "signed_manual_release_review" in data["required_offline_artifacts"]
    assert data["decision"]["rehearsal_ready_for_operator"] is True
    assert data["decision"]["go_no_go"] == "ready_for_offline_manual_review"
    assert data["decision"]["next_required_action"] == "perform_offline_manual_release_review"
    assert data["decision"]["manual_review_recorded_now"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["decision"]["gateway_can_execute"] is False
    assert data["operator_rehearsal_policy"]["offline_human_review_required"] is True
    assert data["operator_rehearsal_policy"]["dual_control_required_before_future_execution"] is True
    assert data["safety_summary"]["marks_rehearsal_complete_now"] is False
    assert data["safety_summary"]["approves_release_now"] is False
    assert data["safety_summary"]["writes_audit_ledger_row_now"] is False
    assert approval["event_id"] is not None


def test_audit_ledger_migration_manual_release_evidence_verifier_requires_artifacts(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")

    data = service.verify_audit_ledger_migration_manual_release_evidence(
        evidence={},
        limit=5,
        max_age_days=7,
        repeat_checks=2,
    )
    checks = {check["name"]: check for check in data["checks"]}

    assert data["schema_version"] == "trade_execution_audit_ledger_migration_manual_release_evidence_verifier.v1"
    assert data["status"] == "manual_release_evidence_missing"
    assert data["stage"] == "V5.5-P24"
    assert data["rehearsal_status"] == "manual_release_rehearsal_waiting_for_evidence"
    assert data["missing_artifacts"] == data["required_artifacts"]
    assert checks["rehearsal_ready"]["status"] == "failed"
    assert checks["required_artifacts_present_once"]["status"] == "failed"
    assert checks["payload_safety_flags"]["status"] == "failed"
    assert data["decision"]["evidence_complete"] is False
    assert data["decision"]["go_no_go"] == "no_go"
    assert data["decision"]["manual_review_recorded_now"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["decision"]["migration_allowed_now"] is False
    assert data["decision"]["execution_allowed_now"] is False
    assert data["safety_summary"]["persists_manual_release_evidence"] is False
    assert data["safety_summary"]["writes_database_now"] is False
    assert "persist_manual_release_evidence" in data["forbidden_actions"]
    assert "approve_release_from_evidence_verifier" in data["forbidden_actions"]
    assert data["live_trading_enabled"] is False


def test_audit_ledger_migration_manual_release_evidence_verifier_passes_complete_fixture(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
    approval = service.approve_audit_ledger_migration_spec(
        approved_by="evidence-reviewer",
        note="manual release evidence verifier approval metadata",
    )
    rehearsal = service.audit_ledger_migration_manual_release_review_rehearsal(
        limit=5,
        max_age_days=7,
        repeat_checks=2,
    )
    evidence = {
        "source_package_id": rehearsal["source_package_id"],
        "rehearsal_id": rehearsal["rehearsal_id"],
        "artifacts": [
            {
                "name": name,
                "present": True,
                "artifact_hash": f"artifact-{index:02d}-0123456789abcdef",
                "reviewed_by": "offline-operator",
                "reviewed_at": "2026-05-31T15:00:00",
                "review_note": "offline evidence reviewed",
            }
            for index, name in enumerate(rehearsal["required_offline_artifacts"], start=1)
        ],
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": False,
    }

    data = service.verify_audit_ledger_migration_manual_release_evidence(
        evidence=evidence,
        limit=5,
        max_age_days=7,
        repeat_checks=2,
    )
    checks = {check["name"]: check for check in data["checks"]}

    assert data["status"] == "manual_release_evidence_verification_passed"
    assert data["source_package_id"] == rehearsal["source_package_id"]
    assert data["rehearsal_id"] == rehearsal["rehearsal_id"]
    assert data["rehearsal_status"] == "manual_release_rehearsal_ready"
    assert data["missing_artifacts"] == []
    assert data["duplicate_artifacts"] == []
    assert data["failed_checks"] == []
    assert all(check["status"] == "passed" for check in data["checks"])
    assert checks["no_forbidden_evidence_fields"]["status"] == "passed"
    assert checks["verifier_remains_non_executable"]["status"] == "passed"
    assert data["decision"]["evidence_complete"] is True
    assert data["decision"]["go_no_go"] == "evidence_complete_for_offline_review"
    assert data["decision"]["manual_review_recorded_now"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["decision"]["gateway_can_execute"] is False
    assert data["safety_summary"]["persists_manual_release_evidence"] is False
    assert data["safety_summary"]["records_manual_review_now"] is False
    assert data["safety_summary"]["writes_audit_ledger_row_now"] is False
    assert approval["event_id"] is not None


def test_audit_ledger_migration_manual_release_evidence_verifier_blocks_forbidden_fields(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
    service.approve_audit_ledger_migration_spec(
        approved_by="evidence-reviewer",
        note="manual release evidence verifier forbidden-field fixture",
    )
    rehearsal = service.audit_ledger_migration_manual_release_review_rehearsal(limit=5)
    artifacts = [
        {
            "name": name,
            "present": True,
            "artifact_hash": f"artifact-{index:02d}-0123456789abcdef",
            "reviewed_by": "offline-operator",
            "reviewed_at": "2026-05-31T15:00:00",
        }
        for index, name in enumerate(rehearsal["required_offline_artifacts"], start=1)
    ]
    artifacts[0]["sql_text"] = "CREATE TABLE trade_execution_audit_ledger (...)"

    data = service.verify_audit_ledger_migration_manual_release_evidence(
        evidence={
            "source_package_id": rehearsal["source_package_id"],
            "rehearsal_id": rehearsal["rehearsal_id"],
            "artifacts": artifacts,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        },
        limit=5,
    )
    checks = {check["name"]: check for check in data["checks"]}

    assert data["status"] == "manual_release_evidence_verification_failed"
    assert checks["no_forbidden_evidence_fields"]["status"] == "failed"
    assert "sql_text" in checks["no_forbidden_evidence_fields"]["details"]["forbidden_field_hits"]
    assert data["decision"]["evidence_complete"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["safety_summary"]["executes_sql"] is False


def test_audit_ledger_migration_manual_release_evidence_comparison_requires_two_payloads(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")

    data = service.compare_audit_ledger_migration_manual_release_evidence(
        baseline_evidence={},
        candidate_evidence={},
        limit=5,
    )
    checks = {check["name"]: check for check in data["checks"]}

    assert data["schema_version"] == "trade_execution_audit_ledger_migration_manual_release_evidence_comparison.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "manual_release_evidence_comparison_missing"
    assert checks["baseline_and_candidate_present"]["status"] == "failed"
    assert data["decision"]["evidence_pair_stable"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["decision"]["migration_allowed_now"] is False
    assert data["decision"]["execution_allowed_now"] is False
    assert data["safety_summary"]["persists_manual_release_evidence_comparison"] is False
    assert data["safety_summary"]["writes_database_now"] is False
    assert data["safety_summary"]["writes_file"] is False
    assert "persist_manual_release_evidence_comparison" in data["forbidden_actions"]


def test_audit_ledger_migration_manual_release_evidence_comparison_is_stable_for_same_fixture(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
    service.approve_audit_ledger_migration_spec(
        approved_by="evidence-reviewer",
        note="manual release evidence comparison fixture",
    )
    evidence = _complete_manual_release_evidence(service)

    data = service.compare_audit_ledger_migration_manual_release_evidence(
        baseline_evidence=evidence,
        candidate_evidence=evidence,
        limit=5,
    )
    checks = {check["name"]: check for check in data["checks"]}

    assert data["status"] == "manual_release_evidence_comparison_stable"
    assert data["baseline"]["status"] == "manual_release_evidence_verification_passed"
    assert data["candidate"]["status"] == "manual_release_evidence_verification_passed"
    assert data["artifact_names_added"] == []
    assert data["artifact_names_removed"] == []
    assert data["artifact_hash_changes"] == []
    assert data["artifact_review_changes"] == []
    assert data["check_status_differences"] == []
    assert all(check["status"] == "passed" for check in data["checks"])
    assert checks["comparison_remains_non_executable"]["status"] == "passed"
    assert data["decision"]["evidence_pair_stable"] is True
    assert data["decision"]["go_no_go"] == "stable_evidence_pair_for_offline_review"
    assert data["decision"]["release_approved_now"] is False
    assert data["decision"]["gateway_can_execute"] is False
    assert data["safety_summary"]["mutates_evidence"] is False
    assert data["safety_summary"]["persists_manual_release_evidence_comparison"] is False


def test_audit_ledger_migration_manual_release_evidence_comparison_reports_hash_changes(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
    service.approve_audit_ledger_migration_spec(
        approved_by="evidence-reviewer",
        note="manual release evidence comparison changed fixture",
    )
    baseline = _complete_manual_release_evidence(service)
    candidate = json.loads(json.dumps(baseline))
    candidate["artifacts"][0]["artifact_hash"] = "changed-artifact-hash-0123456789abcdef"

    data = service.compare_audit_ledger_migration_manual_release_evidence(
        baseline_evidence=baseline,
        candidate_evidence=candidate,
        limit=5,
    )
    checks = {check["name"]: check for check in data["checks"]}

    assert data["status"] == "manual_release_evidence_comparison_changed"
    assert data["artifact_hash_changes"][0]["name"] == baseline["artifacts"][0]["name"]
    assert checks["artifact_hashes_stable"]["status"] == "failed"
    assert data["decision"]["evidence_pair_stable"] is False
    assert data["decision"]["go_no_go"] == "no_go"
    assert data["decision"]["release_approved_now"] is False
    assert data["safety_summary"]["executes_sql"] is False
    assert data["safety_summary"]["writes_database_now"] is False


def test_audit_ledger_migration_manual_release_health_digest_requires_evidence(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")

    data = service.audit_ledger_migration_manual_release_health_digest(
        baseline_evidence={},
        candidate_evidence={},
        limit=5,
    )
    checks = {check["name"]: check for check in data["checks"]}
    modules = {item["name"]: item for item in data["module_statuses"]}

    assert data["schema_version"] == "trade_execution_audit_ledger_migration_manual_release_health_digest.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "manual_release_health_digest_attention_required"
    assert modules["manual_release_package"]["status"] == "release_package_review_required"
    assert modules["manual_release_evidence_verifier"]["status"] == "manual_release_evidence_missing"
    assert modules["manual_release_evidence_comparison"]["status"] == "manual_release_evidence_comparison_missing"
    assert checks["evidence_verification_passed"]["status"] == "failed"
    assert checks["evidence_comparison_stable"]["status"] == "failed"
    assert data["summary"]["attention_count"] >= 1
    assert data["summary"]["missing_artifact_count"] >= 1
    assert data["decision"]["digest_healthy"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["decision"]["migration_allowed_now"] is False
    assert data["decision"]["execution_allowed_now"] is False
    assert data["safety_summary"]["persists_manual_release_health_digest"] is False
    assert data["safety_summary"]["writes_database_now"] is False
    assert data["safety_summary"]["writes_file"] is False
    assert "persist_manual_release_health_digest" in data["forbidden_actions"]


def test_audit_ledger_migration_manual_release_health_digest_is_healthy_for_complete_stable_evidence(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
    service.approve_audit_ledger_migration_spec(
        approved_by="evidence-reviewer",
        note="manual release health digest fixture",
    )
    evidence = _complete_manual_release_evidence(service)

    data = service.audit_ledger_migration_manual_release_health_digest(
        baseline_evidence=evidence,
        candidate_evidence=evidence,
        limit=5,
    )
    checks = {check["name"]: check for check in data["checks"]}

    assert data["status"] == "manual_release_health_digest_healthy"
    assert data["health_flags"]["release_package_ready"] is True
    assert data["health_flags"]["integrity_passed"] is True
    assert data["health_flags"]["rehearsal_ready"] is True
    assert data["health_flags"]["evidence_verified"] is True
    assert data["health_flags"]["evidence_pair_stable"] is True
    assert data["summary"]["attention_count"] == 0
    assert data["summary"]["changed_artifact_hash_count"] == 0
    assert all(check["status"] == "passed" for check in data["checks"])
    assert checks["digest_remains_non_executable"]["status"] == "passed"
    assert data["decision"]["digest_healthy"] is True
    assert data["decision"]["go_no_go"] == "health_digest_ready_for_offline_review"
    assert data["decision"]["release_approved_now"] is False
    assert data["decision"]["gateway_can_execute"] is False
    assert data["safety_summary"]["persists_manual_release_health_digest"] is False
    assert data["safety_summary"]["executes_sql"] is False



def test_audit_ledger_migration_manual_release_health_digest_history_retention_proposal_is_metadata_only(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
    service.approve_audit_ledger_migration_spec(
        approved_by="history-reviewer",
        note="manual release health digest history retention fixture",
    )
    evidence = _complete_manual_release_evidence(service)

    data = service.audit_ledger_migration_manual_release_health_digest_history_retention_proposal(
        baseline_evidence=evidence,
        candidate_evidence=evidence,
        limit=5,
    )
    gates = {gate["name"]: gate for gate in data["review_gates"]}

    assert data["schema_version"] == "trade_execution_audit_ledger_migration_manual_release_health_digest_history_retention_proposal.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "history_retention_proposal_ready"
    assert data["proposal"]["default_state"] == "not_persisted"
    assert data["proposal"]["storage_mode"] == "future_reviewed_metadata_only_table"
    assert "digest_id" in data["proposal"]["required_fields"]
    assert "raw_manual_release_evidence" in data["proposal"]["excluded_fields"]
    assert "broker_credentials" in data["proposal"]["excluded_fields"]
    assert data["current_digest_summary"]["digest_status"] == "manual_release_health_digest_healthy"
    assert data["current_digest_summary"]["failed_check_names"] == []
    assert gates["metadata_only_required"]["status"] == "passed"
    assert gates["migration_review_required"]["status"] == "passed"
    assert data["summary"]["persists_history_now"] is False
    assert data["decision"]["proposal_ready_for_manual_review"] is True
    assert data["decision"]["history_persistence_enabled_now"] is False
    assert data["decision"]["can_create_table_now"] is False
    assert data["decision"]["can_write_history_row_now"] is False
    assert data["decision"]["can_run_migration_now"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["decision"]["execution_allowed_now"] is False
    assert data["safety_summary"]["persists_manual_release_health_digest_history"] is False
    assert data["safety_summary"]["writes_database_now"] is False
    assert data["safety_summary"]["executes_sql"] is False
    assert data["safety_summary"]["writes_file"] is False
    assert "persist_manual_release_health_digest_history" in data["forbidden_actions"]


def test_audit_ledger_migration_manual_release_health_digest_history_migration_readiness_checklist_is_review_only(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
    service.approve_audit_ledger_migration_spec(
        approved_by="history-migration-reviewer",
        note="manual release health digest history migration readiness fixture",
    )
    evidence = _complete_manual_release_evidence(service)

    data = service.audit_ledger_migration_manual_release_health_digest_history_migration_readiness_checklist(
        baseline_evidence=evidence,
        candidate_evidence=evidence,
        limit=5,
    )
    checks = {check["name"]: check for check in data["checks"]}

    assert data["schema_version"] == "trade_execution_audit_ledger_migration_manual_release_health_digest_history_migration_readiness_checklist.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "history_migration_readiness_review_ready"
    assert data["source_proposal"]["status"] == "history_retention_proposal_ready"
    assert data["migration_plan"]["target_table"] == "manual_release_health_digest_history"
    assert data["migration_plan"]["create_table_now"] is False
    assert data["migration_plan"]["writes_database_now"] is False
    assert data["migration_plan"]["writes_migration_file_now"] is False
    assert data["migration_plan"]["operator_review_required"] is True
    assert len(data["field_mapping"]) >= 10
    assert "raw_manual_release_evidence" in data["excluded_fields"]
    assert "broker_credentials" in data["excluded_fields"]
    assert "plaintext_secrets" in data["excluded_fields"]
    assert checks["proposal_available"]["status"] == "passed"
    assert checks["sensitive_fields_excluded"]["status"] == "passed"
    assert checks["migration_file_required"]["status"] == "review_required"
    assert checks["rollback_plan_required"]["status"] == "review_required"
    assert checks["test_plan_required"]["status"] == "review_required"
    assert data["summary"]["blocked_check_count"] == 0
    assert data["summary"]["review_required_count"] == 3
    assert data["summary"]["migration_allowed_now"] is False
    assert data["decision"]["migration_readiness_review_ready"] is True
    assert data["decision"]["history_persistence_enabled_now"] is False
    assert data["decision"]["can_create_table_now"] is False
    assert data["decision"]["can_write_history_row_now"] is False
    assert data["decision"]["can_run_migration_now"] is False
    assert data["decision"]["can_write_migration_file_now"] is False
    assert data["decision"]["migration_allowed_now"] is False
    assert data["decision"]["execution_allowed_now"] is False
    assert data["decision"]["go_no_go"] == "ready_for_future_migration_spec_review"
    assert data["safety_summary"]["persists_manual_release_health_digest_history"] is False
    assert data["safety_summary"]["writes_database_now"] is False
    assert data["safety_summary"]["creates_table_now"] is False
    assert data["safety_summary"]["executes_sql"] is False
    assert data["safety_summary"]["writes_file"] is False
    assert "run_history_migration" in data["forbidden_actions"]
    assert "write_migration_file" in data["forbidden_actions"]


def test_audit_ledger_migration_manual_release_health_digest_history_migration_spec_verifier_is_dry_run(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
    service.approve_audit_ledger_migration_spec(
        approved_by="history-spec-reviewer",
        note="manual release health digest history migration spec verifier fixture",
    )
    evidence = _complete_manual_release_evidence(service)

    data = service.verify_audit_ledger_migration_manual_release_health_digest_history_migration_spec(
        baseline_evidence=evidence,
        candidate_evidence=evidence,
        limit=5,
    )
    checks = {check["name"]: check for check in data["checks"]}

    assert data["schema_version"] == "trade_execution_audit_ledger_migration_manual_release_health_digest_history_migration_spec_verifier.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "spec_verification_passed"
    assert data["verification_state"] == "dry_run_in_memory_only"
    assert len(data["spec_hash"]) == 64
    assert data["target_table"] == "manual_release_health_digest_history"
    assert data["failed_checks"] == []
    assert data["missing_fields"] == []
    assert checks["required_fields_covered"]["status"] == "passed"
    assert checks["sensitive_fields_absent"]["status"] == "passed"
    assert checks["dangerous_sql_absent"]["status"] == "passed"
    assert checks["migration_not_allowed_now"]["status"] == "passed"
    assert data["summary"]["failed_count"] == 0
    assert data["summary"]["executes_sql"] is False
    assert data["summary"]["creates_table_now"] is False
    assert data["summary"]["writes_database_now"] is False
    assert data["summary"]["writes_migration_file_now"] is False
    assert data["summary"]["writes_history_row_now"] is False
    assert data["decision"]["spec_verification_passed"] is True
    assert data["decision"]["can_execute_sql_now"] is False
    assert data["decision"]["can_create_table_now"] is False
    assert data["decision"]["can_write_history_row_now"] is False
    assert data["decision"]["migration_allowed_now"] is False
    assert data["decision"]["execution_allowed_now"] is False
    assert data["safety_summary"]["dry_run_verifier_only"] is True
    assert data["safety_summary"]["persists_manual_release_health_digest_history"] is False
    assert data["safety_summary"]["executes_sql"] is False
    assert data["safety_summary"]["writes_database_now"] is False
    assert data["safety_summary"]["writes_file"] is False
    assert "execute_sql" in data["forbidden_actions"]
    assert "run_history_migration" in data["forbidden_actions"]


def test_audit_ledger_migration_manual_release_health_digest_history_migration_spec_verifier_blocks_unsafe_text(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
    service.approve_audit_ledger_migration_spec(
        approved_by="history-spec-reviewer",
        note="unsafe manual release health digest history migration spec fixture",
    )
    evidence = _complete_manual_release_evidence(service)

    data = service.verify_audit_ledger_migration_manual_release_health_digest_history_migration_spec(
        spec_text="DROP TABLE manual_release_health_digest_history; SELECT raw_manual_release_evidence, broker_credentials, orders;",
        baseline_evidence=evidence,
        candidate_evidence=evidence,
        limit=5,
    )

    assert data["status"] == "spec_verification_failed"
    assert "drop" in data["dangerous_matches"]
    assert "raw_manual_release_evidence" in data["sensitive_matches"]
    assert "broker_credentials" in data["sensitive_matches"]
    assert "orders" in data["sensitive_matches"]
    assert data["decision"]["spec_verification_passed"] is False
    assert data["decision"]["can_execute_sql_now"] is False
    assert data["summary"]["executes_sql"] is False
    assert data["safety_summary"]["executes_sql"] is False
    assert data["migration_allowed_now"] is False


def test_audit_ledger_migration_manual_release_health_digest_history_migration_spec_approval_is_metadata_only(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
        conn.execute(
            "DELETE FROM events WHERE event_type = 'trade_manual_release_health_digest_history_migration_spec_approval'"
        )
    service.approve_audit_ledger_migration_spec(
        approved_by="history-spec-approver",
        note="manual release health digest history migration spec approval fixture",
    )
    evidence = _complete_manual_release_evidence(service)

    data = service.approve_audit_ledger_migration_manual_release_health_digest_history_migration_spec(
        approved_by="history-spec-approver",
        note="history migration spec reviewed by operator",
        baseline_evidence=evidence,
        candidate_evidence=evidence,
        limit=5,
    )
    approvals = service.list_audit_ledger_migration_manual_release_health_digest_history_migration_spec_approvals(
        limit=5
    )

    assert data["schema_version"] == "trade_execution_audit_ledger_migration_manual_release_health_digest_history_migration_spec_approval.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "approval_metadata_recorded"
    assert isinstance(data["event_id"], int)
    assert data["approved_by"] == "history-spec-approver"
    assert data["approval_effect"] == "existing_event_metadata_only"
    assert data["verification_status"] == "spec_verification_passed"
    assert data["verification_failed_count"] == 0
    assert data["target_table"] == "manual_release_health_digest_history"
    assert data["migration_allowed_now"] is False
    assert data["safety_summary"]["writes_existing_event_now"] is True
    assert data["safety_summary"]["persists_manual_release_health_digest_history"] is False
    assert data["safety_summary"]["writes_history_row_now"] is False
    assert data["safety_summary"]["creates_table_now"] is False
    assert data["safety_summary"]["runs_migration_now"] is False
    assert data["safety_summary"]["executes_sql"] is False
    assert data["safety_summary"]["writes_migration_file_now"] is False
    assert data["allowed_output"] == "review_only_manual_release_health_digest_history_migration_spec_approval_metadata"
    assert "execute_sql" in data["forbidden_actions"]
    assert "write_history_row" in data["forbidden_actions"]
    assert approvals[0]["event_id"] == data["event_id"]
    assert approvals[0]["event_type"] == "trade_manual_release_health_digest_history_migration_spec_approval"


def test_audit_ledger_migration_manual_release_health_digest_history_migration_spec_approval_blocks_failed_spec(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
        conn.execute(
            "DELETE FROM events WHERE event_type = 'trade_manual_release_health_digest_history_migration_spec_approval'"
        )
    service.approve_audit_ledger_migration_spec(
        approved_by="history-spec-approver",
        note="unsafe history migration spec approval fixture",
    )
    evidence = _complete_manual_release_evidence(service)

    data = service.approve_audit_ledger_migration_manual_release_health_digest_history_migration_spec(
        spec_text="DROP TABLE manual_release_health_digest_history; SELECT raw_manual_release_evidence, broker_credentials, orders;",
        baseline_evidence=evidence,
        candidate_evidence=evidence,
        limit=5,
    )
    approvals = service.list_audit_ledger_migration_manual_release_health_digest_history_migration_spec_approvals(
        limit=5
    )

    assert data["status"] == "approval_blocked"
    assert data["event_id"] is None
    assert data["verification"]["status"] == "spec_verification_failed"
    assert data["verification_failed_count"] > 0
    assert data["safety_summary"]["writes_existing_event_now"] is False
    assert data["safety_summary"]["writes_history_row_now"] is False
    assert data["safety_summary"]["executes_sql"] is False
    assert approvals == []


def test_audit_ledger_migration_manual_release_health_digest_history_release_readiness_requires_approval(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
        conn.execute(
            "DELETE FROM events WHERE event_type = 'trade_manual_release_health_digest_history_migration_spec_approval'"
        )
    service.approve_audit_ledger_migration_spec(
        approved_by="history-readiness-reviewer",
        note="base migration approval fixture",
    )

    data = service.audit_ledger_migration_manual_release_health_digest_history_release_readiness(
        limit=5,
    )
    gates = {gate["name"]: gate for gate in data["gates"]}

    assert data["schema_version"] == "trade_execution_audit_ledger_migration_manual_release_health_digest_history_release_readiness.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "release_review_required"
    assert data["decision"]["go_no_go"] == "no_go"
    assert data["decision"]["migration_allowed_now"] is False
    assert data["decision"]["execution_allowed_now"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["evidence"]["proposal_status"] == "history_retention_proposal_ready"
    assert data["evidence"]["checklist_status"] == "history_migration_readiness_review_ready"
    assert data["evidence"]["verification_status"] == "spec_verification_passed"
    assert data["evidence"]["approval_count"] == 0
    assert gates["history_retention_proposal_ready"]["status"] == "passed"
    assert gates["migration_checklist_ready"]["status"] == "passed"
    assert gates["migration_spec_verified"]["status"] == "passed"
    assert gates["operator_approval_metadata_recorded"]["status"] == "review_required"
    assert gates["latest_approval_matches_current_spec"]["status"] == "review_required"
    assert data["safety_summary"]["persists_manual_release_health_digest_history"] is False
    assert data["safety_summary"]["writes_history_row_now"] is False
    assert data["safety_summary"]["executes_sql"] is False
    assert data["allowed_output"] == "review_only_manual_release_health_digest_history_release_readiness"
    assert "write_history_row" in data["forbidden_actions"]
    assert data["live_trading_enabled"] is False


def test_audit_ledger_migration_manual_release_health_digest_history_release_readiness_summarizes_approval(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
        conn.execute(
            "DELETE FROM events WHERE event_type = 'trade_manual_release_health_digest_history_migration_spec_approval'"
        )
    service.approve_audit_ledger_migration_spec(
        approved_by="history-readiness-reviewer",
        note="base migration approval fixture",
    )
    evidence = _complete_manual_release_evidence(service)
    approval = service.approve_audit_ledger_migration_manual_release_health_digest_history_migration_spec(
        approved_by="history-readiness-reviewer",
        note="ready for manual release readiness",
        baseline_evidence=evidence,
        candidate_evidence=evidence,
        limit=5,
    )

    data = service.audit_ledger_migration_manual_release_health_digest_history_release_readiness(limit=5)

    assert data["status"] == "release_evidence_ready"
    assert data["decision"]["go_no_go"] == "go_for_manual_release_review"
    assert data["decision"]["migration_allowed_now"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["evidence"]["approval_count"] == 1
    assert data["evidence"]["latest_approval_event_id"] == approval["event_id"]
    assert data["evidence"]["spec_hash"] == approval["spec_hash"]
    assert data["evidence"]["approved_spec_hash"] == approval["spec_hash"]
    assert all(gate["status"] == "passed" for gate in data["gates"])
    assert data["blocked_gates"] == []
    assert data["review_required_gates"] == []
    assert "explicit_operator_release_approval" in data["required_before_actual_migration"]
    assert data["safety_summary"]["creates_table_now"] is False
    assert data["safety_summary"]["runs_migration_now"] is False
    assert data["safety_summary"]["writes_history_row_now"] is False
    assert data["safety_summary"]["writes_migration_file_now"] is False
    assert data["safety_summary"]["places_real_trade"] is False


def test_audit_ledger_migration_manual_release_health_digest_history_approval_review_requires_approval(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
        conn.execute(
            "DELETE FROM events WHERE event_type = 'trade_manual_release_health_digest_history_migration_spec_approval'"
        )
    service.approve_audit_ledger_migration_spec(
        approved_by="history-freshness-reviewer",
        note="base migration approval fixture",
    )

    data = service.audit_ledger_migration_manual_release_health_digest_history_approval_review(
        limit=5,
        max_age_days=7,
    )
    gates = {gate["name"]: gate for gate in data["gates"]}

    assert data["schema_version"] == "trade_execution_audit_ledger_migration_manual_release_health_digest_history_approval_review.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "approval_review_required"
    assert data["review_policy"]["max_age_days"] == 7
    assert data["latest_approval"]["event_id"] is None
    assert data["latest_approval"]["is_expired"] is False
    assert data["latest_approval"]["matches_current_spec"] is False
    assert data["release_readiness"]["status"] == "release_review_required"
    assert gates["approval_recorded"]["status"] == "review_required"
    assert gates["approval_within_validity_window"]["status"] == "review_required"
    assert gates["approval_matches_current_spec"]["status"] == "review_required"
    assert data["decision"]["next_required_action"] == "record_health_digest_history_migration_spec_approval_metadata"
    assert data["decision"]["approval_can_be_reused_for_manual_release_review"] is False
    assert data["decision"]["migration_allowed_now"] is False
    assert data["decision"]["execution_allowed_now"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["safety_summary"]["writes_history_row_now"] is False
    assert data["safety_summary"]["executes_sql"] is False
    assert data["allowed_output"] == "review_only_manual_release_health_digest_history_approval_review"
    assert "reuse_expired_approval_as_current" in data["forbidden_actions"]
    assert data["live_trading_enabled"] is False


def test_audit_ledger_migration_manual_release_health_digest_history_approval_review_accepts_current_approval(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
        conn.execute(
            "DELETE FROM events WHERE event_type = 'trade_manual_release_health_digest_history_migration_spec_approval'"
        )
    service.approve_audit_ledger_migration_spec(
        approved_by="history-freshness-reviewer",
        note="base migration approval fixture",
    )
    evidence = _complete_manual_release_evidence(service)
    approval = service.approve_audit_ledger_migration_manual_release_health_digest_history_migration_spec(
        approved_by="history-freshness-reviewer",
        note="fresh health digest history approval metadata",
        baseline_evidence=evidence,
        candidate_evidence=evidence,
        limit=5,
    )

    data = service.audit_ledger_migration_manual_release_health_digest_history_approval_review(
        limit=5,
        max_age_days=7,
    )

    assert data["status"] == "approval_current"
    assert data["latest_approval"]["event_id"] == approval["event_id"]
    assert data["latest_approval"]["is_expired"] is False
    assert data["latest_approval"]["matches_current_spec"] is True
    assert data["current_spec"]["spec_hash"] == approval["spec_hash"]
    assert data["release_readiness"]["status"] == "release_evidence_ready"
    assert data["decision"]["next_required_action"] == "none"
    assert data["decision"]["approval_can_be_reused_for_manual_release_review"] is True
    assert all(gate["status"] == "passed" for gate in data["gates"])
    assert data["blocked_gates"] == []
    assert data["review_required_gates"] == []
    assert data["safety_summary"]["runs_migration_now"] is False
    assert data["safety_summary"]["writes_history_row_now"] is False
    assert data["safety_summary"]["places_real_trade"] is False


def test_audit_ledger_migration_manual_release_health_digest_history_approval_review_requires_rotation_for_expired_metadata(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
        conn.execute(
            "DELETE FROM events WHERE event_type = 'trade_manual_release_health_digest_history_migration_spec_approval'"
        )
    service.approve_audit_ledger_migration_spec(
        approved_by="history-stale-reviewer",
        note="base migration approval fixture",
    )
    evidence = _complete_manual_release_evidence(service)
    approval = service.approve_audit_ledger_migration_manual_release_health_digest_history_migration_spec(
        approved_by="history-stale-reviewer",
        note="stale health digest history approval metadata",
        baseline_evidence=evidence,
        candidate_evidence=evidence,
        limit=5,
    )
    old_approved_at = (datetime.now() - timedelta(days=10)).isoformat(timespec="seconds")
    with service.store.connect() as conn:
        row = conn.execute(
            "SELECT payload_json FROM events WHERE id = ?",
            (approval["event_id"],),
        ).fetchone()
        payload = json.loads(row["payload_json"])
        payload["approved_at"] = old_approved_at
        conn.execute(
            "UPDATE events SET payload_json = ? WHERE id = ?",
            (json.dumps(payload, ensure_ascii=False, sort_keys=True), approval["event_id"]),
        )

    data = service.audit_ledger_migration_manual_release_health_digest_history_approval_review(
        limit=5,
        max_age_days=7,
    )
    gates = {gate["name"]: gate for gate in data["gates"]}

    assert data["status"] == "approval_rotation_required"
    assert data["latest_approval"]["event_id"] == approval["event_id"]
    assert data["latest_approval"]["is_expired"] is True
    assert data["latest_approval"]["approval_age_days"] is not None
    assert data["latest_approval"]["approval_age_days"] > 7
    assert data["latest_approval"]["matches_current_spec"] is True
    assert gates["approval_within_validity_window"]["status"] == "review_required"
    assert data["decision"]["next_required_action"] == "refresh_health_digest_history_migration_spec_approval_metadata"
    assert data["decision"]["approval_can_be_reused_for_manual_release_review"] is False
    assert data["safety_summary"]["executes_sql"] is False
    assert data["safety_summary"]["writes_migration_file_now"] is False
    assert data["live_trading_enabled"] is False


def test_audit_ledger_migration_manual_release_health_digest_history_release_package_requires_complete_evidence(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
        conn.execute(
            "DELETE FROM events WHERE event_type = 'trade_manual_release_health_digest_history_migration_spec_approval'"
        )
    service.approve_audit_ledger_migration_spec(
        approved_by="history-package-reviewer",
        note="base migration approval fixture",
    )

    data = service.audit_ledger_migration_manual_release_health_digest_history_release_package(
        limit=5,
        max_age_days=7,
    )
    gates = {gate["name"]: gate for gate in data["gates"]}
    items = {item["name"]: item for item in data["manifest"]["items"]}

    assert data["schema_version"] == "trade_execution_audit_ledger_migration_manual_release_health_digest_history_release_package.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "release_package_review_required"
    assert len(data["package_id"]) == 64
    assert data["decision"]["go_no_go"] == "no_go"
    assert data["decision"]["migration_allowed_now"] is False
    assert data["decision"]["execution_allowed_now"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["decision"]["next_required_action"] == "complete_missing_release_evidence"
    assert gates["history_retention_proposal_ready"]["status"] == "passed"
    assert gates["history_migration_checklist_ready"]["status"] == "passed"
    assert gates["history_migration_spec_verified"]["status"] == "passed"
    assert gates["history_approval_current"]["status"] == "review_required"
    assert items["P18_health_digest_history_spec_approval_metadata"]["status"] == "missing"
    assert items["P18_health_digest_history_spec_approval_metadata"]["safety_passed"] is False
    assert items["P20_health_digest_history_approval_freshness"]["safety_passed"] is False
    assert "reviewed_sqlite_migration_file" in data["manifest"]["required_manual_artifacts_before_execution"]
    assert data["manifest"]["writes_file"] is False
    assert data["manifest"]["download_created"] is False
    assert data["safety_summary"]["executes_sql"] is False
    assert data["safety_summary"]["runs_migration_now"] is False
    assert data["safety_summary"]["creates_table_now"] is False
    assert data["safety_summary"]["writes_database_now"] is False
    assert data["safety_summary"]["writes_history_row_now"] is False
    assert data["allowed_output"] == "review_only_manual_release_health_digest_history_release_package"
    assert "write_release_package_file" in data["forbidden_actions"]
    assert data["review_only"] is True
    assert data["simulation_only"] is True
    assert data["live_trading_enabled"] is False


def test_audit_ledger_migration_manual_release_health_digest_history_release_package_ready_after_current_approval(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
        conn.execute(
            "DELETE FROM events WHERE event_type = 'trade_manual_release_health_digest_history_migration_spec_approval'"
        )
    service.approve_audit_ledger_migration_spec(
        approved_by="history-package-reviewer",
        note="base migration approval fixture",
    )
    evidence = _complete_manual_release_evidence(service)
    approval = service.approve_audit_ledger_migration_manual_release_health_digest_history_migration_spec(
        approved_by="history-package-reviewer",
        note="ready for health digest history release package",
        baseline_evidence=evidence,
        candidate_evidence=evidence,
        limit=5,
    )

    data = service.audit_ledger_migration_manual_release_health_digest_history_release_package(
        limit=5,
        max_age_days=7,
    )
    gates = {gate["name"]: gate for gate in data["gates"]}
    items = {item["name"]: item for item in data["manifest"]["items"]}

    assert data["status"] == "release_package_ready_for_manual_review"
    assert data["stage"] == "V5.5-P24"
    assert data["evidence"]["latest_approval_event_id"] == approval["event_id"]
    assert data["evidence"]["approved_spec_hash"] == data["evidence"]["spec_hash"]
    assert data["evidence"]["approval_review_status"] == "approval_current"
    assert data["decision"]["go_no_go"] == "ready_for_manual_release_review"
    assert data["decision"]["migration_allowed_now"] is False
    assert data["decision"]["execution_allowed_now"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["decision"]["requires_human_release_approval"] is True
    assert all(item["safety_passed"] for item in data["manifest"]["items"])
    assert gates["history_approval_current"]["status"] == "passed"
    assert gates["history_release_readiness_ready"]["status"] == "passed"
    assert gates["no_history_migration_execution_enabled"]["status"] == "passed"
    assert items["P20_health_digest_history_approval_freshness"]["status"] == "approval_current"
    assert data["manifest"]["delivery"] == "api_response_only"
    assert data["safety_summary"]["writes_migration_file_now"] is False
    assert data["safety_summary"]["writes_history_row_now"] is False
    assert data["safety_summary"]["places_real_trade"] is False
    assert data["live_trading_enabled"] is False


def test_audit_ledger_migration_manual_release_health_digest_history_release_package_integrity_passes_with_pending_evidence(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
        conn.execute(
            "DELETE FROM events WHERE event_type = 'trade_manual_release_health_digest_history_migration_spec_approval'"
        )
    service.approve_audit_ledger_migration_spec(
        approved_by="history-integrity-reviewer",
        note="base migration approval fixture",
    )

    data = service.audit_ledger_migration_manual_release_health_digest_history_release_package_integrity_review(
        limit=5,
        max_age_days=7,
        repeat_checks=3,
    )
    checks = {check["name"]: check for check in data["checks"]}

    assert data["schema_version"] == "trade_execution_audit_ledger_migration_manual_release_health_digest_history_release_package_integrity_review.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "integrity_review_passed_release_evidence_pending"
    assert data["source_package_status"] == "release_package_review_required"
    assert data["source_package_id"] == data["recomputed_package_id"]
    assert data["repeat_checks"] == 3
    assert len(set(data["repeated_package_ids"])) == 1
    assert data["failed_check_count"] == 0
    assert checks["package_id_recomputable"]["status"] == "passed"
    assert checks["required_manifest_items_present"]["status"] == "passed"
    assert checks["api_response_only_delivery"]["status"] == "passed"
    assert data["manifest_summary"]["item_count"] == 6
    assert data["manifest_summary"]["writes_file"] is False
    assert data["manifest_summary"]["download_created"] is False
    assert data["decision"]["package_id_stable"] is True
    assert data["decision"]["manifest_integrity_passed"] is True
    assert data["decision"]["release_package_ready"] is False
    assert data["decision"]["go_no_go"] == "no_go"
    assert data["decision"]["next_required_action"] == "complete_missing_release_evidence"
    assert data["decision"]["migration_allowed_now"] is False
    assert data["decision"]["execution_allowed_now"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["safety_summary"]["writes_history_row_now"] is False
    assert data["safety_summary"]["writes_file"] is False
    assert data["safety_summary"]["mutates_source_package"] is False
    assert "approve_release_from_integrity_review" in data["forbidden_actions"]
    assert data["live_trading_enabled"] is False


def test_audit_ledger_migration_manual_release_health_digest_history_release_package_integrity_passes_after_current_approval(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
        conn.execute(
            "DELETE FROM events WHERE event_type = 'trade_manual_release_health_digest_history_migration_spec_approval'"
        )
    service.approve_audit_ledger_migration_spec(
        approved_by="history-integrity-reviewer",
        note="base migration approval fixture",
    )
    evidence = _complete_manual_release_evidence(service)
    service.approve_audit_ledger_migration_manual_release_health_digest_history_migration_spec(
        approved_by="history-integrity-reviewer",
        note="ready for health digest history release package integrity",
        baseline_evidence=evidence,
        candidate_evidence=evidence,
        limit=5,
    )

    data = service.audit_ledger_migration_manual_release_health_digest_history_release_package_integrity_review(
        limit=5,
        max_age_days=7,
        repeat_checks=3,
    )

    assert data["status"] == "integrity_review_passed"
    assert data["source_package_status"] == "release_package_ready_for_manual_review"
    assert data["decision"]["release_package_ready"] is True
    assert data["decision"]["go_no_go"] == "ready_for_manual_release_review"
    assert data["decision"]["next_required_action"] == "manual_release_review"
    assert data["decision"]["migration_allowed_now"] is False
    assert data["decision"]["execution_allowed_now"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["failed_checks"] == []
    assert all(check["status"] == "passed" for check in data["checks"])
    assert data["manifest_summary"]["missing_items"] == []
    assert data["manifest_summary"]["missing_manual_artifacts"] == []
    assert data["safety_summary"]["executes_sql"] is False
    assert data["safety_summary"]["runs_migration_now"] is False
    assert data["safety_summary"]["writes_migration_file_now"] is False
    assert data["safety_summary"]["writes_history_row_now"] is False
    assert data["safety_summary"]["places_real_trade"] is False


def test_audit_ledger_migration_manual_release_health_digest_history_release_rehearsal_waits_for_release_evidence(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
        conn.execute(
            "DELETE FROM events WHERE event_type = 'trade_manual_release_health_digest_history_migration_spec_approval'"
        )
    service.approve_audit_ledger_migration_spec(
        approved_by="history-rehearsal-reviewer",
        note="base migration approval fixture",
    )

    data = service.audit_ledger_migration_manual_release_health_digest_history_release_rehearsal(
        limit=5,
        max_age_days=7,
        repeat_checks=3,
    )
    steps = {step["name"]: step for step in data["steps"]}

    assert data["schema_version"] == "trade_execution_audit_ledger_migration_manual_release_health_digest_history_release_rehearsal.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "manual_release_rehearsal_waiting_for_evidence"
    assert data["integrity_status"] == "integrity_review_passed_release_evidence_pending"
    assert data["source_package_status"] == "release_package_review_required"
    assert len(data["rehearsal_id"]) == 64
    assert steps["confirm_health_digest_history_package_identity"]["status"] == "ready_for_manual_review"
    assert steps["review_health_digest_history_integrity_checks"]["status"] == "ready_for_manual_review"
    assert steps["confirm_health_digest_history_release_evidence_ready"]["status"] == "pending_evidence"
    assert data["pending_steps"] != []
    assert data["failed_steps"] == []
    assert data["operator_rehearsal_policy"]["api_can_record_operator_review"] is False
    assert data["operator_rehearsal_policy"]["api_can_execute_migration"] is False
    assert "signed_manual_release_health_digest_history_review" in data["required_offline_artifacts"]
    assert data["decision"]["rehearsal_ready_for_operator"] is False
    assert data["decision"]["go_no_go"] == "no_go"
    assert data["decision"]["manual_review_recorded_now"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["decision"]["migration_allowed_now"] is False
    assert data["decision"]["execution_allowed_now"] is False
    assert data["safety_summary"]["records_manual_review_now"] is False
    assert data["safety_summary"]["writes_history_row_now"] is False
    assert data["safety_summary"]["executes_sql"] is False
    assert "record_manual_release_review_by_api" in data["forbidden_actions"]
    assert data["live_trading_enabled"] is False


def test_audit_ledger_migration_manual_release_health_digest_history_release_rehearsal_ready_after_current_approval(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
        conn.execute(
            "DELETE FROM events WHERE event_type = 'trade_manual_release_health_digest_history_migration_spec_approval'"
        )
    service.approve_audit_ledger_migration_spec(
        approved_by="history-rehearsal-reviewer",
        note="base migration approval fixture",
    )
    evidence = _complete_manual_release_evidence(service)
    service.approve_audit_ledger_migration_manual_release_health_digest_history_migration_spec(
        approved_by="history-rehearsal-reviewer",
        note="ready for health digest history release rehearsal",
        baseline_evidence=evidence,
        candidate_evidence=evidence,
        limit=5,
    )

    data = service.audit_ledger_migration_manual_release_health_digest_history_release_rehearsal(
        limit=5,
        max_age_days=7,
        repeat_checks=3,
    )

    assert data["status"] == "manual_release_rehearsal_ready"
    assert data["integrity_status"] == "integrity_review_passed"
    assert data["source_package_status"] == "release_package_ready_for_manual_review"
    assert all(step["status"] == "ready_for_manual_review" for step in data["steps"])
    assert data["pending_steps"] == []
    assert data["failed_steps"] == []
    assert data["decision"]["rehearsal_ready_for_operator"] is True
    assert data["decision"]["go_no_go"] == "ready_for_offline_manual_review"
    assert data["decision"]["next_required_action"] == "perform_offline_manual_release_review"
    assert data["decision"]["manual_review_recorded_now"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["decision"]["migration_allowed_now"] is False
    assert data["decision"]["execution_allowed_now"] is False
    assert data["operator_rehearsal_policy"]["offline_human_review_required"] is True
    assert data["safety_summary"]["marks_rehearsal_complete_now"] is False
    assert data["safety_summary"]["writes_migration_file_now"] is False
    assert data["safety_summary"]["writes_history_row_now"] is False
    assert data["safety_summary"]["places_real_trade"] is False


def test_audit_ledger_migration_manual_release_health_digest_history_release_evidence_verifier_requires_artifacts(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
        conn.execute(
            "DELETE FROM events WHERE event_type = 'trade_manual_release_health_digest_history_migration_spec_approval'"
        )

    data = service.verify_audit_ledger_migration_manual_release_health_digest_history_release_evidence(
        evidence={},
        limit=5,
        max_age_days=7,
        repeat_checks=2,
    )
    checks = {check["name"]: check for check in data["checks"]}

    assert data["schema_version"] == "trade_execution_audit_ledger_migration_manual_release_health_digest_history_release_evidence_verifier.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "manual_release_health_digest_history_evidence_missing"
    assert data["rehearsal_status"] == "manual_release_rehearsal_waiting_for_evidence"
    assert data["missing_artifacts"] == data["required_artifacts"]
    assert checks["health_digest_history_rehearsal_ready"]["status"] == "failed"
    assert checks["required_artifacts_present_once"]["status"] == "failed"
    assert checks["payload_safety_flags"]["status"] == "failed"
    assert data["decision"]["evidence_complete"] is False
    assert data["decision"]["go_no_go"] == "no_go"
    assert data["decision"]["manual_review_recorded_now"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["decision"]["migration_allowed_now"] is False
    assert data["decision"]["execution_allowed_now"] is False
    assert data["safety_summary"]["persists_manual_release_health_digest_history_evidence"] is False
    assert data["safety_summary"]["writes_database_now"] is False
    assert data["safety_summary"]["writes_history_row_now"] is False
    assert "persist_manual_release_health_digest_history_evidence" in data["forbidden_actions"]
    assert "approve_release_from_health_digest_history_evidence_verifier" in data["forbidden_actions"]
    assert data["live_trading_enabled"] is False


def test_audit_ledger_migration_manual_release_health_digest_history_release_evidence_verifier_passes_complete_fixture(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
        conn.execute(
            "DELETE FROM events WHERE event_type = 'trade_manual_release_health_digest_history_migration_spec_approval'"
        )
    service.approve_audit_ledger_migration_spec(
        approved_by="history-evidence-reviewer",
        note="base migration approval fixture",
    )
    evidence = _complete_manual_release_evidence(service)
    service.approve_audit_ledger_migration_manual_release_health_digest_history_migration_spec(
        approved_by="history-evidence-reviewer",
        note="ready for health digest history evidence verification",
        baseline_evidence=evidence,
        candidate_evidence=evidence,
        limit=5,
    )
    payload = _complete_health_digest_history_release_evidence(service)

    data = service.verify_audit_ledger_migration_manual_release_health_digest_history_release_evidence(
        evidence=payload,
        limit=5,
        max_age_days=7,
        repeat_checks=2,
    )

    assert data["status"] == "manual_release_health_digest_history_evidence_verification_passed"
    assert data["rehearsal_status"] == "manual_release_rehearsal_ready"
    assert data["missing_artifacts"] == []
    assert data["duplicate_artifacts"] == []
    assert data["failed_checks"] == []
    assert data["failed_check_count"] == 0
    assert all(check["status"] == "passed" for check in data["checks"])
    assert data["decision"]["evidence_complete"] is True
    assert data["decision"]["go_no_go"] == "evidence_complete_for_offline_review"
    assert data["decision"]["next_required_action"] == "offline_health_digest_history_release_review_can_continue"
    assert data["decision"]["manual_review_recorded_now"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["decision"]["migration_allowed_now"] is False
    assert data["decision"]["execution_allowed_now"] is False
    assert data["safety_summary"]["persists_manual_release_health_digest_history_evidence"] is False
    assert data["safety_summary"]["writes_file"] is False
    assert data["safety_summary"]["writes_history_row_now"] is False
    assert data["safety_summary"]["executes_sql"] is False
    assert data["safety_summary"]["places_real_trade"] is False


def test_audit_ledger_migration_manual_release_health_digest_history_release_evidence_verifier_blocks_forbidden_fields(test_db):
    service = TradeExecutionGatewayService()
    with service.store.connect() as conn:
        conn.execute("DELETE FROM events WHERE event_type = 'trade_audit_ledger_migration_spec_approval'")
        conn.execute(
            "DELETE FROM events WHERE event_type = 'trade_manual_release_health_digest_history_migration_spec_approval'"
        )
    service.approve_audit_ledger_migration_spec(
        approved_by="history-evidence-reviewer",
        note="base migration approval fixture",
    )
    evidence = _complete_manual_release_evidence(service)
    service.approve_audit_ledger_migration_manual_release_health_digest_history_migration_spec(
        approved_by="history-evidence-reviewer",
        note="ready for health digest history evidence verification",
        baseline_evidence=evidence,
        candidate_evidence=evidence,
        limit=5,
    )
    payload = _complete_health_digest_history_release_evidence(service)
    payload["artifacts"][0]["sql_text"] = "CREATE TABLE manual_release_health_digest_history (...);"
    payload["artifacts"][0]["database_path"] = "trading_local.sqlite3"

    data = service.verify_audit_ledger_migration_manual_release_health_digest_history_release_evidence(
        evidence=payload,
        limit=5,
        max_age_days=7,
        repeat_checks=2,
    )
    checks = {check["name"]: check for check in data["checks"]}

    assert data["status"] == "manual_release_health_digest_history_evidence_verification_failed"
    assert checks["no_forbidden_evidence_fields"]["status"] == "failed"
    assert checks["no_forbidden_evidence_fields"]["details"]["forbidden_field_hits"] == ["database_path", "sql_text"]
    assert data["decision"]["evidence_complete"] is False
    assert data["decision"]["release_approved_now"] is False
    assert data["decision"]["execution_allowed_now"] is False
    assert data["safety_summary"]["executes_sql"] is False
    assert data["safety_summary"]["writes_database_now"] is False
    assert data["safety_summary"]["writes_history_row_now"] is False


def test_operator_acceptance_checklist_is_review_only_and_cannot_record_acceptance():
    data = TradeExecutionGatewayService().operator_acceptance_checklist()
    item_ids = {item["id"] for item in data["checklist_items"]}

    assert data["schema_version"] == "trade_execution_operator_acceptance_checklist.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "operator_acceptance_checklist_review_ready"
    assert data["checklist_state"] == "defined_for_manual_review_only"
    assert "health_live_trading_disabled" in item_ids
    assert "forbidden_surfaces_absent" in item_ids
    assert all(item["blocking_if_missing"] is True for item in data["checklist_items"])
    assert all(item["api_can_mark_complete"] is False for item in data["checklist_items"])
    assert data["acceptance_policy"]["api_can_record_acceptance"] is False
    assert data["acceptance_policy"]["api_can_enable_gateway"] is False
    assert data["decision"]["operator_acceptance_recorded_now"] is False
    assert data["decision"]["acceptance_allows_enablement_now"] is False
    assert data["decision"]["ready_for_live_enablement"] is False
    assert data["decision"]["gateway_can_execute"] is False
    assert data["safety_summary"]["records_acceptance_now"] is False
    assert data["safety_summary"]["enables_gateway_now"] is False
    assert data["safety_summary"]["writes_database_now"] is False
    assert data["safety_summary"]["places_real_trade"] is False


def test_disabled_release_gate_is_review_only_and_default_disabled():
    data = TradeExecutionGatewayService().disabled_release_gate()

    assert data["schema_version"] == "trade_execution_disabled_release_gate.v1"
    assert data["stage"] == "V5.5-P24"
    assert data["status"] == "disabled_release_gate_review_ready"
    assert data["default_state"] == "disabled"
    assert data["release_gate_state"] == "review_only_metadata"
    assert "no_api_enablement_surface" in data["release_blockers"]
    assert "separate_live_integration_plan_required" in data["release_blockers"]
    assert data["gate_evidence"]["blocked_gate_count"] == 0
    assert data["gate_evidence"]["live_trading_enabled"] is False
    assert data["decision"]["release_gate_allows_enablement_now"] is False
    assert data["decision"]["ready_for_live_enablement"] is False
    assert data["decision"]["gateway_can_execute"] is False
    assert data["decision"]["api_can_enable_gateway"] is False
    assert data["decision"]["api_can_record_release_approval"] is False
    assert data["safety_summary"]["default_disabled"] is True
    assert data["safety_summary"]["enables_gateway_now"] is False
    assert data["safety_summary"]["writes_database_now"] is False
    assert data["safety_summary"]["connects_broker"] is False
    assert data["safety_summary"]["places_real_trade"] is False


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
    risk_contract_resp = client.get("/api/trade-execution-gateway/risk-gate-contract")
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
        json={"spec_text": None, "approved_by": "api-smoke", "note": "api smoke approval metadata"},
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
                "artifact_hash": f"api-artifact-{index:02d}-0123456789abcdef",
                "reviewed_by": "api-smoke-offline-operator",
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
            "approved_by": "api-smoke",
            "note": "api smoke history migration spec approval metadata",
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
    migration_release_health_digest_history_release_package_resp = client.get(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-release-package?limit=5&max_age_days=7&repeat_checks=2"
    )
    migration_release_health_digest_history_package_integrity_resp = client.get(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-release-package/integrity-review?limit=5&max_age_days=7&repeat_checks=2"
    )
    migration_release_health_digest_history_release_rehearsal_resp = client.get(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-release-review/rehearsal?limit=5&max_age_days=7&repeat_checks=2"
    )
    history_rehearsal_json = migration_release_health_digest_history_release_rehearsal_resp.json()
    history_evidence_payload = {
        "source_package_id": history_rehearsal_json["source_package_id"],
        "rehearsal_id": history_rehearsal_json["rehearsal_id"],
        "artifacts": [
            {
                "name": name,
                "present": True,
                "artifact_hash": f"api-history-artifact-{index:02d}-0123456789abcdef",
                "reviewed_by": "api-smoke-offline-history-operator",
                "reviewed_at": "2026-06-01T15:30:00",
            }
            for index, name in enumerate(history_rehearsal_json["required_offline_artifacts"], start=1)
        ],
        "review_only": True,
        "simulation_only": True,
        "live_trading_enabled": False,
    }
    migration_release_health_digest_history_evidence_resp = client.post(
        "/api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-release-evidence/verify?limit=5&max_age_days=7&repeat_checks=2",
        json={"evidence": history_evidence_payload},
    )
    health_resp = client.get("/health")

    assert caps_resp.status_code == 200
    assert gates_resp.status_code == 200
    assert contract_resp.status_code == 200
    assert audit_schema_resp.status_code == 200
    assert risk_contract_resp.status_code == 200
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
    assert migration_release_health_digest_history_release_package_resp.status_code == 200
    assert migration_release_health_digest_history_package_integrity_resp.status_code == 200
    assert migration_release_health_digest_history_release_rehearsal_resp.status_code == 200
    assert migration_release_health_digest_history_evidence_resp.status_code == 200
    assert health_resp.status_code == 200
    assert caps_resp.json()["status"] == "review_only_ready"
    assert caps_resp.json()["execution_enabled"] is False
    assert caps_resp.json()["broker_adapter_enabled"] is False
    assert gates_resp.json()["decision"]["gateway_can_execute"] is False
    assert gates_resp.json()["decision"]["manual_confirmation_contract_ready"] is True
    assert gates_resp.json()["decision"]["risk_contract_ready"] is True
    assert gates_resp.json()["decision"]["rollback_runbook_ready"] is True
    assert gates_resp.json()["decision"]["disabled_release_gate_ready"] is True
    assert gates_resp.json()["decision"]["final_readiness_report_ready"] is True
    assert gates_resp.json()["decision"]["broker_adapter_threat_model_ready"] is True
    assert gates_resp.json()["decision"]["broker_adapter_interface_draft_ready"] is True
    assert gates_resp.json()["decision"]["broker_adapter_contract_verification_ready"] is True
    assert gates_resp.json()["decision"]["order_lifecycle_failure_fixtures_ready"] is True
    assert gates_resp.json()["decision"]["order_failure_runbook_mapping_ready"] is True
    assert gates_resp.json()["decision"]["disabled_audit_ledger_storage_plan_ready"] is True
    assert gates_resp.json()["decision"]["ready_for_live_enablement"] is False
    assert contract_resp.json()["decision"]["contract_allows_execution_now"] is False
    assert audit_schema_resp.json()["writes_database_now"] is False
    assert audit_schema_resp.json()["decision"]["migration_allowed_now"] is False
    assert risk_contract_resp.json()["decision"]["contract_allows_execution_now"] is False
    assert risk_contract_resp.json()["integration_notes"]["ai_override_allowed"] is False
    assert rollback_resp.json()["decision"]["runbook_allows_execution_now"] is False
    assert pre_live_resp.json()["decision"]["gateway_can_execute"] is False
    assert pre_live_resp.json()["decision"]["ready_for_live_enablement"] is False
    assert checklist_resp.json()["decision"]["acceptance_allows_enablement_now"] is False
    assert release_gate_resp.json()["decision"]["release_gate_allows_enablement_now"] is False
    assert release_gate_resp.json()["default_state"] == "disabled"
    assert final_report_resp.json()["decision"]["v5_review_only_baseline_complete"] is True
    assert final_report_resp.json()["decision"]["gateway_can_execute"] is False
    assert final_report_resp.json()["decision"]["ready_for_live_enablement"] is False
    assert threat_model_resp.json()["decision"]["broker_adapter_allowed_now"] is False
    assert threat_model_resp.json()["decision"]["order_execution_allowed_now"] is False
    assert interface_draft_resp.json()["decision"]["interface_implemented_now"] is False
    assert interface_draft_resp.json()["decision"]["adapter_can_execute_now"] is False
    assert contract_verification_resp.json()["decision"]["fixture_contract_tests_passed"] is True
    assert contract_verification_resp.json()["decision"]["adapter_can_execute_now"] is False
    assert contract_verification_resp.json()["summary"]["network_calls"] is False
    assert order_failure_resp.json()["status"] == "order_failure_fixtures_ready"
    assert order_failure_resp.json()["decision"]["can_submit_order_now"] is False
    assert order_failure_resp.json()["summary"]["places_order"] is False
    assert runbook_mapping_resp.json()["status"] == "order_failure_runbook_mapping_ready"
    assert runbook_mapping_resp.json()["summary"]["writes_database_now"] is False
    assert runbook_mapping_resp.json()["decision"]["can_execute_runbook_now"] is False
    assert storage_plan_resp.json()["status"] == "disabled_audit_ledger_storage_plan_ready"
    assert storage_plan_resp.json()["summary"]["writes_database_now"] is False
    assert storage_plan_resp.json()["summary"]["runs_migration_now"] is False
    assert storage_plan_resp.json()["decision"]["can_create_table_now"] is False
    assert migration_spec_resp.json()["status"] == "spec_verification_passed"
    assert migration_spec_resp.json()["summary"]["executes_sql"] is False
    assert migration_spec_resp.json()["summary"]["writes_migration_file_now"] is False
    assert migration_spec_resp.json()["decision"]["can_execute_sql_now"] is False
    assert migration_spec_resp.json()["decision"]["can_create_table_now"] is False
    assert migration_spec_resp.json()["decision"]["can_write_audit_row_now"] is False
    assert gates_resp.json()["decision"]["audit_ledger_migration_spec_dry_run_ready"] is True
    assert gates_resp.json()["decision"]["audit_ledger_migration_release_package_integrity_review_ready"] is True
    assert gates_resp.json()["decision"]["audit_ledger_migration_manual_release_rehearsal_ready"] is True
    assert gates_resp.json()["decision"]["audit_ledger_migration_manual_release_evidence_verifier_ready"] is True
    assert gates_resp.json()["decision"]["audit_ledger_migration_manual_release_evidence_comparison_ready"] is True
    assert gates_resp.json()["decision"]["audit_ledger_migration_manual_release_health_digest_ready"] is True
    assert gates_resp.json()["decision"]["audit_ledger_migration_manual_release_health_digest_history_retention_proposal_ready"] is True
    assert gates_resp.json()["decision"]["audit_ledger_migration_manual_release_health_digest_history_migration_readiness_checklist_ready"] is True
    assert gates_resp.json()["decision"]["audit_ledger_migration_manual_release_health_digest_history_migration_spec_verifier_ready"] is True
    assert gates_resp.json()["decision"]["audit_ledger_migration_manual_release_health_digest_history_migration_spec_approval_metadata_ready"] is True
    assert gates_resp.json()["decision"]["audit_ledger_migration_manual_release_health_digest_history_release_readiness_ready"] is True
    assert gates_resp.json()["decision"]["audit_ledger_migration_manual_release_health_digest_history_approval_freshness_ready"] is True
    assert gates_resp.json()["decision"]["audit_ledger_migration_manual_release_health_digest_history_release_package_ready"] is True
    assert gates_resp.json()["decision"]["audit_ledger_migration_manual_release_health_digest_history_release_package_integrity_review_ready"] is True
    assert gates_resp.json()["decision"]["audit_ledger_migration_manual_release_health_digest_history_release_rehearsal_ready"] is True
    assert gates_resp.json()["decision"]["audit_ledger_migration_manual_release_health_digest_history_release_evidence_verifier_ready"] is True
    assert gates_resp.json()["decision"]["audit_ledger_migration_spec_approval_metadata_ready"] is True
    assert migration_approval_resp.json()["status"] == "approval_metadata_recorded"
    assert migration_approval_resp.json()["safety_summary"]["writes_existing_event_now"] is True
    assert migration_approval_resp.json()["safety_summary"]["writes_audit_ledger_row_now"] is False
    assert migration_approval_resp.json()["safety_summary"]["executes_sql"] is False
    assert migration_approval_resp.json()["migration_allowed_now"] is False
    assert migration_approvals_resp.json()[0]["event_id"] == migration_approval_resp.json()["event_id"]
    assert migration_release_readiness_resp.json()["status"] == "release_evidence_ready"
    assert migration_release_readiness_resp.json()["decision"]["go_no_go"] == "go_for_manual_release_review"
    assert migration_release_readiness_resp.json()["decision"]["migration_allowed_now"] is False
    assert migration_release_readiness_resp.json()["decision"]["release_approved_now"] is False
    assert migration_release_readiness_resp.json()["evidence"]["latest_approval_event_id"] == migration_approval_resp.json()["event_id"]
    assert migration_release_readiness_resp.json()["safety_summary"]["executes_sql"] is False
    assert migration_release_readiness_resp.json()["safety_summary"]["writes_audit_ledger_row_now"] is False
    assert migration_approval_review_resp.json()["status"] == "approval_current"
    assert migration_approval_review_resp.json()["latest_approval"]["event_id"] == migration_approval_resp.json()["event_id"]
    assert migration_approval_review_resp.json()["decision"]["approval_can_be_reused_for_manual_release_review"] is True
    assert migration_approval_review_resp.json()["decision"]["migration_allowed_now"] is False
    assert migration_approval_review_resp.json()["safety_summary"]["writes_audit_ledger_row_now"] is False
    assert migration_approval_review_resp.json()["safety_summary"]["executes_sql"] is False
    assert migration_release_package_resp.json()["status"] == "release_package_ready_for_manual_review"
    assert migration_release_package_resp.json()["decision"]["go_no_go"] == "ready_for_manual_release_review"
    assert migration_release_package_resp.json()["decision"]["execution_allowed_now"] is False
    assert migration_release_package_resp.json()["decision"]["release_approved_now"] is False
    assert migration_release_package_resp.json()["evidence"]["latest_approval_event_id"] == migration_approval_resp.json()["event_id"]
    assert migration_release_package_resp.json()["manifest"]["writes_file"] is False
    assert migration_release_package_resp.json()["manifest"]["download_created"] is False
    assert migration_release_package_resp.json()["safety_summary"]["writes_audit_ledger_row_now"] is False
    assert migration_release_package_resp.json()["safety_summary"]["writes_file"] is False
    assert migration_package_integrity_resp.json()["status"] == "integrity_review_passed"
    assert migration_package_integrity_resp.json()["source_package_id"] == migration_package_integrity_resp.json()["recomputed_package_id"]
    assert migration_package_integrity_resp.json()["decision"]["package_id_stable"] is True
    assert migration_package_integrity_resp.json()["decision"]["manifest_integrity_passed"] is True
    assert migration_package_integrity_resp.json()["decision"]["execution_allowed_now"] is False
    assert migration_package_integrity_resp.json()["decision"]["release_approved_now"] is False
    assert migration_package_integrity_resp.json()["safety_summary"]["writes_file"] is False
    assert migration_package_integrity_resp.json()["safety_summary"]["mutates_source_package"] is False
    assert migration_release_rehearsal_resp.json()["status"] == "manual_release_rehearsal_ready"
    assert migration_release_rehearsal_resp.json()["decision"]["go_no_go"] == "ready_for_offline_manual_review"
    assert migration_release_rehearsal_resp.json()["decision"]["manual_review_recorded_now"] is False
    assert migration_release_rehearsal_resp.json()["decision"]["release_approved_now"] is False
    assert migration_release_rehearsal_resp.json()["decision"]["execution_allowed_now"] is False
    assert migration_release_rehearsal_resp.json()["operator_rehearsal_policy"]["api_can_record_operator_review"] is False
    assert migration_release_rehearsal_resp.json()["safety_summary"]["records_manual_review_now"] is False
    assert migration_release_evidence_resp.json()["status"] == "manual_release_evidence_verification_passed"
    assert migration_release_evidence_resp.json()["decision"]["evidence_complete"] is True
    assert migration_release_evidence_resp.json()["decision"]["manual_review_recorded_now"] is False
    assert migration_release_evidence_resp.json()["decision"]["release_approved_now"] is False
    assert migration_release_evidence_resp.json()["decision"]["execution_allowed_now"] is False
    assert migration_release_evidence_resp.json()["safety_summary"]["persists_manual_release_evidence"] is False
    assert migration_release_evidence_resp.json()["safety_summary"]["writes_database_now"] is False
    assert migration_release_evidence_comparison_resp.json()["status"] == "manual_release_evidence_comparison_stable"
    assert migration_release_evidence_comparison_resp.json()["decision"]["evidence_pair_stable"] is True
    assert migration_release_evidence_comparison_resp.json()["decision"]["release_approved_now"] is False
    assert migration_release_evidence_comparison_resp.json()["decision"]["execution_allowed_now"] is False
    assert migration_release_evidence_comparison_resp.json()["safety_summary"]["persists_manual_release_evidence_comparison"] is False
    assert migration_release_evidence_comparison_resp.json()["safety_summary"]["writes_database_now"] is False
    assert migration_release_health_digest_resp.json()["status"] == "manual_release_health_digest_healthy"
    assert migration_release_health_digest_resp.json()["decision"]["digest_healthy"] is True
    assert migration_release_health_digest_resp.json()["decision"]["release_approved_now"] is False
    assert migration_release_health_digest_resp.json()["decision"]["execution_allowed_now"] is False
    assert migration_release_health_digest_resp.json()["safety_summary"]["persists_manual_release_health_digest"] is False
    assert migration_release_health_digest_resp.json()["safety_summary"]["writes_database_now"] is False
    assert migration_release_health_digest_history_resp.json()["status"] == "history_retention_proposal_ready"
    assert migration_release_health_digest_history_resp.json()["decision"]["history_persistence_enabled_now"] is False
    assert migration_release_health_digest_history_resp.json()["safety_summary"]["persists_manual_release_health_digest_history"] is False
    assert migration_release_health_digest_history_resp.json()["safety_summary"]["writes_database_now"] is False
    assert migration_release_health_digest_history_checklist_resp.json()["status"] == "history_migration_readiness_review_ready"
    assert migration_release_health_digest_history_checklist_resp.json()["decision"]["migration_allowed_now"] is False
    assert migration_release_health_digest_history_checklist_resp.json()["safety_summary"]["persists_manual_release_health_digest_history"] is False
    assert migration_release_health_digest_history_checklist_resp.json()["safety_summary"]["writes_database_now"] is False
    assert migration_release_health_digest_history_checklist_resp.json()["safety_summary"]["writes_file"] is False
    assert migration_release_health_digest_history_spec_resp.json()["status"] == "spec_verification_passed"
    assert migration_release_health_digest_history_spec_resp.json()["decision"]["can_execute_sql_now"] is False
    assert migration_release_health_digest_history_spec_resp.json()["decision"]["can_write_history_row_now"] is False
    assert migration_release_health_digest_history_spec_resp.json()["safety_summary"]["persists_manual_release_health_digest_history"] is False
    assert migration_release_health_digest_history_spec_resp.json()["safety_summary"]["executes_sql"] is False
    assert migration_release_health_digest_history_spec_resp.json()["safety_summary"]["writes_database_now"] is False
    assert migration_release_health_digest_history_spec_approval_resp.json()["status"] == "approval_metadata_recorded"
    assert migration_release_health_digest_history_spec_approval_resp.json()["safety_summary"]["writes_existing_event_now"] is True
    assert migration_release_health_digest_history_spec_approval_resp.json()["safety_summary"]["writes_history_row_now"] is False
    assert migration_release_health_digest_history_spec_approval_resp.json()["safety_summary"]["executes_sql"] is False
    assert migration_release_health_digest_history_spec_approval_resp.json()["migration_allowed_now"] is False
    assert (
        migration_release_health_digest_history_spec_approvals_resp.json()[0]["event_id"]
        == migration_release_health_digest_history_spec_approval_resp.json()["event_id"]
    )
    assert migration_release_health_digest_history_readiness_resp.json()["status"] == "release_evidence_ready"
    assert migration_release_health_digest_history_readiness_resp.json()["decision"]["go_no_go"] == "go_for_manual_release_review"
    assert migration_release_health_digest_history_readiness_resp.json()["decision"]["migration_allowed_now"] is False
    assert migration_release_health_digest_history_readiness_resp.json()["decision"]["release_approved_now"] is False
    assert migration_release_health_digest_history_readiness_resp.json()["evidence"]["latest_approval_event_id"] == migration_release_health_digest_history_spec_approval_resp.json()["event_id"]
    assert migration_release_health_digest_history_readiness_resp.json()["safety_summary"]["writes_history_row_now"] is False
    assert migration_release_health_digest_history_readiness_resp.json()["safety_summary"]["executes_sql"] is False
    assert migration_release_health_digest_history_approval_review_resp.json()["status"] == "approval_current"
    assert migration_release_health_digest_history_approval_review_resp.json()["latest_approval"]["event_id"] == migration_release_health_digest_history_spec_approval_resp.json()["event_id"]
    assert migration_release_health_digest_history_approval_review_resp.json()["decision"]["approval_can_be_reused_for_manual_release_review"] is True
    assert migration_release_health_digest_history_approval_review_resp.json()["decision"]["migration_allowed_now"] is False
    assert migration_release_health_digest_history_approval_review_resp.json()["decision"]["release_approved_now"] is False
    assert migration_release_health_digest_history_approval_review_resp.json()["safety_summary"]["writes_history_row_now"] is False
    assert migration_release_health_digest_history_approval_review_resp.json()["safety_summary"]["executes_sql"] is False
    assert migration_release_health_digest_history_release_package_resp.json()["status"] == "release_package_ready_for_manual_review"
    assert migration_release_health_digest_history_release_package_resp.json()["decision"]["go_no_go"] == "ready_for_manual_release_review"
    assert migration_release_health_digest_history_release_package_resp.json()["decision"]["migration_allowed_now"] is False
    assert migration_release_health_digest_history_release_package_resp.json()["decision"]["execution_allowed_now"] is False
    assert migration_release_health_digest_history_release_package_resp.json()["decision"]["release_approved_now"] is False
    assert migration_release_health_digest_history_release_package_resp.json()["evidence"]["latest_approval_event_id"] == migration_release_health_digest_history_spec_approval_resp.json()["event_id"]
    assert migration_release_health_digest_history_release_package_resp.json()["manifest"]["writes_file"] is False
    assert migration_release_health_digest_history_release_package_resp.json()["manifest"]["download_created"] is False
    assert migration_release_health_digest_history_release_package_resp.json()["safety_summary"]["writes_history_row_now"] is False
    assert migration_release_health_digest_history_release_package_resp.json()["safety_summary"]["executes_sql"] is False
    assert migration_release_health_digest_history_package_integrity_resp.json()["status"] == "integrity_review_passed"
    assert migration_release_health_digest_history_package_integrity_resp.json()["source_package_id"] == migration_release_health_digest_history_package_integrity_resp.json()["recomputed_package_id"]
    assert migration_release_health_digest_history_package_integrity_resp.json()["decision"]["package_id_stable"] is True
    assert migration_release_health_digest_history_package_integrity_resp.json()["decision"]["manifest_integrity_passed"] is True
    assert migration_release_health_digest_history_package_integrity_resp.json()["decision"]["execution_allowed_now"] is False
    assert migration_release_health_digest_history_package_integrity_resp.json()["decision"]["release_approved_now"] is False
    assert migration_release_health_digest_history_package_integrity_resp.json()["safety_summary"]["writes_file"] is False
    assert migration_release_health_digest_history_package_integrity_resp.json()["safety_summary"]["mutates_source_package"] is False
    assert migration_release_health_digest_history_release_rehearsal_resp.json()["status"] == "manual_release_rehearsal_ready"
    assert migration_release_health_digest_history_release_rehearsal_resp.json()["source_package_status"] == "release_package_ready_for_manual_review"
    assert migration_release_health_digest_history_release_rehearsal_resp.json()["integrity_status"] == "integrity_review_passed"
    assert migration_release_health_digest_history_release_rehearsal_resp.json()["decision"]["go_no_go"] == "ready_for_offline_manual_review"
    assert migration_release_health_digest_history_release_rehearsal_resp.json()["decision"]["manual_review_recorded_now"] is False
    assert migration_release_health_digest_history_release_rehearsal_resp.json()["decision"]["release_approved_now"] is False
    assert migration_release_health_digest_history_release_rehearsal_resp.json()["decision"]["execution_allowed_now"] is False
    assert migration_release_health_digest_history_release_rehearsal_resp.json()["operator_rehearsal_policy"]["api_can_record_operator_review"] is False
    assert migration_release_health_digest_history_release_rehearsal_resp.json()["safety_summary"]["records_manual_review_now"] is False
    assert migration_release_health_digest_history_release_rehearsal_resp.json()["safety_summary"]["writes_history_row_now"] is False
    assert migration_release_health_digest_history_evidence_resp.json()["status"] == "manual_release_health_digest_history_evidence_verification_passed"
    assert migration_release_health_digest_history_evidence_resp.json()["rehearsal_status"] == "manual_release_rehearsal_ready"
    assert migration_release_health_digest_history_evidence_resp.json()["decision"]["evidence_complete"] is True
    assert migration_release_health_digest_history_evidence_resp.json()["decision"]["manual_review_recorded_now"] is False
    assert migration_release_health_digest_history_evidence_resp.json()["decision"]["release_approved_now"] is False
    assert migration_release_health_digest_history_evidence_resp.json()["decision"]["execution_allowed_now"] is False
    assert migration_release_health_digest_history_evidence_resp.json()["safety_summary"]["persists_manual_release_health_digest_history_evidence"] is False
    assert migration_release_health_digest_history_evidence_resp.json()["safety_summary"]["writes_history_row_now"] is False
    assert migration_release_health_digest_history_evidence_resp.json()["safety_summary"]["executes_sql"] is False
    assert gates_resp.json()["blocked_gate_count"] == 0
    assert health_resp.json()["live_trading_enabled"] is False
