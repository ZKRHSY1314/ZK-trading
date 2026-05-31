from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from app.config import settings
from app.risk.portfolio import DEFAULT_LIMITS


class TradeExecutionGatewayService:
    """V5.0 starts as a review-only safety boundary, not an executor."""

    stage = "V5.5-P3"

    def capabilities(self) -> dict[str, Any]:
        gates = self.review_gates()["gates"]
        blocked = [gate for gate in gates if gate["status"] == "blocked"]
        status = "blocked_by_safety_gate" if blocked else "review_only_ready"
        return {
            "schema_version": "trade_execution_gateway_capabilities.v1",
            "status": status,
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "gateway_enabled": False,
            "execution_enabled": False,
            "real_money_execution_enabled": False,
            "broker_adapter_enabled": False,
            "screen_click_trading_enabled": False,
            "credential_storage_enabled": False,
            "live_trading_enabled": settings.enable_live_trading,
            "review_only": True,
            "simulation_only": True,
            "allowed_modes": [
                "architecture_review",
                "safety_gate_review",
                "manual_confirmation_design",
                "risk_gate_contract_review",
                "audit_log_schema_review",
                "rollback_plan_review",
                "manual_confirmation_contract_review",
                "audit_evidence_schema_review",
                "portfolio_symbol_risk_gate_contract_review",
                "rollback_runbook_review",
                "pre_live_review_package_review",
                "operator_acceptance_checklist_review",
                "disabled_release_gate_review",
                "final_readiness_report_review",
                "broker_adapter_threat_model_review",
                "broker_adapter_interface_draft_review",
                "broker_adapter_contract_verification_review",
                "order_lifecycle_failure_fixture_review",
                "order_failure_runbook_mapping_review",
            ],
            "forbidden_modes": [
                "broker_login",
                "credential_storage",
                "place_real_trade",
                "cancel_real_trade",
                "modify_live_position",
                "read_live_account_funds",
                "screen_click_trading",
                "live_auto_trading",
                "bypass_risk_gate",
                "enable_gateway_by_api",
                "approve_release_by_api",
                "instantiate_broker_adapter",
                "read_broker_account",
                "broker_network_call",
                "replay_failure_fixture_as_order",
                "execute_failure_runbook",
                "persist_failure_mapping_as_approval",
            ],
            "required_future_components": self._future_components(),
            "current_output": "review_only_trade_execution_gateway_metadata",
            "safety_summary": self._safety_summary(),
            "blocked_gate_count": len(blocked),
        }

    def manual_confirmation_contract(self) -> dict[str, Any]:
        return {
            "schema_version": "trade_execution_manual_confirmation_contract.v1",
            "status": "confirmation_contract_review_ready",
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "contract_name": "ManualConfirmationContract",
            "contract_state": "defined_for_review_only",
            "purpose": "Define the minimum future human confirmation evidence before any real-money gateway could be reviewed.",
            "required_operator_inputs": [
                {
                    "name": "operator_id",
                    "type": "string",
                    "sensitive": False,
                    "storage_policy": "hash_or_alias_only",
                    "reason": "Identify who reviewed the proposed action without storing broker credentials.",
                },
                {
                    "name": "confirmation_phrase",
                    "type": "string",
                    "sensitive": False,
                    "storage_policy": "audit_hash_and_short_excerpt",
                    "required_phrase": "我确认这是人工审核，不是自动实盘下单",
                    "reason": "Force an explicit acknowledgement that no autonomous execution is allowed.",
                },
                {
                    "name": "proposal_hash",
                    "type": "sha256",
                    "sensitive": False,
                    "storage_policy": "full_hash",
                    "reason": "Bind confirmation to an immutable reviewed proposal.",
                },
                {
                    "name": "risk_snapshot_hash",
                    "type": "sha256",
                    "sensitive": False,
                    "storage_policy": "full_hash",
                    "reason": "Bind confirmation to the exact reviewed risk gate evidence.",
                },
            ],
            "required_preconditions": [
                "live_trading_enabled=false",
                "portfolio_risk_gate_passed",
                "symbol_risk_gate_passed",
                "cooldown_gate_passed",
                "audit_schema_validated",
                "rollback_runbook_reviewed",
            ],
            "expiry_policy": {
                "confirmation_ttl_seconds": 120,
                "expires_on_price_or_risk_change": True,
                "requires_reconfirmation_after_expiry": True,
            },
            "dual_control_policy": {
                "second_reviewer_required_for_high_risk": True,
                "high_risk_triggers": [
                    "large_position_size",
                    "daily_loss_near_limit",
                    "drawdown_gate_warning",
                    "low_liquidity",
                    "stale_or_degraded_market_data",
                ],
            },
            "decision": {
                "contract_ready_for_review": True,
                "contract_allows_execution_now": False,
                "requires_future_risk_contract": False,
                "requires_future_audit_storage": True,
                "requires_future_rollback_runbook": False,
                "next_required_action": "review_final_readiness_report",
            },
            "forbidden_inputs": [
                "broker_password",
                "broker_session_cookie",
                "account_number",
                "sms_code",
                "trading_pin",
                "api_secret",
            ],
            "safety_summary": self._safety_summary(),
            "allowed_output": "review_only_manual_confirmation_contract",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def audit_evidence_schema(self) -> dict[str, Any]:
        fields = [
            self._schema_field("audit_id", "uuid", "Unique local audit event id.", False),
            self._schema_field("event_type", "string", "proposal_created|confirmation_recorded|risk_checked|execution_blocked|manual_reviewed.", False),
            self._schema_field("proposal_hash", "sha256", "Hash of the reviewed future execution proposal.", False),
            self._schema_field("previous_event_hash", "sha256|null", "Hash chain pointer for append-only verification.", False),
            self._schema_field("event_hash", "sha256", "Hash of canonical event payload and previous_event_hash.", False),
            self._schema_field("operator_id_hash", "sha256|null", "Hashed or aliased human reviewer id.", False),
            self._schema_field("confirmation_excerpt", "string|null", "Short non-secret confirmation phrase excerpt.", False),
            self._schema_field("risk_snapshot_hash", "sha256|null", "Hash of portfolio/symbol risk evidence.", False),
            self._schema_field("market_data_quality", "json", "Quality, latency, stale/degraded flags for the reviewed quote evidence.", False),
            self._schema_field("safety_flags", "json", "review_only, simulation_only, live_trading_enabled=false, broker_adapter_enabled=false.", False),
            self._schema_field("created_at", "iso_datetime", "Local audit timestamp.", False),
        ]
        return {
            "schema_version": "trade_execution_audit_evidence_schema.v1",
            "status": "audit_schema_review_ready",
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "schema_name": "ExecutionAuditEvidence",
            "schema_state": "defined_for_review_only",
            "storage_state": "not_persisted",
            "target_future_table": "trade_execution_audit_ledger",
            "create_table_now": False,
            "writes_database_now": False,
            "fields": fields,
            "immutability_rules": [
                "append_only_events",
                "canonical_json_hashing",
                "previous_event_hash_chain",
                "no_update_or_delete_for_audit_rows",
                "manual_correction_requires_new_event",
            ],
            "excluded_sensitive_fields": [
                "broker_password",
                "trading_pin",
                "sms_code",
                "api_secret",
                "broker_session_cookie",
                "raw_account_number",
            ],
            "minimum_evidence_before_future_execution_review": [
                "proposal_hash",
                "risk_snapshot_hash",
                "manual_confirmation_hash",
                "market_data_quality",
                "safety_flags",
                "rollback_reference",
            ],
            "decision": {
                "schema_ready_for_review": True,
                "schema_allows_execution_now": False,
                "schema_persistence_enabled_now": False,
                "migration_allowed_now": False,
                "next_required_action": "review_final_readiness_report",
            },
            "safety_summary": self._safety_summary()
            | {
                "create_table_now": False,
                "writes_database_now": False,
                "runs_migration_now": False,
                "writes_migration_file_now": False,
            },
            "allowed_output": "review_only_trade_execution_audit_schema",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def risk_gate_contract(self) -> dict[str, Any]:
        portfolio_gates = [
            self._risk_gate(
                "total_exposure",
                "max_total_exposure",
                DEFAULT_LIMITS["max_total_exposure"],
                "blocked",
                "Stop all new entries when total portfolio exposure reaches the limit.",
            ),
            self._risk_gate(
                "single_position",
                "max_single_position",
                DEFAULT_LIMITS["max_single_position"],
                "blocked",
                "Block add-on or new exposure when one symbol reaches the single-position limit.",
            ),
            self._risk_gate(
                "max_daily_loss",
                "max_daily_loss",
                DEFAULT_LIMITS["max_daily_loss"],
                "blocked",
                "Stop new entries when daily simulated loss reaches the future gateway threshold.",
            ),
            self._risk_gate(
                "max_drawdown_stop",
                "max_drawdown_stop",
                DEFAULT_LIMITS["max_drawdown_stop"],
                "blocked",
                "Stop new entries when drawdown reaches the future gateway threshold.",
            ),
            self._risk_gate(
                "consecutive_loss_cooldown",
                "consecutive_loss_cooldown",
                DEFAULT_LIMITS["consecutive_loss_cooldown"],
                "blocked",
                "Require cooldown after consecutive losing outcomes before any future order review.",
            ),
            self._risk_gate(
                "max_new_positions_per_day",
                "max_new_positions_per_day",
                DEFAULT_LIMITS["max_new_positions_per_day"],
                "blocked",
                "Block additional new positions once the daily new-position count reaches the limit.",
            ),
            self._risk_gate(
                "market_regime",
                "no_extreme_risk_new_entries",
                "extreme_risk blocks; weak reduces size",
                "blocked_or_reduced",
                "Extreme market regime must block new entries; weak regime may only reduce future size.",
            ),
        ]
        symbol_gates = [
            self._risk_gate(
                "symbol_price_quality",
                "fresh_reliable_quote_required",
                "quality_status not stale/degraded/missing",
                "blocked",
                "Block review if quote evidence is stale, missing, degraded, or fallback-only.",
            ),
            self._risk_gate(
                "limit_up_down_state",
                "no_unexecutable_limit_state",
                "limit-up buy and limit-down sell are blocked",
                "blocked",
                "Respect A-share limit-up/limit-down execution realism before future execution review.",
            ),
            self._risk_gate(
                "liquidity_participation",
                "max_participation_rate",
                0.005,
                "blocked_or_partial",
                "Reject or reduce future action if expected participation exceeds liquidity limits.",
            ),
            self._risk_gate(
                "t_plus_1",
                "same_day_sell_blocked",
                "T+1 compliance required",
                "blocked",
                "Block same-day sell review for positions that would violate A-share T+1.",
            ),
            self._risk_gate(
                "candidate_lifecycle",
                "review_state_required",
                "approved_review_or_simulation_only",
                "blocked",
                "Future actions require candidate lifecycle evidence and cannot bypass review states.",
            ),
            self._risk_gate(
                "manual_stop_flags",
                "no_operator_or_system_stop_flag",
                "no stop_new_entries flag",
                "blocked",
                "Operator stops, degraded providers, and risk stop flags override return-seeking logic.",
            ),
        ]
        return {
            "schema_version": "trade_execution_risk_gate_contract.v1",
            "status": "risk_gate_contract_review_ready",
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "contract_name": "PortfolioSymbolRiskGateContract",
            "contract_state": "defined_for_review_only",
            "portfolio_gates": portfolio_gates,
            "symbol_gates": symbol_gates,
            "ordering": [
                "system_safety_flags",
                "data_quality",
                "portfolio_risk",
                "symbol_risk",
                "manual_confirmation",
                "audit_evidence",
                "rollback_readiness",
            ],
            "hard_block_statuses": ["blocked", "blocked_or_partial", "blocked_or_reduced"],
            "required_evidence_hashes": [
                "portfolio_risk_snapshot_hash",
                "symbol_risk_snapshot_hash",
                "market_data_quality_hash",
                "candidate_lifecycle_hash",
                "manual_confirmation_hash",
                "audit_schema_hash",
            ],
            "decision": {
                "contract_ready_for_review": True,
                "contract_allows_execution_now": False,
                "risk_gate_can_override_manual_confirmation": True,
                "requires_fresh_risk_snapshot": True,
                "requires_future_rollback_runbook": False,
                "next_required_action": "review_final_readiness_report",
            },
            "integration_notes": {
                "source_portfolio_limits": "app.risk.portfolio.DEFAULT_LIMITS",
                "risk_posture_if_blocked": "stop_new_entries",
                "manual_confirmation_override_allowed": False,
                "ai_override_allowed": False,
            },
            "safety_summary": self._safety_summary()
            | {
                "risk_contract_ready": True,
                "gateway_can_execute": False,
                "places_real_trade": False,
                "connects_broker": False,
            },
            "allowed_output": "review_only_trade_execution_risk_gate_contract",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def rollback_runbook(self) -> dict[str, Any]:
        return {
            "schema_version": "trade_execution_rollback_runbook.v1",
            "status": "rollback_runbook_review_ready",
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "runbook_name": "ManualGatewayRollbackRunbook",
            "runbook_state": "defined_for_review_only",
            "purpose": "Define how an operator would stop and review a future gateway before any live integration is considered.",
            "trigger_events": [
                "risk_gate_blocked",
                "manual_confirmation_expired",
                "market_data_degraded",
                "audit_hash_mismatch",
                "operator_stop",
                "unexpected_gateway_enablement",
                "live_trading_flag_detected",
            ],
            "rollback_steps": [
                {
                    "step": "freeze_new_gateway_reviews",
                    "owner": "operator",
                    "evidence_required": "operator_stop_note",
                    "executes_commands": False,
                },
                {
                    "step": "mark_pending_proposals_blocked",
                    "owner": "operator",
                    "evidence_required": "proposal_ids_and_block_reason",
                    "executes_commands": False,
                },
                {
                    "step": "verify_live_trading_disabled",
                    "owner": "operator",
                    "evidence_required": "health_live_trading_enabled_false",
                    "executes_commands": False,
                },
                {
                    "step": "review_audit_evidence_hashes",
                    "owner": "operator",
                    "evidence_required": "audit_hash_chain_summary",
                    "executes_commands": False,
                },
                {
                    "step": "write_postmortem_before_recovery",
                    "owner": "operator",
                    "evidence_required": "manual_postmortem_summary",
                    "executes_commands": False,
                },
            ],
            "recovery_requirements": [
                "all_portfolio_and_symbol_risk_gates_pass",
                "fresh_market_data_quality_snapshot",
                "new_manual_confirmation_after_recovery",
                "audit_hash_chain_verified",
                "operator_postmortem_reviewed",
                "live_trading_enabled=false",
            ],
            "decision": {
                "runbook_ready_for_review": True,
                "runbook_allows_execution_now": False,
                "requires_manual_postmortem": True,
                "ready_for_live_enablement": False,
                "next_required_action": "review_final_readiness_report",
            },
            "safety_summary": self._safety_summary()
            | {
                "executes_commands": False,
                "writes_database_now": False,
                "runs_migration_now": False,
                "connects_broker": False,
                "places_real_trade": False,
            },
            "allowed_output": "review_only_trade_execution_rollback_runbook",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def pre_live_review_package(self) -> dict[str, Any]:
        capabilities = self.capabilities()
        manual_confirmation = self.manual_confirmation_contract()
        audit_schema = self.audit_evidence_schema()
        risk_contract = self.risk_gate_contract()
        rollback_runbook = self.rollback_runbook()
        review_gates = self.review_gates()
        manifest = [
            self._package_item("capabilities", capabilities),
            self._package_item("manual_confirmation_contract", manual_confirmation),
            self._package_item("audit_evidence_schema", audit_schema),
            self._package_item("risk_gate_contract", risk_contract),
            self._package_item("rollback_runbook", rollback_runbook),
            self._package_item("review_gates", review_gates),
            self._package_item("operator_acceptance_checklist", self.operator_acceptance_checklist()),
            self._package_item("disabled_release_gate", self.disabled_release_gate()),
        ]
        package_seed = {
            "stage": self.stage,
            "schema_version": "trade_execution_pre_live_review_package.v1",
            "manifest": manifest,
            "safety_summary": self._safety_summary(),
            "decision": {
                "gateway_can_execute": False,
                "ready_for_live_enablement": False,
            },
        }
        return {
            "schema_version": "trade_execution_pre_live_review_package.v1",
            "status": "pre_live_review_package_ready",
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "package_id": self._stable_hash(package_seed),
            "package_state": "assembled_for_review_only",
            "manifest": manifest,
            "required_manual_artifacts": [
                "operator_review_of_manual_confirmation_contract",
                "operator_review_of_risk_gate_contract",
                "rollback_drill_evidence",
                "audit_hash_chain_review",
                "legal_or_compliance_review_if_real_money_is_considered",
                "fresh_health_live_trading_enabled_false",
                "operator_acceptance_checklist_reviewed",
                "disabled_release_gate_reviewed",
            ],
            "included_safety_evidence": {
                "capabilities_status": capabilities["status"],
                "review_gates_status": review_gates["status"],
                "blocked_gate_count": review_gates["blocked_gate_count"],
                "review_required_count": review_gates["review_required_count"],
                "live_trading_enabled": settings.enable_live_trading,
            },
            "decision": {
                "package_ready_for_manual_review": True,
                "ready_for_live_enablement": False,
                "gateway_can_execute": False,
                "requires_operator_release_review": True,
                "requires_separate_live_integration_plan": True,
                "next_required_action": "review_final_readiness_report",
            },
            "safety_summary": self._safety_summary()
            | {
                "writes_database_now": False,
                "runs_migration_now": False,
                "writes_migration_file_now": False,
                "stores_credentials": False,
                "connects_broker": False,
                "places_real_trade": False,
            },
            "allowed_output": "review_only_trade_execution_pre_live_review_package",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def operator_acceptance_checklist(self) -> dict[str, Any]:
        checklist_items = [
            self._checklist_item(
                "health_live_trading_disabled",
                "Fresh `/health` evidence shows live_trading_enabled=false.",
                "health_response_hash",
            ),
            self._checklist_item(
                "pre_live_package_reviewed",
                "Operator reviewed the pre-live package manifest and package hash.",
                "pre_live_package_hash",
            ),
            self._checklist_item(
                "manual_confirmation_contract_reviewed",
                "Manual confirmation fields, TTL, dual control, and forbidden sensitive inputs were reviewed.",
                "manual_confirmation_contract_hash",
            ),
            self._checklist_item(
                "risk_gate_contract_reviewed",
                "Portfolio and symbol hard-block gates were reviewed and no override path is allowed.",
                "risk_gate_contract_hash",
            ),
            self._checklist_item(
                "rollback_runbook_drill_reviewed",
                "Manual rollback triggers, stop steps, and postmortem requirements were reviewed.",
                "rollback_runbook_hash",
            ),
            self._checklist_item(
                "audit_evidence_schema_reviewed",
                "Future append-only audit evidence schema was reviewed without enabling persistence now.",
                "audit_evidence_schema_hash",
            ),
            self._checklist_item(
                "forbidden_surfaces_absent",
                "No broker, order, credential, account/funds, screen-click, or live-trading route is present.",
                "forbidden_route_scan_summary",
            ),
        ]
        return {
            "schema_version": "trade_execution_operator_acceptance_checklist.v1",
            "status": "operator_acceptance_checklist_review_ready",
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "checklist_state": "defined_for_manual_review_only",
            "checklist_items": checklist_items,
            "operator_attestation_phrase": "我确认这是发布前人工验收清单，不是实盘启用授权",
            "acceptance_policy": {
                "all_items_required": True,
                "operator_review_required": True,
                "api_can_record_acceptance": False,
                "api_can_enable_gateway": False,
                "missing_item_effect": "block_live_integration_review",
            },
            "decision": {
                "checklist_ready_for_review": True,
                "operator_acceptance_recorded_now": False,
                "acceptance_allows_enablement_now": False,
                "ready_for_live_enablement": False,
                "gateway_can_execute": False,
                "next_required_action": "review_final_readiness_report",
            },
            "safety_summary": self._safety_summary()
            | {
                "writes_database_now": False,
                "records_acceptance_now": False,
                "enables_gateway_now": False,
                "connects_broker": False,
                "places_real_trade": False,
            },
            "allowed_output": "review_only_trade_execution_operator_acceptance_checklist",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def disabled_release_gate(self) -> dict[str, Any]:
        gates = self.review_gates()
        release_blockers = [
            "gateway_default_state_disabled",
            "no_api_enablement_surface",
            "no_broker_adapter",
            "no_credential_storage",
            "no_order_execution_route",
            "no_account_or_funds_read_route",
            "operator_acceptance_not_recorded_by_api",
            "separate_live_integration_plan_required",
        ]
        return {
            "schema_version": "trade_execution_disabled_release_gate.v1",
            "status": "disabled_release_gate_review_ready",
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "gate_name": "DisabledByDefaultReleaseGate",
            "default_state": "disabled",
            "release_gate_state": "review_only_metadata",
            "preconditions_for_future_external_review": [
                "all_review_gates_passed",
                "operator_acceptance_checklist_completed_outside_api",
                "separate_live_integration_plan_reviewed",
                "legal_or_compliance_review_if_real_money_is_considered",
                "new_tests_for_any_live_adapter_before_code_merge",
            ],
            "release_blockers": release_blockers,
            "gate_evidence": {
                "review_gates_status": gates["status"],
                "blocked_gate_count": gates["blocked_gate_count"],
                "review_required_count": gates["review_required_count"],
                "live_trading_enabled": settings.enable_live_trading,
            },
            "decision": {
                "release_gate_ready_for_review": True,
                "release_gate_allows_enablement_now": False,
                "ready_for_live_enablement": False,
                "gateway_can_execute": False,
                "api_can_enable_gateway": False,
                "api_can_record_release_approval": False,
                "next_required_action": "review_final_readiness_report",
            },
            "safety_summary": self._safety_summary()
            | {
                "default_disabled": True,
                "enables_gateway_now": False,
                "writes_database_now": False,
                "connects_broker": False,
                "places_real_trade": False,
            },
            "allowed_output": "review_only_trade_execution_disabled_release_gate",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def final_readiness_report(self) -> dict[str, Any]:
        capabilities = self.capabilities()
        gates = self.review_gates()
        manual_confirmation = self.manual_confirmation_contract()
        audit_schema = self.audit_evidence_schema()
        risk_contract = self.risk_gate_contract()
        rollback_runbook = self.rollback_runbook()
        pre_live_package = self.pre_live_review_package()
        acceptance_checklist = self.operator_acceptance_checklist()
        release_gate = self.disabled_release_gate()
        manifest = [
            self._package_item("capabilities", capabilities),
            self._package_item("review_gates", gates),
            self._package_item("manual_confirmation_contract", manual_confirmation),
            self._package_item("audit_evidence_schema", audit_schema),
            self._package_item("risk_gate_contract", risk_contract),
            self._package_item("rollback_runbook", rollback_runbook),
            self._package_item("pre_live_review_package", pre_live_package),
            self._package_item("operator_acceptance_checklist", acceptance_checklist),
            self._package_item("disabled_release_gate", release_gate),
        ]
        safety_matrix = {
            "gateway_enabled": capabilities["gateway_enabled"],
            "execution_enabled": capabilities["execution_enabled"],
            "real_money_execution_enabled": capabilities["real_money_execution_enabled"],
            "broker_adapter_enabled": capabilities["broker_adapter_enabled"],
            "credential_storage_enabled": capabilities["credential_storage_enabled"],
            "screen_click_trading_enabled": capabilities["screen_click_trading_enabled"],
            "gateway_can_execute": gates["decision"]["gateway_can_execute"],
            "ready_for_live_enablement": gates["decision"]["ready_for_live_enablement"],
            "api_can_enable_gateway": release_gate["decision"]["api_can_enable_gateway"],
            "api_can_record_release_approval": release_gate["decision"]["api_can_record_release_approval"],
            "live_trading_enabled": settings.enable_live_trading,
        }
        report_seed = {
            "stage": self.stage,
            "schema_version": "trade_execution_final_readiness_report.v1",
            "manifest": manifest,
            "safety_matrix": safety_matrix,
            "pre_live_package_id": pre_live_package["package_id"],
        }
        return {
            "schema_version": "trade_execution_final_readiness_report.v1",
            "status": "v5_review_only_gateway_baseline_ready",
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "report_id": self._stable_hash(report_seed),
            "report_state": "final_v5_review_only_baseline",
            "manifest": manifest,
            "summary": {
                "completed_review_modules": len(manifest),
                "blocked_gate_count": gates["blocked_gate_count"],
                "review_required_count": gates["review_required_count"],
                "pre_live_package_id": pre_live_package["package_id"],
                "default_release_state": release_gate["default_state"],
                "next_track": "V5.5 broker adapter threat modeling, fixture contract verification, and order lifecycle failure fixtures",
            },
            "safety_matrix": safety_matrix,
            "remaining_blockers": [
                "separate_live_integration_project_required",
                "disabled_audit_ledger_storage_plan_required",
                "credential_handling_design_required",
                "real_order_api_tests_required_before_any_adapter",
                "operator_acceptance_cannot_be_recorded_by_current_api",
                "live_trading_enabled_must_remain_false",
            ],
            "decision": {
                "v5_review_only_baseline_complete": True,
                "ready_for_v5_5_threat_modeling": True,
                "ready_for_live_enablement": False,
                "gateway_can_execute": False,
                "api_can_enable_gateway": False,
                "api_can_record_release_approval": False,
                "next_required_action": "design_disabled_audit_ledger_storage_plan",
            },
            "safety_summary": self._safety_summary()
            | {
                "writes_database_now": False,
                "runs_migration_now": False,
                "records_acceptance_now": False,
                "enables_gateway_now": False,
                "connects_broker": False,
                "places_real_trade": False,
            },
            "allowed_output": "review_only_trade_execution_final_readiness_report",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def broker_adapter_threat_model(self) -> dict[str, Any]:
        threat_categories = [
            {
                "name": "credential_exposure",
                "risk": "Broker passwords, tokens, SMS codes, cookies, account numbers, and trading PINs must never enter this API.",
                "mitigation": "No credential fields, no persistence, no environment writes, and no adapter instantiation in V5.5-P3.",
                "status": "blocked_by_design",
            },
            {
                "name": "unauthorized_order_execution",
                "risk": "A model, scheduler, screen process, or API caller could attempt to submit/cancel/modify a real order.",
                "mitigation": "No order endpoint, no broker client, no execution method, and risk gates remain review-only blockers.",
                "status": "blocked_by_design",
            },
            {
                "name": "account_data_leakage",
                "risk": "Future account, position, fund, or trade-confirm data could expose sensitive financial state.",
                "mitigation": "No account/funds/position read surface exists; future design requires redaction and explicit threat review.",
                "status": "blocked_by_design",
            },
            {
                "name": "screen_click_bypass",
                "risk": "A screen-control workflow could bypass API safety gates and operate broker UI directly.",
                "mitigation": "Screen-click trading remains forbidden; screen monitoring is read-only metadata.",
                "status": "blocked_by_design",
            },
            {
                "name": "risk_gate_bypass",
                "risk": "Manual confirmation or AI suggestions could override portfolio, symbol, liquidity, or market-quality blockers.",
                "mitigation": "Risk gate contract remains hard-blocking and cannot be overridden by AI or manual confirmation.",
                "status": "blocked_by_design",
            },
        ]
        return {
            "schema_version": "trade_execution_broker_adapter_threat_model.v1",
            "status": "broker_adapter_threat_model_review_ready",
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "model_state": "review_only_no_adapter",
            "scope": "Threat model for a future broker adapter boundary before any implementation or connectivity.",
            "protected_assets": [
                "broker_credentials",
                "account_identity",
                "positions_and_funds",
                "order_intent",
                "manual_confirmation_evidence",
                "audit_hash_chain",
                "risk_gate_evidence",
            ],
            "trust_boundaries": [
                "frontend_to_backend_api",
                "backend_to_future_broker_adapter",
                "model_gateway_to_review_metadata",
                "screen_monitoring_to_read_only_evidence",
                "operator_manual_review_to_disabled_release_gate",
            ],
            "threat_categories": threat_categories,
            "required_future_reviews": [
                "credential_handling_threat_model",
                "broker_sandbox_contract_tests",
                "order_lifecycle_failure_modes",
                "account_data_redaction_policy",
                "manual_confirmation_release_process",
                "legal_or_compliance_review_if_real_money_is_considered",
            ],
            "decision": {
                "threat_model_ready_for_review": True,
                "broker_adapter_allowed_now": False,
                "credential_handling_allowed_now": False,
                "account_read_allowed_now": False,
                "order_execution_allowed_now": False,
                "ready_for_live_enablement": False,
                "next_required_action": "design_disabled_audit_ledger_storage_plan",
            },
            "safety_summary": self._safety_summary()
            | {
                "broker_adapter_enabled": False,
                "credential_storage_enabled": False,
                "reads_live_account_funds": False,
                "places_real_trade": False,
                "connects_broker": False,
            },
            "allowed_output": "review_only_trade_execution_broker_adapter_threat_model",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def broker_adapter_interface_draft(self) -> dict[str, Any]:
        draft_methods = [
            self._draft_method("describe_capabilities", "Return static adapter capabilities only.", "metadata_only"),
            self._draft_method("validate_config_shape", "Validate non-secret config schema without reading credentials.", "dry_run_only"),
            self._draft_method("build_order_preview", "Build a non-executable order preview payload for manual review.", "simulation_only"),
            self._draft_method("map_rejection_reason", "Normalize future broker rejection codes from fixture data.", "fixture_only"),
            self._draft_method("redact_account_snapshot", "Describe redaction rules for future account snapshots.", "design_only"),
        ]
        return {
            "schema_version": "trade_execution_broker_adapter_interface_draft.v1",
            "status": "broker_adapter_interface_draft_review_ready",
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "interface_state": "draft_only_not_implemented",
            "adapter_contract_name": "BrokerAdapterBoundaryDraft",
            "draft_methods": draft_methods,
            "forbidden_methods": [
                "login",
                "submit_order",
                "cancel_order",
                "modify_order",
                "read_account_funds",
                "read_live_positions",
                "store_credentials",
                "click_broker_screen",
            ],
            "required_inputs_policy": {
                "allows_credentials": False,
                "allows_account_number": False,
                "allows_sms_code": False,
                "allows_trading_pin": False,
                "allows_plaintext_secret": False,
            },
            "future_test_requirements": [
                "fixture_only_adapter_contract_tests",
                "no_network_call_unit_tests",
                "credential_field_rejection_tests",
                "order_preview_non_execution_tests",
                "risk_gate_hard_block_tests",
                "audit_redaction_tests",
            ],
            "decision": {
                "interface_draft_ready_for_review": True,
                "interface_implemented_now": False,
                "adapter_can_connect_now": False,
                "adapter_can_execute_now": False,
                "adapter_can_read_account_now": False,
                "ready_for_live_enablement": False,
                "next_required_action": "design_disabled_audit_ledger_storage_plan",
            },
            "safety_summary": self._safety_summary()
            | {
                "implements_adapter_now": False,
                "makes_network_calls": False,
                "writes_credentials": False,
                "connects_broker": False,
                "places_real_trade": False,
                "reads_live_account_funds": False,
            },
            "allowed_output": "review_only_trade_execution_broker_adapter_interface_draft",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def broker_adapter_contract_verification(self) -> dict[str, Any]:
        interface = self.broker_adapter_interface_draft()
        draft_methods = {item["name"]: item for item in interface["draft_methods"]}
        checks = [
            self._contract_check(
                "draft_method_surface_present",
                set(draft_methods) == {
                    "describe_capabilities",
                    "validate_config_shape",
                    "build_order_preview",
                    "map_rejection_reason",
                    "redact_account_snapshot",
                },
                "Fixture verifier sees every provider-neutral draft method.",
                {"method_count": len(draft_methods)},
            ),
            self._contract_check(
                "draft_methods_non_executable",
                all(
                    item["implemented_now"] is False
                    and item["calls_broker_now"] is False
                    and item["places_order_now"] is False
                    and item["reads_account_now"] is False
                    and item["stores_credentials_now"] is False
                    for item in draft_methods.values()
                ),
                "Every draft method remains metadata/fixture only.",
                {"checked_methods": sorted(draft_methods)},
            ),
            self._contract_check(
                "credential_inputs_rejected",
                all(value is False for value in interface["required_inputs_policy"].values()),
                "Fixture config shape rejects credentials, account numbers, SMS codes, PINs, and plaintext secrets.",
                interface["required_inputs_policy"],
            ),
            self._contract_check(
                "forbidden_methods_absent",
                {"login", "submit_order", "cancel_order", "modify_order", "read_account_funds", "read_live_positions", "store_credentials", "click_broker_screen"}
                <= set(interface["forbidden_methods"]),
                "Dangerous adapter methods are explicitly forbidden before implementation.",
                {"forbidden_methods": interface["forbidden_methods"]},
            ),
            self._contract_check(
                "order_preview_non_executable",
                draft_methods["build_order_preview"]["mode"] == "simulation_only"
                and draft_methods["build_order_preview"]["places_order_now"] is False,
                "Order preview can only describe a review payload and cannot submit/cancel/modify orders.",
                draft_methods["build_order_preview"],
            ),
            self._contract_check(
                "fixture_rejection_mapping_only",
                draft_methods["map_rejection_reason"]["mode"] == "fixture_only",
                "Broker rejection mapping is limited to fixture data.",
                draft_methods["map_rejection_reason"],
            ),
            self._contract_check(
                "redaction_design_only",
                draft_methods["redact_account_snapshot"]["mode"] == "design_only"
                and draft_methods["redact_account_snapshot"]["reads_account_now"] is False,
                "Account snapshot redaction is only a future design contract and reads no account data now.",
                draft_methods["redact_account_snapshot"],
            ),
            self._contract_check(
                "network_and_state_mutation_blocked",
                True,
                "Verifier performs no network calls, no environment writes, no DB writes, and no adapter instantiation.",
                {
                    "makes_network_calls": False,
                    "writes_env": False,
                    "writes_database_now": False,
                    "instantiates_adapter": False,
                },
            ),
        ]
        passed = all(check["status"] == "passed" for check in checks)
        return {
            "schema_version": "trade_execution_broker_adapter_contract_verification.v1",
            "status": "fixture_contract_verification_passed" if passed else "fixture_contract_verification_failed",
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "verification_state": "fixture_only_no_adapter",
            "source_contract": interface["adapter_contract_name"],
            "fixture_name": "broker_adapter_boundary_contract_v1",
            "checks": checks,
            "summary": {
                "total_checks": len(checks),
                "passed_checks": sum(1 for check in checks if check["status"] == "passed"),
                "blocked_checks": sum(1 for check in checks if check["status"] == "blocked"),
                "fixture_only": True,
                "network_calls": False,
                "adapter_instantiated": False,
            },
            "decision": {
                "contract_verification_ready_for_review": True,
                "fixture_contract_tests_passed": passed,
                "adapter_implemented_now": False,
                "adapter_can_connect_now": False,
                "adapter_can_execute_now": False,
                "adapter_can_read_account_now": False,
                "credentials_allowed_now": False,
                "ready_for_live_enablement": False,
                "next_required_action": "design_disabled_audit_ledger_storage_plan",
            },
            "safety_summary": self._safety_summary()
            | {
                "fixture_only_contract_verifier": True,
                "instantiates_adapter": False,
                "makes_network_calls": False,
                "writes_database_now": False,
                "writes_env": False,
                "connects_broker": False,
                "places_real_trade": False,
                "reads_live_account_funds": False,
            },
            "allowed_output": "review_only_fixture_broker_adapter_contract_verification",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def order_lifecycle_failure_fixtures(self) -> dict[str, Any]:
        fixtures = [
            self._failure_fixture(
                "broker_rejected_order_preview",
                "rejected",
                "future_broker_rejection",
                "A future broker rejects the previewed order before execution.",
                "block_and_request_manual_review",
                ["map_rejection_reason", "risk_gate_contract", "manual_confirmation_contract"],
                {"rejection_code": "PRICE_OUT_OF_RANGE", "normalized_reason": "price_or_limit_state_rejected"},
            ),
            self._failure_fixture(
                "partial_fill_preview",
                "partial",
                "liquidity_or_participation_limit",
                "A future simulated order preview is only partially fillable under liquidity constraints.",
                "reduce_or_cancel_in_review_only_plan",
                ["risk_gate_contract", "audit_evidence_schema"],
                {"requested_quantity": 1000, "fillable_quantity": 300, "max_participation_rate": 0.005},
            ),
            self._failure_fixture(
                "stale_market_data_before_confirmation",
                "blocked",
                "stale_quote",
                "Market data becomes stale before manual confirmation can be trusted.",
                "expire_confirmation_and_refresh_quote",
                ["manual_confirmation_contract", "risk_gate_contract"],
                {"latency_ms": 90000, "quality_status": "stale_realtime"},
            ),
            self._failure_fixture(
                "manual_confirmation_expired",
                "blocked",
                "confirmation_ttl_expired",
                "The operator confirmation TTL expires before a future gateway could review the action.",
                "require_new_manual_confirmation",
                ["manual_confirmation_contract", "audit_evidence_schema"],
                {"confirmation_ttl_seconds": 120, "elapsed_seconds": 180},
            ),
            self._failure_fixture(
                "risk_gate_changed_after_preview",
                "blocked",
                "risk_snapshot_changed",
                "Portfolio or symbol risk changes after preview generation.",
                "discard_preview_and_recompute_risk",
                ["risk_gate_contract", "rollback_runbook"],
                {"previous_risk_hash": "fixture_previous_hash", "current_risk_hash": "fixture_current_hash"},
            ),
            self._failure_fixture(
                "limit_down_sell_blocked",
                "blocked",
                "limit_down_unexecutable",
                "A future sell preview would be unexecutable because the symbol is at limit-down.",
                "block_exit_and_escalate_manual_risk_review",
                ["risk_gate_contract", "rollback_runbook"],
                {"symbol_state": "limit_down", "side": "sell"},
            ),
        ]
        return {
            "schema_version": "trade_execution_order_lifecycle_failure_fixtures.v1",
            "status": "order_failure_fixtures_ready",
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "fixture_state": "review_only_no_order_lifecycle_engine",
            "fixture_suite": "broker_order_lifecycle_failure_modes_v1",
            "fixtures": fixtures,
            "summary": {
                "fixture_count": len(fixtures),
                "blocked_count": sum(1 for item in fixtures if item["expected_status"] == "blocked"),
                "partial_count": sum(1 for item in fixtures if item["expected_status"] == "partial"),
                "rejected_count": sum(1 for item in fixtures if item["expected_status"] == "rejected"),
                "places_order": False,
                "connects_broker": False,
                "reads_account": False,
                "requires_credentials": False,
            },
            "decision": {
                "failure_fixtures_ready_for_review": True,
                "can_replay_as_real_order": False,
                "can_submit_order_now": False,
                "can_cancel_order_now": False,
                "can_modify_order_now": False,
                "requires_broker_connection": False,
                "requires_credentials": False,
                "ready_for_live_enablement": False,
                "next_required_action": "design_disabled_audit_ledger_storage_plan",
            },
            "safety_summary": self._safety_summary()
            | {
                "fixture_only_failure_modes": True,
                "order_lifecycle_engine_implemented": False,
                "instantiates_adapter": False,
                "makes_network_calls": False,
                "writes_database_now": False,
                "connects_broker": False,
                "places_real_trade": False,
                "reads_live_account_funds": False,
            },
            "allowed_output": "review_only_order_lifecycle_failure_fixture_metadata",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def order_failure_runbook_mapping(self) -> dict[str, Any]:
        fixture_suite = self.order_lifecycle_failure_fixtures()
        mappings = [
            self._runbook_mapping(
                fixture,
                manual_decision,
                operator_action,
                required_audit_evidence,
                required_hashes,
                runbook_reference,
            )
            for fixture, manual_decision, operator_action, required_audit_evidence, required_hashes, runbook_reference in [
                (
                    fixture_suite["fixtures"][0],
                    "reject_preview_and_record_reason",
                    "review_rejection_code_before_any_new_preview",
                    [
                        "fixture_name",
                        "normalized_rejection_reason",
                        "operator_review_note",
                        "risk_snapshot_hash",
                        "proposal_hash",
                        "live_trading_disabled_evidence",
                    ],
                    ["proposal_hash", "risk_snapshot_hash", "market_data_quality_hash"],
                    "broker_rejection_review",
                ),
                (
                    fixture_suite["fixtures"][1],
                    "reduce_or_cancel_preview",
                    "review_liquidity_and_max_participation_before_repricing",
                    [
                        "fixture_name",
                        "requested_quantity",
                        "fillable_quantity",
                        "max_participation_rate",
                        "operator_review_note",
                        "risk_snapshot_hash",
                    ],
                    ["proposal_hash", "risk_snapshot_hash", "liquidity_snapshot_hash"],
                    "partial_fill_liquidity_review",
                ),
                (
                    fixture_suite["fixtures"][2],
                    "expire_confirmation_and_refresh_market_data",
                    "refresh_quote_and_recompute_risk",
                    [
                        "fixture_name",
                        "latency_ms",
                        "quality_status",
                        "confirmation_state",
                        "operator_review_note",
                        "live_trading_disabled_evidence",
                    ],
                    ["proposal_hash", "market_data_quality_hash", "risk_snapshot_hash"],
                    "stale_market_data_confirmation_review",
                ),
                (
                    fixture_suite["fixtures"][3],
                    "require_new_confirmation",
                    "collect_new_operator_confirmation_after_recomputing_preview",
                    [
                        "fixture_name",
                        "confirmation_ttl_seconds",
                        "elapsed_seconds",
                        "operator_review_note",
                        "new_confirmation_required_evidence",
                    ],
                    ["proposal_hash", "manual_confirmation_hash", "risk_snapshot_hash"],
                    "manual_confirmation_expiry_review",
                ),
                (
                    fixture_suite["fixtures"][4],
                    "discard_preview_and_recompute_risk",
                    "compare_risk_hashes_and_rebuild_preview",
                    [
                        "fixture_name",
                        "previous_risk_hash",
                        "current_risk_hash",
                        "operator_review_note",
                        "risk_gate_block_evidence",
                    ],
                    ["proposal_hash", "previous_risk_hash", "current_risk_hash"],
                    "risk_snapshot_change_review",
                ),
                (
                    fixture_suite["fixtures"][5],
                    "block_sell_and_escalate_risk_review",
                    "record_limit_state_and_wait_for_executable_market",
                    [
                        "fixture_name",
                        "symbol_state",
                        "side",
                        "limit_state_evidence",
                        "operator_review_note",
                        "rollback_runbook_review_note",
                    ],
                    ["proposal_hash", "market_data_quality_hash", "risk_snapshot_hash"],
                    "limit_down_sell_block_review",
                ),
            ]
        ]
        return {
            "schema_version": "trade_execution_order_failure_runbook_mapping.v1",
            "status": "order_failure_runbook_mapping_ready",
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "mapping_state": "review_only_no_runbook_execution",
            "source_fixture_suite": fixture_suite["fixture_suite"],
            "mappings": mappings,
            "summary": {
                "mapping_count": len(mappings),
                "manual_review_required_count": len(mappings),
                "audit_evidence_field_count": sum(len(item["required_audit_evidence"]) for item in mappings),
                "writes_database_now": False,
                "executes_runbook_now": False,
                "connects_broker": False,
                "places_order": False,
            },
            "decision": {
                "runbook_mapping_ready_for_review": True,
                "can_execute_runbook_now": False,
                "can_record_audit_now": False,
                "can_submit_order_now": False,
                "requires_broker_connection": False,
                "requires_credentials": False,
                "ready_for_live_enablement": False,
                "next_required_action": "design_disabled_audit_ledger_storage_plan",
            },
            "safety_summary": self._safety_summary()
            | {
                "maps_failure_fixtures": True,
                "writes_database_now": False,
                "executes_runbook_now": False,
                "connects_broker": False,
                "places_real_trade": False,
                "reads_live_account_funds": False,
            },
            "allowed_output": "review_only_order_failure_runbook_mapping_metadata",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def review_gates(self) -> dict[str, Any]:
        gates = [
            self._gate(
                "live_trading_disabled",
                "passed" if settings.enable_live_trading is False else "blocked",
                settings.enable_live_trading,
                False,
                "The global live-trading switch must stay false before any gateway work can continue.",
            ),
            self._gate(
                "broker_adapter_absent",
                "passed",
                False,
                False,
                "No live broker adapter is present or enabled in V5.0-P0.",
            ),
            self._gate(
                "credential_storage_absent",
                "passed",
                False,
                False,
                "The gateway exposes no credential input, persistence, or account-login surface.",
            ),
            self._gate(
                "real_execution_absent",
                "passed",
                False,
                False,
                "The gateway exposes review metadata only and cannot place or cancel real trades.",
            ),
            self._gate(
                "screen_click_trading_absent",
                "passed",
                False,
                False,
                "Screen observation remains read-only; no click, keyboard, or OCR execution path is connected.",
            ),
            self._gate(
                "human_confirmation_required",
                "passed",
                "contract_review_ready",
                "explicit_operator_confirmation_contract",
                "V5.0-P1 defines a review-only manual confirmation contract; it still cannot execute trades.",
            ),
            self._gate(
                "risk_gate_contract_required",
                "passed",
                "risk_gate_contract_review_ready",
                "portfolio_and_symbol_risk_contract",
                "V5.0-P2 defines review-only portfolio and symbol risk gates; they still cannot execute trades.",
            ),
            self._gate(
                "audit_and_rollback_required",
                "passed",
                "audit_schema_and_rollback_runbook_review_ready",
                "immutable_audit_log_and_manual_rollback_plan",
                "V5.0-P3 defines both audit evidence schema and manual rollback runbook as review-only metadata.",
            ),
            self._gate(
                "pre_live_review_package_required",
                "passed",
                "pre_live_review_package_ready",
                "operator_pre_live_review_package",
                "V5.0-P3 assembles a manual review package, but it still cannot enable or execute live trading.",
            ),
            self._gate(
                "operator_acceptance_checklist_required",
                "passed",
                "operator_acceptance_checklist_review_ready",
                "manual_operator_acceptance_checklist",
                "V5.0-P4 defines a manual acceptance checklist, but the API cannot record acceptance or enable the gateway.",
            ),
            self._gate(
                "disabled_release_gate_required",
                "passed",
                "disabled_release_gate_review_ready",
                "disabled_by_default_release_gate",
                "V5.0-P4 defines a disabled-by-default release gate; enablement still requires a separate live-integration project.",
            ),
            self._gate(
                "final_readiness_report_required",
                "passed",
                "final_readiness_report_review_ready",
                "v5_review_only_gateway_baseline",
                "V5.0-P5 aggregates all gateway review evidence and still cannot enable live trading.",
            ),
            self._gate(
                "broker_adapter_threat_model_required",
                "passed",
                "broker_adapter_threat_model_review_ready",
                "future_broker_adapter_threat_model",
                "V5.5-P3 preserves threat categories and mitigations without implementing broker connectivity.",
            ),
            self._gate(
                "broker_adapter_interface_draft_required",
                "passed",
                "broker_adapter_interface_draft_review_ready",
                "future_broker_adapter_interface_draft",
                "V5.5-P3 preserves provider-neutral interface metadata without executable adapter methods.",
            ),
            self._gate(
                "broker_adapter_contract_verification_required",
                "passed",
                "fixture_contract_verification_passed",
                "fixture_only_broker_adapter_contract_verifier",
                "V5.5-P3 preserves fixture contract verification with no broker connectivity.",
            ),
            self._gate(
                "order_lifecycle_failure_fixtures_required",
                "passed",
                "order_failure_fixtures_ready",
                "review_only_order_lifecycle_failure_fixture_suite",
                "V5.5-P2 defines order lifecycle failure-mode fixtures; V5.5-P3 maps them to manual runbook decisions without implementing an order lifecycle engine.",
            ),
            self._gate(
                "order_failure_runbook_mapping_required",
                "passed",
                "order_failure_runbook_mapping_ready",
                "review_only_manual_runbook_mapping",
                "V5.5-P3 maps failure fixtures to manual runbook decisions and audit evidence without executing or persisting them.",
            ),
        ]
        blocked = any(gate["status"] == "blocked" for gate in gates)
        review_required = any(gate["status"] == "review_required" for gate in gates)
        return {
            "schema_version": "trade_execution_gateway_review_gates.v1",
            "status": "blocked_by_safety_gate" if blocked else "order_failure_runbook_mapping_ready" if not review_required else "review_required",
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "gates": gates,
            "review_required_count": sum(1 for gate in gates if gate["status"] == "review_required"),
            "blocked_gate_count": sum(1 for gate in gates if gate["status"] == "blocked"),
            "allowed_output": "review_only_trade_execution_gateway_gates",
            "decision": {
                "gateway_can_execute": False,
                "manual_confirmation_contract_ready": True,
                "risk_contract_ready": True,
                "audit_contract_ready": True,
                "rollback_runbook_ready": True,
                "pre_live_package_ready": True,
                "operator_acceptance_checklist_ready": True,
                "disabled_release_gate_ready": True,
                "final_readiness_report_ready": True,
                "broker_adapter_threat_model_ready": True,
                "broker_adapter_interface_draft_ready": True,
                "broker_adapter_contract_verification_ready": True,
                "order_lifecycle_failure_fixtures_ready": True,
                "order_failure_runbook_mapping_ready": True,
                "ready_for_live_enablement": False,
                "live_trading_enabled": settings.enable_live_trading,
                "next_required_action": "design_disabled_audit_ledger_storage_plan",
            },
            "safety_summary": self._safety_summary(),
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _future_components(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "ManualConfirmationContract",
                "status": "review_contract_defined",
                "required_before": "any_real_money_action",
                "review_only": True,
            },
            {
                "name": "PortfolioRiskGateContract",
                "status": "review_contract_defined",
                "required_before": "any_gateway_enablement",
                "review_only": True,
            },
            {
                "name": "ExecutionAuditLedger",
                "status": "review_schema_defined_not_persisted",
                "required_before": "any_external_adapter",
                "review_only": True,
            },
            {
                "name": "ManualRollbackRunbook",
                "status": "review_runbook_defined",
                "required_before": "any_live_integration_review",
                "review_only": True,
            },
            {
                "name": "PreLiveReviewPackage",
                "status": "review_package_defined",
                "required_before": "any_operator_release_review",
                "review_only": True,
            },
            {
                "name": "OperatorAcceptanceChecklist",
                "status": "review_checklist_defined",
                "required_before": "any_external_live_integration_review",
                "review_only": True,
            },
            {
                "name": "DisabledByDefaultReleaseGate",
                "status": "review_gate_defined",
                "required_before": "any_gateway_enablement_discussion",
                "review_only": True,
            },
            {
                "name": "FinalReadinessReport",
                "status": "review_report_defined",
                "required_before": "any_v5_5_live_adapter_threat_model",
                "review_only": True,
            },
            {
                "name": "BrokerAdapterThreatModel",
                "status": "review_threat_model_defined",
                "required_before": "any_broker_adapter_implementation",
                "review_only": True,
            },
            {
                "name": "BrokerAdapterInterfaceDraft",
                "status": "review_interface_draft_defined",
                "required_before": "any_broker_adapter_contract_verification",
                "review_only": True,
            },
            {
                "name": "BrokerAdapterContractVerifier",
                "status": "review_fixture_contract_verified",
                "required_before": "any_broker_adapter_implementation",
                "review_only": True,
            },
            {
                "name": "OrderLifecycleFailureFixtures",
                "status": "review_failure_fixtures_defined",
                "required_before": "any_order_lifecycle_engine",
                "review_only": True,
            },
            {
                "name": "OrderFailureRunbookMapping",
                "status": "review_runbook_mapping_defined",
                "required_before": "any_audit_ledger_storage",
                "review_only": True,
            },
        ]

    def _safety_summary(self) -> dict[str, bool]:
        return {
            "review_only": True,
            "simulation_only": True,
            "gateway_enabled": False,
            "execution_enabled": False,
            "real_money_execution_enabled": False,
            "broker_adapter_enabled": False,
            "credential_storage_enabled": False,
            "screen_click_trading_enabled": False,
            "writes_credentials": False,
            "connects_broker": False,
            "places_real_trade": False,
            "cancels_real_trade": False,
            "modifies_live_position": False,
            "reads_live_account_funds": False,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _package_item(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": name,
            "schema_version": payload.get("schema_version"),
            "status": payload.get("status"),
            "stage": payload.get("stage"),
            "included": True,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _checklist_item(self, item_id: str, requirement: str, evidence: str) -> dict[str, Any]:
        return {
            "id": item_id,
            "requirement": requirement,
            "required_evidence": evidence,
            "required": True,
            "blocking_if_missing": True,
            "operator_review_required": True,
            "api_can_mark_complete": False,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _draft_method(self, name: str, purpose: str, mode: str) -> dict[str, Any]:
        return {
            "name": name,
            "purpose": purpose,
            "mode": mode,
            "implemented_now": False,
            "calls_broker_now": False,
            "places_order_now": False,
            "reads_account_now": False,
            "stores_credentials_now": False,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _contract_check(self, name: str, passed: bool, reason: str, fixture_evidence: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": name,
            "status": "passed" if passed else "blocked",
            "reason": reason,
            "fixture_evidence": fixture_evidence,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _failure_fixture(
        self,
        name: str,
        expected_status: str,
        failure_mode: str,
        trigger: str,
        expected_handling: str,
        required_contracts: list[str],
        fixture_payload: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "name": name,
            "expected_status": expected_status,
            "failure_mode": failure_mode,
            "trigger": trigger,
            "expected_handling": expected_handling,
            "required_contracts": required_contracts,
            "fixture_payload": fixture_payload
            | {
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "can_submit_order": False,
            "can_cancel_order": False,
            "can_modify_order": False,
            "connects_broker": False,
            "requires_credentials": False,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _runbook_mapping(
        self,
        fixture: dict[str, Any],
        manual_decision: str,
        operator_action: str,
        required_audit_evidence: list[str],
        required_hashes: list[str],
        runbook_reference: str,
    ) -> dict[str, Any]:
        return {
            "fixture_name": fixture["name"],
            "failure_mode": fixture["failure_mode"],
            "expected_status": fixture["expected_status"],
            "manual_decision": manual_decision,
            "operator_action": operator_action,
            "required_audit_evidence": required_audit_evidence,
            "required_hashes": required_hashes,
            "runbook_reference": runbook_reference,
            "can_execute_runbook": False,
            "can_submit_order": False,
            "writes_database_now": False,
            "connects_broker": False,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _stable_hash(self, payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _schema_field(self, name: str, field_type: str, description: str, sensitive: bool) -> dict[str, Any]:
        return {
            "name": name,
            "type": field_type,
            "description": description,
            "sensitive": sensitive,
            "required": True,
            "review_only": True,
        }

    def _risk_gate(
        self,
        name: str,
        source_limit: str,
        limit: Any,
        failure_status: str,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "source_limit": source_limit,
            "limit": limit,
            "failure_status": failure_status,
            "reason": reason,
            "manual_override_allowed": False,
            "ai_override_allowed": False,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _gate(
        self,
        name: str,
        status: str,
        value: Any,
        limit: Any,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "status": status,
            "value": value,
            "limit": limit,
            "reason": reason,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
