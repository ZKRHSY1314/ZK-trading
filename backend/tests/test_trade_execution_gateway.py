from app.config import settings
from app.trade_execution.gateway import TradeExecutionGatewayService


def test_trade_execution_gateway_capabilities_are_review_only():
    data = TradeExecutionGatewayService().capabilities()

    assert data["stage"] == "V5.5-P3"
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
    assert "place_real_trade" in data["forbidden_modes"]
    assert "enable_gateway_by_api" in data["forbidden_modes"]
    assert "instantiate_broker_adapter" in data["forbidden_modes"]
    assert "broker_network_call" in data["forbidden_modes"]
    assert "execute_failure_runbook" in data["forbidden_modes"]
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
    assert data["safety_summary"]["places_real_trade"] is False
    assert data["safety_summary"]["connects_broker"] is False


def test_trade_execution_gateway_review_gates_are_pre_live_metadata_only():
    data = TradeExecutionGatewayService().review_gates()
    gates = {gate["name"]: gate for gate in data["gates"]}

    assert data["stage"] == "V5.5-P3"
    assert data["status"] == "order_failure_runbook_mapping_ready"
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
    assert data["decision"]["ready_for_live_enablement"] is False
    assert data["decision"]["live_trading_enabled"] is False
    assert data["safety_summary"]["real_money_execution_enabled"] is False


def test_manual_confirmation_contract_is_review_only():
    data = TradeExecutionGatewayService().manual_confirmation_contract()
    input_names = {item["name"] for item in data["required_operator_inputs"]}

    assert data["schema_version"] == "trade_execution_manual_confirmation_contract.v1"
    assert data["stage"] == "V5.5-P3"
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
    assert data["stage"] == "V5.5-P3"
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
    assert data["stage"] == "V5.5-P3"
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
    assert data["stage"] == "V5.5-P3"
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
    assert data["stage"] == "V5.5-P3"
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
    assert manifest["review_gates"]["status"] == "order_failure_runbook_mapping_ready"
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
    assert data["stage"] == "V5.5-P3"
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
    assert data["stage"] == "V5.5-P3"
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
    assert data["stage"] == "V5.5-P3"
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
    assert data["stage"] == "V5.5-P3"
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
    assert data["stage"] == "V5.5-P3"
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
    assert data["stage"] == "V5.5-P3"
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


def test_operator_acceptance_checklist_is_review_only_and_cannot_record_acceptance():
    data = TradeExecutionGatewayService().operator_acceptance_checklist()
    item_ids = {item["id"] for item in data["checklist_items"]}

    assert data["schema_version"] == "trade_execution_operator_acceptance_checklist.v1"
    assert data["stage"] == "V5.5-P3"
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
    assert data["stage"] == "V5.5-P3"
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
    assert gates_resp.json()["blocked_gate_count"] == 0
    assert health_resp.json()["live_trading_enabled"] is False
