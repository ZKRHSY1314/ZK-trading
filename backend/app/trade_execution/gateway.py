from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any

from app.config import settings
from app.risk.portfolio import DEFAULT_LIMITS
from app.storage.sqlite_store import SQLiteStore


class TradeExecutionGatewayService:
    """V5.0 starts as a review-only safety boundary, not an executor."""

    stage = "V5.5-P24"

    def __init__(self) -> None:
        self.store = SQLiteStore(settings.database_path)

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
                "disabled_audit_ledger_storage_plan_review",
                "audit_ledger_migration_spec_dry_run_review",
                "audit_ledger_migration_spec_approval_metadata_review",
                "audit_ledger_migration_release_readiness_review",
                "audit_ledger_migration_approval_freshness_review",
                "audit_ledger_migration_manual_release_package_review",
                "audit_ledger_migration_release_package_integrity_review",
                "audit_ledger_migration_manual_release_review_rehearsal",
                "audit_ledger_migration_manual_release_evidence_verification",
                "audit_ledger_migration_manual_release_evidence_comparison",
                "audit_ledger_migration_manual_release_health_digest",
                "audit_ledger_migration_manual_release_health_digest_history_retention_proposal",
                "audit_ledger_migration_manual_release_health_digest_history_migration_readiness_checklist",
                "audit_ledger_migration_manual_release_health_digest_history_migration_spec_verifier",
                "audit_ledger_migration_manual_release_health_digest_history_migration_spec_approval_metadata",
                "audit_ledger_migration_manual_release_health_digest_history_release_readiness_review",
                "audit_ledger_migration_manual_release_health_digest_history_approval_freshness_review",
                "audit_ledger_migration_manual_release_health_digest_history_release_package_review",
                "audit_ledger_migration_manual_release_health_digest_history_release_package_integrity_review",
                "audit_ledger_migration_manual_release_health_digest_history_release_rehearsal",
                "audit_ledger_migration_manual_release_health_digest_history_release_evidence_verification",
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
                "create_audit_ledger_table",
                "write_audit_ledger_row",
                "run_audit_ledger_migration",
                "execute_sql",
                "write_migration_file",
                "approve_migration_as_execution",
                "approve_release_from_summary",
                "reuse_expired_approval_as_current",
                "write_release_package_file",
                "approve_release_from_integrity_review",
                "record_manual_release_review_by_api",
                "persist_manual_release_evidence",
                "persist_manual_release_evidence_comparison",
                "persist_manual_release_health_digest",
                "persist_manual_release_health_digest_history",
                "create_manual_release_health_digest_history_table",
                "run_manual_release_health_digest_history_migration",
                "write_manual_release_health_digest_history_migration_file",
                "execute_manual_release_health_digest_history_migration_spec",
                "approve_manual_release_health_digest_history_migration_as_execution",
                "approve_manual_release_health_digest_history_release_from_readiness",
                "reuse_expired_manual_release_health_digest_history_approval_as_current",
                "treat_manual_release_health_digest_history_package_as_release_approval",
                "approve_manual_release_health_digest_history_release_from_integrity_review",
                "record_manual_release_health_digest_history_review_by_api",
                "persist_manual_release_health_digest_history_evidence",
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
            "operator_attestation_phrase": "I confirm this is a pre-release manual acceptance checklist, not live-trading enablement.",
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
                "next_required_action": "review_audit_ledger_migration_manual_release_package",
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
                "mitigation": "No credential fields, no persistence, no environment writes, and no adapter instantiation in V5.5-P13.",
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
                "next_required_action": "review_audit_ledger_migration_manual_release_package",
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
                "next_required_action": "review_audit_ledger_migration_manual_release_package",
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
                "next_required_action": "review_audit_ledger_migration_manual_release_package",
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
                "next_required_action": "review_audit_ledger_migration_manual_release_package",
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
                "next_required_action": "review_audit_ledger_migration_manual_release_package",
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

    def audit_ledger_storage_plan(self) -> dict[str, Any]:
        audit_schema = self.audit_evidence_schema()
        runbook_mapping = self.order_failure_runbook_mapping()
        planned_columns = [
            self._storage_column("audit_id", "TEXT", False, "primary key generated by future audit ledger writer", "audit_evidence_schema"),
            self._storage_column("created_at", "TEXT", False, "ISO timestamp from future append-only event writer", "audit_evidence_schema"),
            self._storage_column("event_type", "TEXT", False, "allowed audit event type", "audit_evidence_schema"),
            self._storage_column("proposal_hash", "TEXT", False, "hash of reviewed proposal, never raw proposal body", "audit_evidence_schema"),
            self._storage_column("failure_fixture_name", "TEXT", True, "optional source failure fixture for blocked order lifecycle reviews", "order_failure_runbook_mapping"),
            self._storage_column("manual_decision", "TEXT", True, "manual decision label from runbook mapping", "order_failure_runbook_mapping"),
            self._storage_column("runbook_reference", "TEXT", True, "manual runbook reference, not an executable command", "order_failure_runbook_mapping"),
            self._storage_column("operator_id_hash", "TEXT", True, "hashed reviewer id only", "manual_confirmation_contract"),
            self._storage_column("risk_snapshot_hash", "TEXT", True, "hash of portfolio/symbol risk evidence", "risk_gate_contract"),
            self._storage_column("market_data_quality_hash", "TEXT", True, "hash of quote quality and latency evidence", "risk_gate_contract"),
            self._storage_column("safety_flags_json", "TEXT", False, "canonical JSON containing review_only/simulation_only/live_trading_enabled=false", "gateway_safety_summary"),
            self._storage_column("evidence_payload_hash", "TEXT", False, "hash of canonical redacted evidence payload", "audit_evidence_schema"),
            self._storage_column("previous_event_hash", "TEXT", True, "previous row event hash for future append-only chain verification", "audit_evidence_schema"),
            self._storage_column("event_hash", "TEXT", False, "current row hash over canonical payload and previous_event_hash", "audit_evidence_schema"),
            self._storage_column("review_note_excerpt", "TEXT", True, "short non-secret operator note excerpt", "operator_review"),
        ]
        proposed_indexes = [
            {"name": "idx_trade_execution_audit_ledger_created_at", "columns": ["created_at"], "unique": False, "create_now": False},
            {"name": "idx_trade_execution_audit_ledger_event_type", "columns": ["event_type"], "unique": False, "create_now": False},
            {"name": "idx_trade_execution_audit_ledger_proposal_hash", "columns": ["proposal_hash"], "unique": False, "create_now": False},
            {"name": "idx_trade_execution_audit_ledger_event_hash", "columns": ["event_hash"], "unique": True, "create_now": False},
        ]
        return {
            "schema_version": "trade_execution_audit_ledger_storage_plan.v1",
            "status": "disabled_audit_ledger_storage_plan_ready",
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "storage_state": "disabled_not_persisted",
            "target_future_table": audit_schema["target_future_table"],
            "source_schema": audit_schema["schema_version"],
            "source_runbook_mapping": runbook_mapping["schema_version"],
            "planned_columns": planned_columns,
            "proposed_indexes": proposed_indexes,
            "hash_chain_policy": {
                "algorithm": "sha256",
                "canonicalization": "canonical_json_sort_keys_utf8",
                "previous_event_hash_required_after_first_row": True,
                "manual_correction_policy": "append_correction_event_never_update_or_delete",
                "verify_before_any_future_live_review": True,
            },
            "retention_policy": {
                "default_retention_days": 365,
                "manual_archive_required_before_prune": True,
                "prune_requires_operator_approval": True,
                "prune_api_enabled_now": False,
            },
            "redaction_policy": {
                "store_only_hashes_for_sensitive_identity": True,
                "store_short_review_note_excerpt_only": True,
                "excluded_sensitive_fields": audit_schema["excluded_sensitive_fields"],
                "raw_payload_storage_allowed": False,
            },
            "migration_preconditions": [
                "dry_run_migration_spec_verifier_passed",
                "operator_approval_for_schema_change_recorded",
                "backup_and_restore_drill_reviewed",
                "rollback_plan_reviewed",
                "forbidden_sensitive_fields_scan_passed",
                "health_live_trading_enabled_false",
            ],
            "rollback_requirements": [
                "migration_must_be_reversible_before_execution",
                "restore_from_backup_drill_required",
                "hash_chain_verifier_must_pass_after_restore",
                "operator_postmortem_required_for_failed_migration",
            ],
            "blocked_actions": [
                "create_table",
                "alter_table",
                "write_audit_row",
                "run_migration",
                "write_migration_file",
                "connect_broker",
                "submit_order",
                "store_credentials",
            ],
            "summary": {
                "planned_column_count": len(planned_columns),
                "proposed_index_count": len(proposed_indexes),
                "excluded_sensitive_field_count": len(audit_schema["excluded_sensitive_fields"]),
                "create_table_now": False,
                "writes_database_now": False,
                "runs_migration_now": False,
                "writes_migration_file_now": False,
                "records_audit_rows_now": False,
            },
            "decision": {
                "storage_plan_ready_for_review": True,
                "can_create_table_now": False,
                "can_write_audit_row_now": False,
                "can_run_migration_now": False,
                "can_write_migration_file_now": False,
                "requires_operator_approval_before_migration": True,
                "requires_dry_run_verifier_before_migration": True,
                "ready_for_live_enablement": False,
                "next_required_action": "review_audit_ledger_migration_manual_release_package",
            },
            "safety_summary": self._safety_summary()
            | {
                "storage_plan_only": True,
                "create_table_now": False,
                "writes_database_now": False,
                "runs_migration_now": False,
                "writes_migration_file_now": False,
                "records_audit_rows_now": False,
                "connects_broker": False,
                "places_real_trade": False,
            },
            "allowed_output": "review_only_disabled_audit_ledger_storage_plan",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def verify_audit_ledger_migration_spec(self, spec_text: str | None = None) -> dict[str, Any]:
        storage_plan = self.audit_ledger_storage_plan()
        target_table = storage_plan["target_future_table"]
        required_columns = [str(item["name"]) for item in storage_plan["planned_columns"]]
        proposed_indexes = [str(item["name"]) for item in storage_plan["proposed_indexes"]]
        spec = spec_text if spec_text is not None else self._default_audit_ledger_migration_spec(storage_plan)
        normalized = " ".join(spec.lower().split())
        dangerous_terms = [
            " drop ",
            " delete ",
            " insert ",
            " update ",
            " alter ",
            " pragma ",
            " attach ",
            " detach ",
            " vacuum ",
            " replace ",
            " truncate ",
            " execute ",
        ]
        sensitive_terms = [
            *storage_plan["redaction_policy"]["excluded_sensitive_fields"],
            "broker_credentials",
            "trading_password",
            "plaintext_secret",
            "account_funds",
            "live_positions",
            "sms_code",
        ]
        missing_columns = [column for column in required_columns if column.lower() not in normalized]
        missing_indexes = [index for index in proposed_indexes if index.lower() not in normalized]
        dangerous_matches = [term.strip() for term in dangerous_terms if term in f" {normalized} "]
        sensitive_matches = [term for term in sensitive_terms if term.lower() in normalized]
        checks = [
            self._migration_spec_check(
                "spec_text_present",
                bool(spec.strip()),
                "migration spec text must be provided or generated from the disabled safe default",
            ),
            self._migration_spec_check(
                "target_table_named",
                target_table.lower() in normalized,
                "spec must name the future audit ledger target table",
            ),
            self._migration_spec_check(
                "create_table_shape_present",
                "create table" in normalized and "if not exists" in normalized,
                "dry-run spec may describe guarded CREATE TABLE shape but must not execute it",
            ),
            self._migration_spec_check(
                "required_columns_covered",
                not missing_columns,
                "spec must cover every disabled storage-plan column",
                {"missing_columns": missing_columns},
            ),
            self._migration_spec_check(
                "proposed_indexes_covered",
                not missing_indexes,
                "spec should cover every disabled storage-plan index",
                {"missing_indexes": missing_indexes},
            ),
            self._migration_spec_check(
                "hash_chain_columns_present",
                {"previous_event_hash", "event_hash"} <= set(required_columns)
                and "previous_event_hash" in normalized
                and "event_hash" in normalized,
                "spec must preserve previous/current event hash chain columns",
            ),
            self._migration_spec_check(
                "safety_flags_column_present",
                "safety_flags_json" in normalized,
                "spec must preserve review_only/simulation_only/live_trading_enabled=false evidence",
            ),
            self._migration_spec_check(
                "sensitive_fields_absent",
                not sensitive_matches,
                "spec must not include broker credentials, trading PINs, SMS codes, account numbers, raw secrets, funds, or positions",
                {"sensitive_matches": sensitive_matches},
            ),
            self._migration_spec_check(
                "dangerous_sql_absent",
                not dangerous_matches,
                "dry-run verifier rejects destructive, mutating, attachment, pragma, or execution SQL terms",
                {"dangerous_matches": dangerous_matches},
            ),
            self._migration_spec_check(
                "storage_plan_disabled",
                storage_plan["decision"]["can_create_table_now"] is False
                and storage_plan["decision"]["can_run_migration_now"] is False
                and storage_plan["summary"]["writes_database_now"] is False,
                "verification must not change disabled storage-plan posture",
            ),
            self._migration_spec_check(
                "operator_approval_required",
                storage_plan["decision"]["requires_operator_approval_before_migration"] is True,
                "future migration still requires operator approval",
            ),
            self._migration_spec_check(
                "live_trading_disabled",
                not settings.enable_live_trading and storage_plan["live_trading_enabled"] is False,
                "migration spec verification must preserve disabled live-trading state",
            ),
        ]
        failed = [item for item in checks if item["status"] != "passed"]
        return {
            "schema_version": "trade_execution_audit_ledger_migration_spec_verifier.v1",
            "status": "spec_verification_passed" if not failed else "spec_verification_failed",
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "verification_state": "dry_run_in_memory_only",
            "target_table": target_table,
            "spec_hash": hashlib.sha256(spec.encode("utf-8")).hexdigest(),
            "spec_excerpt": spec[:800],
            "checks": checks,
            "missing_columns": missing_columns,
            "missing_indexes": missing_indexes,
            "dangerous_matches": dangerous_matches,
            "sensitive_matches": sensitive_matches,
            "failed_count": len(failed),
            "migration_allowed_now": False,
            "forbidden_actions": [
                "execute_sql",
                "create_table",
                "alter_table",
                "run_migration",
                "write_migration_file",
                "write_audit_row",
                "connect_broker",
                "submit_order",
                "store_credentials",
            ],
            "summary": {
                "required_column_count": len(required_columns),
                "covered_column_count": len(required_columns) - len(missing_columns),
                "proposed_index_count": len(proposed_indexes),
                "covered_index_count": len(proposed_indexes) - len(missing_indexes),
                "dangerous_match_count": len(dangerous_matches),
                "sensitive_match_count": len(sensitive_matches),
                "executes_sql": False,
                "creates_table_now": False,
                "writes_database_now": False,
                "runs_migration_now": False,
                "writes_migration_file_now": False,
                "records_audit_rows_now": False,
            },
            "decision": {
                "spec_verification_ready_for_review": True,
                "spec_verification_passed": not failed,
                "can_execute_sql_now": False,
                "can_create_table_now": False,
                "can_run_migration_now": False,
                "can_write_migration_file_now": False,
                "can_write_audit_row_now": False,
                "requires_operator_approval_before_migration": True,
                "ready_for_live_enablement": False,
                "next_required_action": "review_audit_ledger_migration_manual_release_package",
            },
            "safety_summary": self._safety_summary()
            | {
                "dry_run_verifier_only": True,
                "executes_sql": False,
                "creates_table_now": False,
                "writes_database_now": False,
                "runs_migration_now": False,
                "writes_migration_file_now": False,
                "records_audit_rows_now": False,
                "connects_broker": False,
                "places_real_trade": False,
            },
            "allowed_output": "review_only_audit_ledger_migration_spec_verifier",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def approve_audit_ledger_migration_spec(
        self,
        spec_text: str | None = None,
        approved_by: str = "operator",
        note: str | None = None,
    ) -> dict[str, Any]:
        verification = self.verify_audit_ledger_migration_spec(spec_text=spec_text)
        verification_passed = verification.get("status") == "spec_verification_passed"
        now = datetime.now().isoformat(timespec="seconds")
        approval = {
            "schema_version": "trade_execution_audit_ledger_migration_spec_approval.v1",
            "status": "approval_metadata_recorded" if verification_passed else "approval_blocked",
            "stage": self.stage,
            "approved_at": now,
            "approved_by": (approved_by or "operator")[:80],
            "approval_note": note,
            "approval_effect": "existing_event_metadata_only",
            "spec_hash": verification.get("spec_hash"),
            "verification_status": verification.get("status"),
            "verification_failed_count": verification.get("failed_count", 0),
            "target_table": verification.get("target_table"),
            "migration_allowed_now": False,
            "future_migration_still_requires": [
                "reviewed_sqlite_migration_file",
                "operator_release_approval",
                "rollback_plan",
                "migration_unit_tests",
                "api_smoke_tests",
                "hash_chain_verifier_after_restore",
                "forbidden_tracked_file_scan",
                "separate_live_integration_review",
            ],
            "safety_summary": self._safety_summary()
            | {
                "writes_existing_event_now": verification_passed,
                "writes_audit_ledger_row_now": False,
                "creates_table_now": False,
                "runs_migration_now": False,
                "executes_sql": False,
                "writes_migration_file_now": False,
                "connects_broker": False,
                "places_real_trade": False,
                "stores_credentials": False,
            },
            "allowed_output": "review_only_audit_ledger_migration_spec_approval_metadata",
            "forbidden_actions": [
                "execute_sql",
                "run_migration_now",
                "create_table_now",
                "write_migration_file_now",
                "write_audit_ledger_row_now",
                "approve_release_now",
                "enable_gateway_now",
                "connect_broker",
                "submit_order",
                "store_credentials",
                "screen_click",
                "keyboard_type",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
        if not verification_passed:
            approval["event_id"] = None
            approval["verification"] = verification
            return approval

        payload = dict(approval)
        payload["verification"] = {
            "schema_version": verification.get("schema_version"),
            "status": verification.get("status"),
            "spec_hash": verification.get("spec_hash"),
            "failed_count": verification.get("failed_count"),
            "target_table": verification.get("target_table"),
            "allowed_output": verification.get("allowed_output"),
            "migration_allowed_now": verification.get("migration_allowed_now"),
            "live_trading_enabled": verification.get("live_trading_enabled"),
        }
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO events(event_type, payload_json)
                VALUES (?, ?)
                """,
                (
                    "trade_audit_ledger_migration_spec_approval",
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            event_id = int(cursor.lastrowid or 0)
        approval["event_id"] = event_id
        approval["verification"] = payload["verification"]
        return approval

    def list_audit_ledger_migration_spec_approvals(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            ("trade_audit_ledger_migration_spec_approval", max(1, min(limit, 200))),
        )
        approvals: list[dict[str, Any]] = []
        for row in rows:
            payload = self._decode_json(row.get("payload_json") or "{}")
            item = payload if isinstance(payload, dict) else {}
            item["event_id"] = row.get("id")
            item["event_type"] = row.get("event_type")
            item["created_at"] = row.get("created_at")
            item["review_only"] = True
            item["simulation_only"] = True
            item["live_trading_enabled"] = settings.enable_live_trading
            approvals.append(item)
        return approvals

    def audit_ledger_migration_release_readiness(self, limit: int = 50) -> dict[str, Any]:
        storage_plan = self.audit_ledger_storage_plan()
        verification = self.verify_audit_ledger_migration_spec()
        approvals = self.list_audit_ledger_migration_spec_approvals(limit=limit)
        latest_approval = approvals[0] if approvals else None
        storage_ready = storage_plan.get("status") == "disabled_audit_ledger_storage_plan_ready"
        verification_ready = verification.get("status") == "spec_verification_passed"
        approval_ready = (
            bool(latest_approval)
            and latest_approval.get("status") == "approval_metadata_recorded"
            and latest_approval.get("verification_status") == "spec_verification_passed"
        )
        approval_matches_spec = bool(latest_approval) and latest_approval.get("spec_hash") == verification.get("spec_hash")
        no_execution_enabled = (
            storage_plan.get("decision", {}).get("can_run_migration_now") is False
            and verification.get("migration_allowed_now") is False
            and (latest_approval or {}).get("migration_allowed_now", False) is False
        )
        safety_ready = (
            storage_plan.get("summary", {}).get("writes_database_now") is False
            and verification.get("summary", {}).get("executes_sql") is False
            and verification.get("summary", {}).get("writes_migration_file_now") is False
            and (latest_approval or {}).get("safety_summary", {}).get("writes_audit_ledger_row_now", False) is False
            and (latest_approval or {}).get("safety_summary", {}).get("runs_migration_now", False) is False
            and (latest_approval or {}).get("safety_summary", {}).get("executes_sql", False) is False
            and not settings.enable_live_trading
        )
        gates = [
            self._release_readiness_gate(
                "storage_plan_ready",
                storage_ready,
                "V5.5-P4 disabled audit ledger storage plan must be ready for review.",
            ),
            self._release_readiness_gate(
                "migration_spec_verified",
                verification_ready,
                "V5.5-P5 dry-run migration spec verifier must pass.",
            ),
            self._release_readiness_gate(
                "operator_approval_metadata_recorded",
                approval_ready,
                "V5.5-P6 operator approval metadata is required before manual release review.",
                status_if_false="review_required",
            ),
            self._release_readiness_gate(
                "latest_approval_matches_current_spec",
                approval_matches_spec,
                "latest approval metadata must match the currently verified migration spec hash.",
                status_if_false="review_required",
            ),
            self._release_readiness_gate(
                "no_migration_execution_enabled",
                no_execution_enabled,
                "release readiness summary must not enable SQL, migrations, audit-ledger writes, or release approval.",
            ),
            self._release_readiness_gate(
                "safety_summary_clean",
                safety_ready,
                "release readiness summary must preserve no SQL execution, no migration file, no audit ledger rows, no broker access, and disabled live trading.",
            ),
        ]
        blocked = [gate for gate in gates if gate["status"] == "blocked"]
        review_required = [gate for gate in gates if gate["status"] == "review_required"]
        if blocked:
            status = "release_blocked"
        elif review_required:
            status = "release_review_required"
        else:
            status = "release_evidence_ready"
        return {
            "schema_version": "trade_execution_audit_ledger_migration_release_readiness.v1",
            "status": status,
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "decision": {
                "go_no_go": "go_for_manual_release_review" if status == "release_evidence_ready" else "no_go",
                "migration_allowed_now": False,
                "release_approved_now": False,
                "requires_human_release_approval": True,
                "reason": "all evidence gates passed" if status == "release_evidence_ready" else "release evidence is incomplete or requires review",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "evidence": {
                "storage_plan_status": storage_plan.get("status"),
                "verification_status": verification.get("status"),
                "verification_failed_count": verification.get("failed_count"),
                "approval_count": len(approvals),
                "latest_approval_status": latest_approval.get("status") if latest_approval else None,
                "latest_approval_event_id": latest_approval.get("event_id") if latest_approval else None,
                "target_table": verification.get("target_table"),
                "spec_hash": verification.get("spec_hash"),
                "approved_spec_hash": latest_approval.get("spec_hash") if latest_approval else None,
                "allowed_output": "review_only_audit_ledger_migration_release_readiness",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "gates": gates,
            "blocked_gates": blocked,
            "review_required_gates": review_required,
            "required_before_actual_migration": [
                "separate_reviewed_sqlite_migration_file",
                "explicit_operator_release_approval",
                "database_backup_and_restore_drill",
                "rollback_plan_review",
                "migration_unit_tests",
                "api_smoke_tests",
                "hash_chain_verifier_after_restore",
                "forbidden_tracked_file_scan",
                "separate_live_integration_review",
            ],
            "safety_summary": self._safety_summary()
            | {
                "executes_sql": False,
                "runs_migration_now": False,
                "creates_table_now": False,
                "writes_database_now": False,
                "writes_audit_ledger_row_now": False,
                "writes_migration_file_now": False,
                "approves_release_now": False,
                "enables_gateway_now": False,
                "connects_broker": False,
                "places_real_trade": False,
                "stores_credentials": False,
            },
            "allowed_output": "review_only_audit_ledger_migration_release_readiness",
            "forbidden_actions": [
                "execute_sql",
                "run_migration_now",
                "create_table_now",
                "write_migration_file_now",
                "write_audit_ledger_row_now",
                "approve_release_now",
                "enable_gateway_now",
                "connect_broker",
                "submit_order",
                "store_credentials",
                "screen_click",
                "keyboard_type",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def audit_ledger_migration_approval_review(
        self,
        limit: int = 50,
        max_age_days: int = 7,
    ) -> dict[str, Any]:
        safe_max_age_days = max(1, min(max_age_days, 365))
        release = self.audit_ledger_migration_release_readiness(limit=limit)
        verification = self.verify_audit_ledger_migration_spec()
        approvals = self.list_audit_ledger_migration_spec_approvals(limit=limit)
        latest_approval = approvals[0] if approvals else None
        now = datetime.now()
        approval_time = self._parse_datetime(
            latest_approval.get("approved_at") or latest_approval.get("created_at") if latest_approval else None
        )
        approval_age_hours = round((now - approval_time).total_seconds() / 3600, 3) if approval_time else None
        approval_age_days = round(float(approval_age_hours or 0) / 24, 3) if approval_age_hours is not None else None
        expires_at = (
            (approval_time + timedelta(days=safe_max_age_days)).isoformat(timespec="seconds")
            if approval_time
            else None
        )
        current_spec_hash = verification.get("spec_hash")
        approved_spec_hash = latest_approval.get("spec_hash") if latest_approval else None
        approval_recorded = bool(latest_approval)
        approval_not_expired = bool(approval_time) and approval_age_days is not None and approval_age_days <= safe_max_age_days
        spec_hash_matches = bool(latest_approval) and approved_spec_hash == current_spec_hash
        release_ready = release.get("status") == "release_evidence_ready"
        gates = [
            self._release_readiness_gate(
                "approval_recorded",
                approval_recorded,
                "latest operator approval metadata must exist before migration release review.",
                status_if_false="review_required",
            ),
            self._release_readiness_gate(
                "approval_within_validity_window",
                approval_not_expired,
                f"approval metadata must be newer than {safe_max_age_days} day(s).",
                status_if_false="review_required",
            ),
            self._release_readiness_gate(
                "approval_matches_current_spec",
                spec_hash_matches,
                "latest approval spec hash must match the currently verified migration spec hash.",
                status_if_false="review_required",
            ),
            self._release_readiness_gate(
                "release_readiness_evidence_ready",
                release_ready,
                "V5.5-P7 release readiness must be evidence-ready before approval can be treated as current.",
                status_if_false="review_required",
            ),
            self._release_readiness_gate(
                "no_migration_execution_enabled",
                release.get("decision", {}).get("migration_allowed_now") is False
                and verification.get("migration_allowed_now") is False
                and (latest_approval or {}).get("migration_allowed_now", False) is False,
                "approval review must not enable migration execution.",
            ),
            self._release_readiness_gate(
                "live_trading_disabled",
                not settings.enable_live_trading
                and release.get("live_trading_enabled") is False
                and verification.get("live_trading_enabled") is False,
                "live trading must remain disabled.",
            ),
        ]
        blocked = [gate for gate in gates if gate["status"] == "blocked"]
        review_required = [gate for gate in gates if gate["status"] == "review_required"]
        if blocked:
            status = "approval_review_blocked"
        elif not approval_recorded:
            status = "approval_review_required"
        elif review_required:
            status = "approval_rotation_required"
        else:
            status = "approval_current"
        next_required_action = "none"
        if status == "approval_review_required":
            next_required_action = "record_operator_approval_metadata"
        elif status == "approval_rotation_required":
            next_required_action = "refresh_operator_approval_metadata"
        elif status == "approval_review_blocked":
            next_required_action = "resolve_blocked_release_evidence"
        return {
            "schema_version": "trade_execution_audit_ledger_migration_approval_review.v1",
            "status": status,
            "stage": self.stage,
            "generated_at": now.isoformat(timespec="seconds"),
            "review_policy": {
                "max_age_days": safe_max_age_days,
                "rotation_required_when": [
                    "approval_missing",
                    "approval_expired",
                    "spec_hash_changed",
                    "release_readiness_not_ready",
                ],
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "latest_approval": {
                "event_id": latest_approval.get("event_id") if latest_approval else None,
                "status": latest_approval.get("status") if latest_approval else None,
                "approved_at": latest_approval.get("approved_at") if latest_approval else None,
                "created_at": latest_approval.get("created_at") if latest_approval else None,
                "approved_by": latest_approval.get("approved_by") if latest_approval else None,
                "spec_hash": approved_spec_hash,
                "verification_status": latest_approval.get("verification_status") if latest_approval else None,
                "approval_age_hours": approval_age_hours,
                "approval_age_days": approval_age_days,
                "expires_at": expires_at,
                "is_expired": False if approval_not_expired else bool(latest_approval),
                "matches_current_spec": spec_hash_matches,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "current_spec": {
                "spec_hash": current_spec_hash,
                "verification_status": verification.get("status"),
                "failed_count": verification.get("failed_count"),
                "migration_allowed_now": False,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "release_readiness": {
                "status": release.get("status"),
                "go_no_go": release.get("decision", {}).get("go_no_go"),
                "approval_count": release.get("evidence", {}).get("approval_count"),
                "latest_approval_event_id": release.get("evidence", {}).get("latest_approval_event_id"),
                "migration_allowed_now": False,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "gates": gates,
            "blocked_gates": blocked,
            "review_required_gates": review_required,
            "decision": {
                "next_required_action": next_required_action,
                "migration_allowed_now": False,
                "approval_can_be_reused_for_manual_release_review": status == "approval_current",
                "requires_human_release_approval": True,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "safety_summary": self._safety_summary()
            | {
                "executes_sql": False,
                "runs_migration_now": False,
                "creates_table_now": False,
                "writes_database_now": False,
                "writes_audit_ledger_row_now": False,
                "writes_migration_file_now": False,
                "approves_release_now": False,
                "enables_gateway_now": False,
                "connects_broker": False,
                "places_real_trade": False,
                "stores_credentials": False,
            },
            "allowed_output": "review_only_audit_ledger_migration_approval_review",
            "forbidden_actions": [
                "execute_sql",
                "run_migration_now",
                "create_table_now",
                "write_migration_file_now",
                "write_audit_ledger_row_now",
                "approve_release_now",
                "enable_gateway_now",
                "reuse_expired_approval_as_current",
                "connect_broker",
                "submit_order",
                "store_credentials",
                "screen_click",
                "keyboard_type",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def audit_ledger_migration_release_package(
        self,
        limit: int = 50,
        max_age_days: int = 7,
    ) -> dict[str, Any]:
        storage_plan = self.audit_ledger_storage_plan()
        verification = self.verify_audit_ledger_migration_spec()
        approvals = self.list_audit_ledger_migration_spec_approvals(limit=limit)
        latest_approval = approvals[0] if approvals else None
        release = self.audit_ledger_migration_release_readiness(limit=limit)
        approval_review = self.audit_ledger_migration_approval_review(
            limit=limit,
            max_age_days=max_age_days,
        )
        manifest_items = [
            self._release_package_item(
                "P4_disabled_audit_ledger_storage_plan",
                storage_plan.get("status"),
                storage_plan.get("allowed_output"),
                storage_plan.get("generated_at"),
                storage_plan.get("summary", {}).get("writes_database_now") is False
                and storage_plan.get("summary", {}).get("runs_migration_now") is False,
            ),
            self._release_package_item(
                "P5_migration_spec_verifier",
                verification.get("status"),
                verification.get("allowed_output"),
                verification.get("generated_at"),
                verification.get("status") == "spec_verification_passed"
                and verification.get("failed_count") == 0
                and verification.get("summary", {}).get("executes_sql") is False,
            ),
            self._release_package_item(
                "P6_approval_metadata",
                latest_approval.get("status") if latest_approval else "missing",
                latest_approval.get("allowed_output") if latest_approval else "missing",
                latest_approval.get("approved_at") if latest_approval else None,
                bool(latest_approval)
                and latest_approval.get("verification_status") == "spec_verification_passed"
                and latest_approval.get("migration_allowed_now") is False,
            ),
            self._release_package_item(
                "P7_release_readiness",
                release.get("status"),
                release.get("allowed_output"),
                release.get("generated_at"),
                release.get("status") == "release_evidence_ready"
                and release.get("decision", {}).get("migration_allowed_now") is False,
            ),
            self._release_package_item(
                "P8_approval_freshness",
                approval_review.get("status"),
                approval_review.get("allowed_output"),
                approval_review.get("generated_at"),
                approval_review.get("status") == "approval_current"
                and approval_review.get("decision", {}).get("migration_allowed_now") is False,
            ),
        ]
        safe_max_age_days = max(1, min(max_age_days, 365))
        package_id_inputs = {
            "storage_plan_status": storage_plan.get("status"),
            "verification_status": verification.get("status"),
            "spec_hash": verification.get("spec_hash"),
            "latest_approval_event_id": latest_approval.get("event_id") if latest_approval else None,
            "latest_approval_spec_hash": latest_approval.get("spec_hash") if latest_approval else None,
            "release_status": release.get("status"),
            "approval_review_status": approval_review.get("status"),
            "max_age_days": safe_max_age_days,
        }
        package_id = self._stable_hash(package_id_inputs)
        gates = [
            self._release_readiness_gate(
                "storage_plan_ready",
                storage_plan.get("status") == "disabled_audit_ledger_storage_plan_ready",
                "V5.5-P4 disabled audit ledger storage plan must be ready.",
                status_if_false="review_required",
            ),
            self._release_readiness_gate(
                "spec_verifier_passed",
                verification.get("status") == "spec_verification_passed" and verification.get("failed_count") == 0,
                "V5.5-P5 dry-run verifier must pass without failed checks.",
                status_if_false="review_required",
            ),
            self._release_readiness_gate(
                "approval_current",
                approval_review.get("status") == "approval_current",
                "V5.5-P8 approval freshness review must be current.",
                status_if_false="review_required",
            ),
            self._release_readiness_gate(
                "release_readiness_ready",
                release.get("status") == "release_evidence_ready",
                "V5.5-P7 release readiness must be evidence-ready.",
                status_if_false="review_required",
            ),
            self._release_readiness_gate(
                "no_execution_or_persistence_enabled",
                storage_plan.get("summary", {}).get("writes_database_now") is False
                and verification.get("summary", {}).get("executes_sql") is False
                and release.get("safety_summary", {}).get("runs_migration_now") is False
                and approval_review.get("safety_summary", {}).get("writes_database_now") is False,
                "release package must not enable SQL, migrations, table creation, audit-ledger writes, or release-file writes.",
            ),
            self._release_readiness_gate(
                "live_trading_disabled",
                not settings.enable_live_trading
                and storage_plan.get("live_trading_enabled") is False
                and release.get("live_trading_enabled") is False
                and approval_review.get("live_trading_enabled") is False,
                "live trading must remain disabled.",
            ),
        ]
        blocked = [gate for gate in gates if gate["status"] == "blocked"]
        review_required = [gate for gate in gates if gate["status"] == "review_required"]
        if blocked:
            status = "release_package_blocked"
        elif review_required:
            status = "release_package_review_required"
        else:
            status = "release_package_ready_for_manual_review"
        return {
            "schema_version": "trade_execution_audit_ledger_migration_release_package.v1",
            "status": status,
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "package_id": package_id,
            "package_id_inputs": package_id_inputs,
            "manifest": {
                "name": "trade_execution_audit_ledger_migration_manual_release_package",
                "purpose": "manual review evidence for a future SQLite trade execution audit ledger migration",
                "items": manifest_items,
                "required_manual_artifacts_before_execution": [
                    "reviewed_sqlite_migration_file",
                    "explicit_operator_release_approval",
                    "database_backup_and_restore_drill",
                    "rollback_plan_review",
                    "migration_unit_tests",
                    "api_smoke_tests",
                    "hash_chain_verifier_after_restore",
                    "forbidden_tracked_file_scan",
                    "separate_live_integration_review",
                ],
                "delivery": "api_response_only",
                "writes_file": False,
                "download_created": False,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "evidence": {
                "storage_plan_status": storage_plan.get("status"),
                "verification_status": verification.get("status"),
                "verification_failed_count": verification.get("failed_count"),
                "latest_approval_event_id": latest_approval.get("event_id") if latest_approval else None,
                "latest_approval_status": latest_approval.get("status") if latest_approval else None,
                "release_readiness_status": release.get("status"),
                "approval_review_status": approval_review.get("status"),
                "spec_hash": verification.get("spec_hash"),
                "approved_spec_hash": latest_approval.get("spec_hash") if latest_approval else None,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "gates": gates,
            "blocked_gates": blocked,
            "review_required_gates": review_required,
            "decision": {
                "go_no_go": "ready_for_manual_release_review" if status == "release_package_ready_for_manual_review" else "no_go",
                "migration_allowed_now": False,
                "execution_allowed_now": False,
                "release_approved_now": False,
                "requires_human_release_approval": True,
                "next_required_action": "manual_release_review" if status == "release_package_ready_for_manual_review" else "complete_missing_release_evidence",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "safety_summary": self._safety_summary()
            | {
                "executes_sql": False,
                "runs_migration_now": False,
                "creates_table_now": False,
                "writes_database_now": False,
                "writes_audit_ledger_row_now": False,
                "writes_migration_file_now": False,
                "writes_file": False,
                "download_created": False,
                "approves_release_now": False,
                "enables_gateway_now": False,
                "connects_broker": False,
                "places_real_trade": False,
                "stores_credentials": False,
            },
            "allowed_output": "review_only_audit_ledger_migration_release_package",
            "forbidden_actions": [
                "execute_sql",
                "run_migration_now",
                "create_table_now",
                "write_migration_file_now",
                "write_audit_ledger_row_now",
                "write_release_package_file",
                "create_download",
                "approve_release_now",
                "enable_gateway_now",
                "connect_broker",
                "submit_order",
                "store_credentials",
                "screen_click",
                "keyboard_type",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def audit_ledger_migration_release_package_integrity_review(
        self,
        limit: int = 50,
        max_age_days: int = 7,
        repeat_checks: int = 2,
    ) -> dict[str, Any]:
        safe_repeat_checks = max(2, min(repeat_checks, 5))
        packages = [
            self.audit_ledger_migration_release_package(limit=limit, max_age_days=max_age_days)
            for _ in range(safe_repeat_checks)
        ]
        package = packages[0]
        repeated_package_ids = [item.get("package_id") for item in packages]
        manifest = package.get("manifest", {})
        evidence = package.get("evidence", {})
        decision = package.get("decision", {})
        safety_summary = package.get("safety_summary", {})
        items = manifest.get("items", [])
        item_names = [item.get("name") for item in items]
        required_item_names = [
            "P4_disabled_audit_ledger_storage_plan",
            "P5_migration_spec_verifier",
            "P6_approval_metadata",
            "P7_release_readiness",
            "P8_approval_freshness",
        ]
        missing_items = [name for name in required_item_names if name not in item_names]
        duplicate_items = sorted({name for name in item_names if item_names.count(name) > 1})
        required_manual_artifacts = [
            "reviewed_sqlite_migration_file",
            "explicit_operator_release_approval",
            "database_backup_and_restore_drill",
            "rollback_plan_review",
            "migration_unit_tests",
            "api_smoke_tests",
            "hash_chain_verifier_after_restore",
            "forbidden_tracked_file_scan",
            "separate_live_integration_review",
        ]
        missing_manual_artifacts = [
            item
            for item in required_manual_artifacts
            if item not in manifest.get("required_manual_artifacts_before_execution", [])
        ]
        required_forbidden_actions = [
            "execute_sql",
            "run_migration_now",
            "create_table_now",
            "write_migration_file_now",
            "write_audit_ledger_row_now",
            "write_release_package_file",
            "create_download",
            "approve_release_now",
            "enable_gateway_now",
            "connect_broker",
            "submit_order",
            "store_credentials",
            "screen_click",
            "keyboard_type",
        ]
        missing_forbidden_actions = [
            action for action in required_forbidden_actions if action not in package.get("forbidden_actions", [])
        ]
        required_false_safety_fields = [
            "executes_sql",
            "runs_migration_now",
            "creates_table_now",
            "writes_database_now",
            "writes_audit_ledger_row_now",
            "writes_migration_file_now",
            "writes_file",
            "download_created",
            "approves_release_now",
            "enables_gateway_now",
            "connects_broker",
            "places_real_trade",
            "stores_credentials",
        ]
        unsafe_safety_fields = [
            field for field in required_false_safety_fields if safety_summary.get(field) is not False
        ]
        recomputed_package_id = self._stable_hash(package.get("package_id_inputs", {}))
        checks = [
            self._release_integrity_check(
                "package_id_recomputable",
                recomputed_package_id == package.get("package_id"),
                "package_id must be recomputable from package_id_inputs.",
                {
                    "expected_package_id": recomputed_package_id,
                    "actual_package_id": package.get("package_id"),
                },
            ),
            self._release_integrity_check(
                "package_id_stable_across_reads",
                len(set(repeated_package_ids)) == 1,
                "Repeated API-only package generation must produce the same package_id when source evidence is unchanged.",
                {"repeated_package_ids": repeated_package_ids},
            ),
            self._release_integrity_check(
                "required_manifest_items_present",
                not missing_items and not duplicate_items,
                "Manifest must contain each required P4-P8 evidence item once.",
                {"missing_items": missing_items, "duplicate_items": duplicate_items},
            ),
            self._release_integrity_check(
                "manifest_items_are_review_only",
                all(
                    item.get("included") is True
                    and item.get("review_only") is True
                    and item.get("simulation_only") is True
                    and item.get("live_trading_enabled") is False
                    for item in items
                ),
                "Every manifest item must remain review-only, simulation-only, and live-disabled.",
                {"item_count": len(items)},
            ),
            self._release_integrity_check(
                "manual_artifacts_complete",
                not missing_manual_artifacts,
                "Release package must list the required manual artifacts before any future migration execution review.",
                {"missing_manual_artifacts": missing_manual_artifacts},
            ),
            self._release_integrity_check(
                "api_response_only_delivery",
                manifest.get("delivery") == "api_response_only"
                and manifest.get("writes_file") is False
                and manifest.get("download_created") is False,
                "Release package must stay API-response-only with no file write or download creation.",
                {
                    "delivery": manifest.get("delivery"),
                    "writes_file": manifest.get("writes_file"),
                    "download_created": manifest.get("download_created"),
                },
            ),
            self._release_integrity_check(
                "decision_remains_non_executable",
                decision.get("migration_allowed_now") is False
                and decision.get("execution_allowed_now") is False
                and decision.get("release_approved_now") is False,
                "Integrity review must not convert package evidence into execution, migration, or release approval.",
                {
                    "migration_allowed_now": decision.get("migration_allowed_now"),
                    "execution_allowed_now": decision.get("execution_allowed_now"),
                    "release_approved_now": decision.get("release_approved_now"),
                },
            ),
            self._release_integrity_check(
                "safety_summary_allows_no_mutation",
                not unsafe_safety_fields,
                "Safety summary must explicitly deny SQL, migrations, file writes, audit-ledger writes, gateway enablement, broker actions, and credentials.",
                {"unsafe_safety_fields": unsafe_safety_fields},
            ),
            self._release_integrity_check(
                "forbidden_actions_complete",
                not missing_forbidden_actions,
                "Forbidden actions must include execution, migration, file, broker, credential, order, and screen-control actions.",
                {"missing_forbidden_actions": missing_forbidden_actions},
            ),
            self._release_integrity_check(
                "evidence_matches_package_inputs",
                package.get("package_id_inputs", {}).get("spec_hash") == evidence.get("spec_hash")
                and package.get("package_id_inputs", {}).get("latest_approval_spec_hash") == evidence.get("approved_spec_hash")
                and package.get("package_id_inputs", {}).get("release_status") == evidence.get("release_readiness_status")
                and package.get("package_id_inputs", {}).get("approval_review_status") == evidence.get("approval_review_status"),
                "Package inputs must trace back to the evidence object that an operator reviews.",
                {
                    "package_id_inputs": package.get("package_id_inputs"),
                    "evidence": evidence,
                },
            ),
            self._release_integrity_check(
                "live_trading_disabled",
                package.get("live_trading_enabled") is False
                and manifest.get("live_trading_enabled") is False
                and evidence.get("live_trading_enabled") is False
                and decision.get("live_trading_enabled") is False
                and not settings.enable_live_trading,
                "Live trading must remain disabled across package, manifest, evidence, and decision.",
                {
                    "package_live_trading_enabled": package.get("live_trading_enabled"),
                    "manifest_live_trading_enabled": manifest.get("live_trading_enabled"),
                    "evidence_live_trading_enabled": evidence.get("live_trading_enabled"),
                    "decision_live_trading_enabled": decision.get("live_trading_enabled"),
                    "settings_live_trading_enabled": settings.enable_live_trading,
                },
            ),
        ]
        failed_checks = [check for check in checks if check["status"] == "failed"]
        release_package_ready = package.get("status") == "release_package_ready_for_manual_review"
        if failed_checks:
            status = "integrity_review_failed"
            next_required_action = "repair_release_package_integrity"
        elif release_package_ready:
            status = "integrity_review_passed"
            next_required_action = "manual_release_review"
        else:
            status = "integrity_review_passed_release_evidence_pending"
            next_required_action = "complete_missing_release_evidence"
        return {
            "schema_version": "trade_execution_audit_ledger_migration_release_package_integrity_review.v1",
            "status": status,
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source_package_id": package.get("package_id"),
            "source_package_status": package.get("status"),
            "recomputed_package_id": recomputed_package_id,
            "repeat_checks": safe_repeat_checks,
            "repeated_package_ids": repeated_package_ids,
            "checks": checks,
            "failed_checks": failed_checks,
            "failed_check_count": len(failed_checks),
            "manifest_summary": {
                "item_count": len(items),
                "required_item_names": required_item_names,
                "missing_items": missing_items,
                "duplicate_items": duplicate_items,
                "missing_manual_artifacts": missing_manual_artifacts,
                "delivery": manifest.get("delivery"),
                "writes_file": manifest.get("writes_file"),
                "download_created": manifest.get("download_created"),
                "review_only": manifest.get("review_only"),
                "simulation_only": manifest.get("simulation_only"),
                "live_trading_enabled": manifest.get("live_trading_enabled"),
            },
            "decision": {
                "package_id_stable": len(set(repeated_package_ids)) == 1,
                "manifest_integrity_passed": not failed_checks,
                "release_package_ready": release_package_ready,
                "go_no_go": "ready_for_manual_release_review" if status == "integrity_review_passed" else "no_go",
                "migration_allowed_now": False,
                "execution_allowed_now": False,
                "release_approved_now": False,
                "next_required_action": next_required_action,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "safety_summary": self._safety_summary()
            | {
                "executes_sql": False,
                "runs_migration_now": False,
                "creates_table_now": False,
                "writes_database_now": False,
                "writes_audit_ledger_row_now": False,
                "writes_migration_file_now": False,
                "writes_file": False,
                "download_created": False,
                "approves_release_now": False,
                "enables_gateway_now": False,
                "connects_broker": False,
                "places_real_trade": False,
                "stores_credentials": False,
                "mutates_source_package": False,
            },
            "allowed_output": "review_only_audit_ledger_migration_release_package_integrity_review",
            "forbidden_actions": package.get("forbidden_actions", [])
            + [
                "mutate_release_package",
                "approve_release_from_integrity_review",
                "persist_integrity_snapshot",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def audit_ledger_migration_manual_release_review_rehearsal(
        self,
        limit: int = 50,
        max_age_days: int = 7,
        repeat_checks: int = 2,
    ) -> dict[str, Any]:
        integrity = self.audit_ledger_migration_release_package_integrity_review(
            limit=limit,
            max_age_days=max_age_days,
            repeat_checks=repeat_checks,
        )
        integrity_passed = integrity.get("decision", {}).get("manifest_integrity_passed") is True
        release_package_ready = integrity.get("decision", {}).get("release_package_ready") is True
        source_package_id = integrity.get("source_package_id")
        source_package_status = integrity.get("source_package_status")
        manifest_summary = integrity.get("manifest_summary", {})
        missing_manual_artifacts = manifest_summary.get("missing_manual_artifacts", [])
        steps = [
            self._manual_release_rehearsal_step(
                "confirm_package_identity",
                integrity.get("decision", {}).get("package_id_stable") is True
                and source_package_id == integrity.get("recomputed_package_id"),
                "Operator compares the package id with the recomputed id and repeated package-id evidence.",
                {"source_package_id": source_package_id, "recomputed_package_id": integrity.get("recomputed_package_id")},
            ),
            self._manual_release_rehearsal_step(
                "review_integrity_checks",
                integrity_passed and integrity.get("failed_check_count") == 0,
                "Operator reviews all package integrity checks and confirms no failed checks are present.",
                {"failed_check_count": integrity.get("failed_check_count"), "check_count": len(integrity.get("checks", []))},
            ),
            self._manual_release_rehearsal_step(
                "confirm_release_evidence_ready",
                release_package_ready,
                "Operator confirms release package evidence is ready before any future manual release discussion.",
                {"source_package_status": source_package_status},
                pending_reason="Release package evidence is still pending.",
            ),
            self._manual_release_rehearsal_step(
                "review_required_manual_artifacts",
                not missing_manual_artifacts,
                "Operator reviews required manual artifacts: migration file review, release approval, backup/restore drill, rollback, tests, hash-chain verifier, forbidden-file scan, and separate live integration review.",
                {"missing_manual_artifacts": missing_manual_artifacts},
            ),
            self._manual_release_rehearsal_step(
                "verify_no_api_release_approval",
                integrity.get("decision", {}).get("release_approved_now") is False,
                "Operator confirms this API cannot approve release or convert rehearsal evidence into approval.",
                {"release_approved_now": integrity.get("decision", {}).get("release_approved_now")},
            ),
            self._manual_release_rehearsal_step(
                "verify_no_migration_execution",
                integrity.get("decision", {}).get("migration_allowed_now") is False
                and integrity.get("decision", {}).get("execution_allowed_now") is False,
                "Operator confirms rehearsal cannot execute migrations or trading actions.",
                {
                    "migration_allowed_now": integrity.get("decision", {}).get("migration_allowed_now"),
                    "execution_allowed_now": integrity.get("decision", {}).get("execution_allowed_now"),
                },
            ),
            self._manual_release_rehearsal_step(
                "verify_no_persistence_or_download",
                integrity.get("safety_summary", {}).get("writes_file") is False
                and integrity.get("safety_summary", {}).get("download_created") is False
                and integrity.get("safety_summary", {}).get("writes_database_now") is False,
                "Operator confirms rehearsal returns API metadata only and does not persist review snapshots or downloads.",
                {
                    "writes_file": integrity.get("safety_summary", {}).get("writes_file"),
                    "download_created": integrity.get("safety_summary", {}).get("download_created"),
                    "writes_database_now": integrity.get("safety_summary", {}).get("writes_database_now"),
                },
            ),
            self._manual_release_rehearsal_step(
                "verify_live_trading_disabled",
                integrity.get("live_trading_enabled") is False and not settings.enable_live_trading,
                "Operator confirms live trading stays disabled during rehearsal.",
                {
                    "integrity_live_trading_enabled": integrity.get("live_trading_enabled"),
                    "settings_live_trading_enabled": settings.enable_live_trading,
                },
            ),
        ]
        pending_steps = [step for step in steps if step["status"] == "pending_evidence"]
        failed_steps = [step for step in steps if step["status"] == "blocked"]
        if failed_steps:
            status = "manual_release_rehearsal_blocked"
            next_required_action = "repair_rehearsal_blockers"
        elif pending_steps:
            status = "manual_release_rehearsal_waiting_for_evidence"
            next_required_action = "complete_missing_release_evidence"
        else:
            status = "manual_release_rehearsal_ready"
            next_required_action = "perform_offline_manual_release_review"
        rehearsal_id = self._stable_hash(
            {
                "source_package_id": source_package_id,
                "integrity_status": integrity.get("status"),
                "source_package_status": source_package_status,
                "step_statuses": {step["name"]: step["status"] for step in steps},
                "max_age_days": max(1, min(max_age_days, 365)),
            }
        )
        return {
            "schema_version": "trade_execution_audit_ledger_migration_manual_release_rehearsal.v1",
            "status": status,
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "rehearsal_id": rehearsal_id,
            "source_package_id": source_package_id,
            "source_package_status": source_package_status,
            "integrity_status": integrity.get("status"),
            "steps": steps,
            "pending_steps": pending_steps,
            "failed_steps": failed_steps,
            "operator_rehearsal_policy": {
                "api_can_record_operator_review": False,
                "api_can_mark_rehearsal_complete": False,
                "api_can_approve_release": False,
                "api_can_execute_migration": False,
                "offline_human_review_required": True,
                "dual_control_required_before_future_execution": True,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "required_offline_artifacts": [
                "signed_manual_release_review",
                "reviewed_sqlite_migration_file",
                "database_backup_and_restore_drill_evidence",
                "rollback_plan_signoff",
                "migration_test_report",
                "api_smoke_report",
                "post_restore_hash_chain_verification",
                "forbidden_tracked_file_scan_report",
                "separate_live_integration_review",
            ],
            "decision": {
                "rehearsal_ready_for_operator": status == "manual_release_rehearsal_ready",
                "manual_review_recorded_now": False,
                "release_approved_now": False,
                "migration_allowed_now": False,
                "execution_allowed_now": False,
                "gateway_can_execute": False,
                "go_no_go": "ready_for_offline_manual_review" if status == "manual_release_rehearsal_ready" else "no_go",
                "next_required_action": next_required_action,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "safety_summary": self._safety_summary()
            | {
                "executes_sql": False,
                "runs_migration_now": False,
                "creates_table_now": False,
                "writes_database_now": False,
                "writes_audit_ledger_row_now": False,
                "writes_migration_file_now": False,
                "writes_file": False,
                "download_created": False,
                "records_manual_review_now": False,
                "marks_rehearsal_complete_now": False,
                "approves_release_now": False,
                "enables_gateway_now": False,
                "connects_broker": False,
                "places_real_trade": False,
                "stores_credentials": False,
            },
            "allowed_output": "review_only_manual_release_review_rehearsal",
            "forbidden_actions": integrity.get("forbidden_actions", [])
            + [
                "record_manual_release_review_by_api",
                "mark_rehearsal_complete_by_api",
                "approve_release_from_rehearsal",
                "execute_migration_from_rehearsal",
                "persist_rehearsal_snapshot",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def verify_audit_ledger_migration_manual_release_evidence(
        self,
        evidence: dict[str, Any] | None = None,
        limit: int = 50,
        max_age_days: int = 7,
        repeat_checks: int = 2,
    ) -> dict[str, Any]:
        rehearsal = self.audit_ledger_migration_manual_release_review_rehearsal(
            limit=limit,
            max_age_days=max_age_days,
            repeat_checks=repeat_checks,
        )
        payload = evidence or {}
        artifacts = payload.get("artifacts") if isinstance(payload, dict) else None
        artifact_list = artifacts if isinstance(artifacts, list) else []
        artifacts_by_name = {
            str(item.get("name")): item
            for item in artifact_list
            if isinstance(item, dict) and item.get("name")
        }
        required_artifacts = list(rehearsal.get("required_offline_artifacts", []))
        missing_artifacts = [name for name in required_artifacts if name not in artifacts_by_name]
        duplicate_artifacts = sorted(
            {
                str(item.get("name"))
                for item in artifact_list
                if isinstance(item, dict)
                and item.get("name")
                and [str(other.get("name")) for other in artifact_list if isinstance(other, dict)].count(str(item.get("name"))) > 1
            }
        )
        artifacts_missing_hash = [
            name
            for name, item in artifacts_by_name.items()
            if item.get("present") is not True
            or not isinstance(item.get("artifact_hash"), str)
            or len(item.get("artifact_hash", "")) < 16
        ]
        artifacts_missing_review = [
            name
            for name, item in artifacts_by_name.items()
            if not item.get("reviewed_by") or not item.get("reviewed_at")
        ]
        forbidden_evidence_fields = [
            "sql_text",
            "shell_command",
            "broker_credentials",
            "trading_password",
            "account_funds",
            "live_positions",
            "order_action",
            "screen_click",
        ]
        forbidden_field_hits = sorted(
            {
                field
                for item in artifact_list
                if isinstance(item, dict)
                for field in forbidden_evidence_fields
                if field in item
            }
        )
        checks = [
            self._manual_release_evidence_check(
                "rehearsal_ready",
                rehearsal.get("status") == "manual_release_rehearsal_ready",
                "Manual release evidence can only pass after the rehearsal is ready for offline operator review.",
                {"rehearsal_status": rehearsal.get("status")},
            ),
            self._manual_release_evidence_check(
                "source_package_id_matches",
                payload.get("source_package_id") == rehearsal.get("source_package_id"),
                "Evidence must reference the rehearsal source package id.",
                {
                    "expected_source_package_id": rehearsal.get("source_package_id"),
                    "actual_source_package_id": payload.get("source_package_id"),
                },
            ),
            self._manual_release_evidence_check(
                "rehearsal_id_matches",
                payload.get("rehearsal_id") == rehearsal.get("rehearsal_id"),
                "Evidence must reference the current rehearsal id.",
                {
                    "expected_rehearsal_id": rehearsal.get("rehearsal_id"),
                    "actual_rehearsal_id": payload.get("rehearsal_id"),
                },
            ),
            self._manual_release_evidence_check(
                "required_artifacts_present_once",
                not missing_artifacts and not duplicate_artifacts,
                "All required offline artifacts must be represented exactly once.",
                {"missing_artifacts": missing_artifacts, "duplicate_artifacts": duplicate_artifacts},
            ),
            self._manual_release_evidence_check(
                "artifact_hashes_present",
                not artifacts_missing_hash and len(artifacts_by_name) >= len(required_artifacts),
                "Every artifact must be marked present and carry a non-empty evidence hash.",
                {"artifacts_missing_hash": artifacts_missing_hash},
            ),
            self._manual_release_evidence_check(
                "artifact_reviews_present",
                not artifacts_missing_review and len(artifacts_by_name) >= len(required_artifacts),
                "Every artifact must include offline reviewer and review timestamp metadata.",
                {"artifacts_missing_review": artifacts_missing_review},
            ),
            self._manual_release_evidence_check(
                "no_forbidden_evidence_fields",
                not forbidden_field_hits,
                "Evidence payload must not contain SQL text, shell commands, broker credentials, account data, order actions, or screen-control fields.",
                {"forbidden_field_hits": forbidden_field_hits},
            ),
            self._manual_release_evidence_check(
                "payload_safety_flags",
                payload.get("review_only") is True
                and payload.get("simulation_only") is True
                and payload.get("live_trading_enabled") is False,
                "Evidence payload must keep review-only, simulation-only, and live-trading-disabled flags.",
                {
                    "review_only": payload.get("review_only"),
                    "simulation_only": payload.get("simulation_only"),
                    "live_trading_enabled": payload.get("live_trading_enabled"),
                },
            ),
            self._manual_release_evidence_check(
                "verifier_remains_non_executable",
                rehearsal.get("decision", {}).get("release_approved_now") is False
                and rehearsal.get("decision", {}).get("migration_allowed_now") is False
                and rehearsal.get("decision", {}).get("execution_allowed_now") is False,
                "Verifier must not convert evidence into release approval, migration permission, or execution.",
                {
                    "release_approved_now": rehearsal.get("decision", {}).get("release_approved_now"),
                    "migration_allowed_now": rehearsal.get("decision", {}).get("migration_allowed_now"),
                    "execution_allowed_now": rehearsal.get("decision", {}).get("execution_allowed_now"),
                },
            ),
            self._manual_release_evidence_check(
                "live_trading_disabled",
                rehearsal.get("live_trading_enabled") is False and not settings.enable_live_trading,
                "Live trading must remain disabled while verifying manual release evidence.",
                {
                    "rehearsal_live_trading_enabled": rehearsal.get("live_trading_enabled"),
                    "settings_live_trading_enabled": settings.enable_live_trading,
                },
            ),
        ]
        failed_checks = [check for check in checks if check["status"] == "failed"]
        if not artifact_list:
            status = "manual_release_evidence_missing"
            next_required_action = "collect_offline_manual_release_artifacts"
        elif failed_checks:
            status = "manual_release_evidence_verification_failed"
            next_required_action = "repair_manual_release_evidence"
        else:
            status = "manual_release_evidence_verification_passed"
            next_required_action = "offline_release_review_can_continue"
        verification_id = self._stable_hash(
            {
                "source_package_id": rehearsal.get("source_package_id"),
                "rehearsal_id": rehearsal.get("rehearsal_id"),
                "artifact_names": sorted(artifacts_by_name),
                "check_statuses": {check["name"]: check["status"] for check in checks},
                "payload_review_only": payload.get("review_only"),
                "payload_simulation_only": payload.get("simulation_only"),
                "payload_live_trading_enabled": payload.get("live_trading_enabled"),
            }
        )
        return {
            "schema_version": "trade_execution_audit_ledger_migration_manual_release_evidence_verifier.v1",
            "status": status,
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "verification_id": verification_id,
            "source_package_id": rehearsal.get("source_package_id"),
            "rehearsal_id": rehearsal.get("rehearsal_id"),
            "rehearsal_status": rehearsal.get("status"),
            "required_artifacts": required_artifacts,
            "provided_artifact_names": sorted(artifacts_by_name),
            "missing_artifacts": missing_artifacts,
            "duplicate_artifacts": duplicate_artifacts,
            "checks": checks,
            "failed_checks": failed_checks,
            "failed_check_count": len(failed_checks),
            "decision": {
                "evidence_complete": status == "manual_release_evidence_verification_passed",
                "manual_review_recorded_now": False,
                "release_approved_now": False,
                "migration_allowed_now": False,
                "execution_allowed_now": False,
                "gateway_can_execute": False,
                "go_no_go": "evidence_complete_for_offline_review" if status == "manual_release_evidence_verification_passed" else "no_go",
                "next_required_action": next_required_action,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "safety_summary": self._safety_summary()
            | {
                "executes_sql": False,
                "runs_migration_now": False,
                "creates_table_now": False,
                "writes_database_now": False,
                "writes_audit_ledger_row_now": False,
                "writes_migration_file_now": False,
                "writes_file": False,
                "download_created": False,
                "persists_manual_release_evidence": False,
                "records_manual_review_now": False,
                "approves_release_now": False,
                "enables_gateway_now": False,
                "connects_broker": False,
                "places_real_trade": False,
                "stores_credentials": False,
            },
            "allowed_output": "review_only_manual_release_evidence_verification",
            "forbidden_actions": rehearsal.get("forbidden_actions", [])
            + [
                "persist_manual_release_evidence",
                "record_manual_release_review_by_api",
                "approve_release_from_evidence_verifier",
                "execute_migration_from_evidence_verifier",
                "create_evidence_download",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def compare_audit_ledger_migration_manual_release_evidence(
        self,
        baseline_evidence: dict[str, Any] | None = None,
        candidate_evidence: dict[str, Any] | None = None,
        limit: int = 50,
        max_age_days: int = 7,
        repeat_checks: int = 2,
    ) -> dict[str, Any]:
        baseline_payload = baseline_evidence or {}
        candidate_payload = candidate_evidence or {}
        baseline = self.verify_audit_ledger_migration_manual_release_evidence(
            evidence=baseline_payload,
            limit=limit,
            max_age_days=max_age_days,
            repeat_checks=repeat_checks,
        )
        candidate = self.verify_audit_ledger_migration_manual_release_evidence(
            evidence=candidate_payload,
            limit=limit,
            max_age_days=max_age_days,
            repeat_checks=repeat_checks,
        )
        baseline_hashes = self._manual_release_artifact_hashes(baseline_payload)
        candidate_hashes = self._manual_release_artifact_hashes(candidate_payload)
        baseline_reviews = self._manual_release_artifact_reviews(baseline_payload)
        candidate_reviews = self._manual_release_artifact_reviews(candidate_payload)
        baseline_names = set(baseline_hashes)
        candidate_names = set(candidate_hashes)
        artifact_names_added = sorted(candidate_names - baseline_names)
        artifact_names_removed = sorted(baseline_names - candidate_names)
        artifact_hash_changes = [
            {
                "name": name,
                "baseline_hash": baseline_hashes.get(name),
                "candidate_hash": candidate_hashes.get(name),
            }
            for name in sorted(baseline_names & candidate_names)
            if baseline_hashes.get(name) != candidate_hashes.get(name)
        ]
        artifact_review_changes = [
            {
                "name": name,
                "baseline_review": baseline_reviews.get(name),
                "candidate_review": candidate_reviews.get(name),
            }
            for name in sorted(set(baseline_reviews) & set(candidate_reviews))
            if baseline_reviews.get(name) != candidate_reviews.get(name)
        ]
        baseline_check_statuses = {check["name"]: check["status"] for check in baseline.get("checks", [])}
        candidate_check_statuses = {check["name"]: check["status"] for check in candidate.get("checks", [])}
        check_status_differences = [
            {
                "name": name,
                "baseline_status": baseline_check_statuses.get(name),
                "candidate_status": candidate_check_statuses.get(name),
            }
            for name in sorted(set(baseline_check_statuses) | set(candidate_check_statuses))
            if baseline_check_statuses.get(name) != candidate_check_statuses.get(name)
        ]
        comparison_checks = [
            self._manual_release_evidence_check(
                "baseline_and_candidate_present",
                bool(baseline_hashes) and bool(candidate_hashes),
                "Both baseline and candidate evidence payloads must include offline artifacts before comparison can pass.",
                {
                    "baseline_artifact_count": len(baseline_hashes),
                    "candidate_artifact_count": len(candidate_hashes),
                },
            ),
            self._manual_release_evidence_check(
                "source_package_id_stable",
                baseline.get("source_package_id") == candidate.get("source_package_id"),
                "Evidence revisions must point to the same manual release package.",
                {
                    "baseline_source_package_id": baseline.get("source_package_id"),
                    "candidate_source_package_id": candidate.get("source_package_id"),
                },
            ),
            self._manual_release_evidence_check(
                "rehearsal_id_stable",
                baseline.get("rehearsal_id") == candidate.get("rehearsal_id"),
                "Evidence revisions must point to the same manual release rehearsal.",
                {
                    "baseline_rehearsal_id": baseline.get("rehearsal_id"),
                    "candidate_rehearsal_id": candidate.get("rehearsal_id"),
                },
            ),
            self._manual_release_evidence_check(
                "verification_status_stable",
                baseline.get("status") == candidate.get("status"),
                "Verifier status should be stable across compared evidence revisions.",
                {
                    "baseline_status": baseline.get("status"),
                    "candidate_status": candidate.get("status"),
                },
            ),
            self._manual_release_evidence_check(
                "artifact_names_stable",
                not artifact_names_added and not artifact_names_removed,
                "Artifact names should not be added or removed between evidence revisions without operator review.",
                {
                    "artifact_names_added": artifact_names_added,
                    "artifact_names_removed": artifact_names_removed,
                },
            ),
            self._manual_release_evidence_check(
                "artifact_hashes_stable",
                not artifact_hash_changes,
                "Artifact hashes should stay stable between evidence revisions unless the change is reviewed offline.",
                {"artifact_hash_changes": artifact_hash_changes},
            ),
            self._manual_release_evidence_check(
                "artifact_review_metadata_stable",
                not artifact_review_changes,
                "Reviewer metadata should stay stable between evidence revisions unless the change is reviewed offline.",
                {"artifact_review_changes": artifact_review_changes},
            ),
            self._manual_release_evidence_check(
                "check_statuses_stable",
                not check_status_differences,
                "Verifier check statuses should stay stable between evidence revisions.",
                {"check_status_differences": check_status_differences},
            ),
            self._manual_release_evidence_check(
                "comparison_remains_non_executable",
                baseline.get("decision", {}).get("release_approved_now") is False
                and candidate.get("decision", {}).get("release_approved_now") is False
                and baseline.get("decision", {}).get("migration_allowed_now") is False
                and candidate.get("decision", {}).get("migration_allowed_now") is False
                and baseline.get("decision", {}).get("execution_allowed_now") is False
                and candidate.get("decision", {}).get("execution_allowed_now") is False,
                "Comparison must not convert evidence stability into release approval, migration permission, or execution.",
                {
                    "baseline_release_approved_now": baseline.get("decision", {}).get("release_approved_now"),
                    "candidate_release_approved_now": candidate.get("decision", {}).get("release_approved_now"),
                    "baseline_migration_allowed_now": baseline.get("decision", {}).get("migration_allowed_now"),
                    "candidate_migration_allowed_now": candidate.get("decision", {}).get("migration_allowed_now"),
                    "baseline_execution_allowed_now": baseline.get("decision", {}).get("execution_allowed_now"),
                    "candidate_execution_allowed_now": candidate.get("decision", {}).get("execution_allowed_now"),
                },
            ),
            self._manual_release_evidence_check(
                "live_trading_disabled",
                baseline.get("live_trading_enabled") is False
                and candidate.get("live_trading_enabled") is False
                and not settings.enable_live_trading,
                "Live trading must remain disabled while comparing manual release evidence.",
                {
                    "baseline_live_trading_enabled": baseline.get("live_trading_enabled"),
                    "candidate_live_trading_enabled": candidate.get("live_trading_enabled"),
                    "settings_live_trading_enabled": settings.enable_live_trading,
                },
            ),
        ]
        failed_checks = [check for check in comparison_checks if check["status"] == "failed"]
        if not baseline_hashes or not candidate_hashes:
            status = "manual_release_evidence_comparison_missing"
            next_required_action = "provide_two_offline_evidence_payloads"
        elif failed_checks:
            status = "manual_release_evidence_comparison_changed"
            next_required_action = "review_evidence_revision_differences_offline"
        else:
            status = "manual_release_evidence_comparison_stable"
            next_required_action = "continue_offline_release_review_with_stable_evidence"
        comparison_id = self._stable_hash(
            {
                "baseline_verification_id": baseline.get("verification_id"),
                "candidate_verification_id": candidate.get("verification_id"),
                "artifact_hash_changes": artifact_hash_changes,
                "artifact_review_changes": artifact_review_changes,
                "check_status_differences": check_status_differences,
                "status": status,
            }
        )
        return {
            "schema_version": "trade_execution_audit_ledger_migration_manual_release_evidence_comparison.v1",
            "status": status,
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "comparison_id": comparison_id,
            "baseline": {
                "status": baseline.get("status"),
                "verification_id": baseline.get("verification_id"),
                "source_package_id": baseline.get("source_package_id"),
                "rehearsal_id": baseline.get("rehearsal_id"),
                "provided_artifact_names": baseline.get("provided_artifact_names", []),
                "failed_check_count": baseline.get("failed_check_count"),
                "evidence_complete": baseline.get("decision", {}).get("evidence_complete"),
            },
            "candidate": {
                "status": candidate.get("status"),
                "verification_id": candidate.get("verification_id"),
                "source_package_id": candidate.get("source_package_id"),
                "rehearsal_id": candidate.get("rehearsal_id"),
                "provided_artifact_names": candidate.get("provided_artifact_names", []),
                "failed_check_count": candidate.get("failed_check_count"),
                "evidence_complete": candidate.get("decision", {}).get("evidence_complete"),
            },
            "artifact_names_added": artifact_names_added,
            "artifact_names_removed": artifact_names_removed,
            "artifact_hash_changes": artifact_hash_changes,
            "artifact_review_changes": artifact_review_changes,
            "check_status_differences": check_status_differences,
            "checks": comparison_checks,
            "failed_checks": failed_checks,
            "failed_check_count": len(failed_checks),
            "decision": {
                "evidence_pair_stable": status == "manual_release_evidence_comparison_stable",
                "manual_review_recorded_now": False,
                "release_approved_now": False,
                "migration_allowed_now": False,
                "execution_allowed_now": False,
                "gateway_can_execute": False,
                "go_no_go": "stable_evidence_pair_for_offline_review" if status == "manual_release_evidence_comparison_stable" else "no_go",
                "next_required_action": next_required_action,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "safety_summary": self._safety_summary()
            | {
                "executes_sql": False,
                "runs_migration_now": False,
                "creates_table_now": False,
                "writes_database_now": False,
                "writes_audit_ledger_row_now": False,
                "writes_migration_file_now": False,
                "writes_file": False,
                "download_created": False,
                "persists_manual_release_evidence": False,
                "persists_manual_release_evidence_comparison": False,
                "mutates_evidence": False,
                "records_manual_review_now": False,
                "approves_release_now": False,
                "enables_gateway_now": False,
                "connects_broker": False,
                "places_real_trade": False,
                "stores_credentials": False,
            },
            "allowed_output": "review_only_manual_release_evidence_comparison",
            "forbidden_actions": [
                "persist_manual_release_evidence_comparison",
                "record_manual_release_review_by_api",
                "approve_release_from_evidence_comparison",
                "execute_migration_from_evidence_comparison",
                "create_evidence_comparison_download",
                "write_evidence_comparison_file",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def audit_ledger_migration_manual_release_health_digest(
        self,
        baseline_evidence: dict[str, Any] | None = None,
        candidate_evidence: dict[str, Any] | None = None,
        limit: int = 50,
        max_age_days: int = 7,
        repeat_checks: int = 2,
    ) -> dict[str, Any]:
        release_package = self.audit_ledger_migration_release_package(
            limit=limit,
            max_age_days=max_age_days,
        )
        integrity = self.audit_ledger_migration_release_package_integrity_review(
            limit=limit,
            max_age_days=max_age_days,
            repeat_checks=repeat_checks,
        )
        rehearsal = self.audit_ledger_migration_manual_release_review_rehearsal(
            limit=limit,
            max_age_days=max_age_days,
            repeat_checks=repeat_checks,
        )
        candidate_payload = candidate_evidence or {}
        baseline_payload = baseline_evidence or candidate_payload
        verifier = self.verify_audit_ledger_migration_manual_release_evidence(
            evidence=candidate_payload,
            limit=limit,
            max_age_days=max_age_days,
            repeat_checks=repeat_checks,
        )
        comparison = self.compare_audit_ledger_migration_manual_release_evidence(
            baseline_evidence=baseline_payload,
            candidate_evidence=candidate_payload,
            limit=limit,
            max_age_days=max_age_days,
            repeat_checks=repeat_checks,
        )
        module_statuses = [
            self._manual_release_digest_module(
                "manual_release_package",
                release_package.get("status"),
                release_package.get("package_id"),
                release_package.get("decision", {}).get("go_no_go"),
            ),
            self._manual_release_digest_module(
                "release_package_integrity",
                integrity.get("status"),
                integrity.get("integrity_id"),
                integrity.get("decision", {}).get("go_no_go"),
            ),
            self._manual_release_digest_module(
                "manual_release_rehearsal",
                rehearsal.get("status"),
                rehearsal.get("rehearsal_id"),
                rehearsal.get("decision", {}).get("go_no_go"),
            ),
            self._manual_release_digest_module(
                "manual_release_evidence_verifier",
                verifier.get("status"),
                verifier.get("verification_id"),
                verifier.get("decision", {}).get("go_no_go"),
            ),
            self._manual_release_digest_module(
                "manual_release_evidence_comparison",
                comparison.get("status"),
                comparison.get("comparison_id"),
                comparison.get("decision", {}).get("go_no_go"),
            ),
        ]
        attention_items = [
            item
            for item in module_statuses
            if item["status"]
            not in {
                "release_package_ready_for_manual_review",
                "integrity_review_passed",
                "manual_release_rehearsal_ready",
                "manual_release_evidence_verification_passed",
                "manual_release_evidence_comparison_stable",
            }
        ]
        digest_checks = [
            self._manual_release_evidence_check(
                "release_package_ready",
                release_package.get("status") == "release_package_ready_for_manual_review",
                "Manual release package must be ready for operator review.",
                {
                    "status": release_package.get("status"),
                    "package_id": release_package.get("package_id"),
                },
            ),
            self._manual_release_evidence_check(
                "integrity_review_passed",
                integrity.get("status") == "integrity_review_passed",
                "Release package integrity must pass before evidence health can be healthy.",
                {
                    "status": integrity.get("status"),
                    "failed_check_count": integrity.get("failed_check_count"),
                },
            ),
            self._manual_release_evidence_check(
                "manual_release_rehearsal_ready",
                rehearsal.get("status") == "manual_release_rehearsal_ready",
                "Offline manual release rehearsal must be ready.",
                {
                    "status": rehearsal.get("status"),
                    "pending_steps": rehearsal.get("pending_steps", []),
                },
            ),
            self._manual_release_evidence_check(
                "evidence_verification_passed",
                verifier.get("status") == "manual_release_evidence_verification_passed",
                "Manual release evidence must verify before the digest is healthy.",
                {
                    "status": verifier.get("status"),
                    "failed_check_count": verifier.get("failed_check_count"),
                    "missing_artifacts": verifier.get("missing_artifacts", []),
                },
            ),
            self._manual_release_evidence_check(
                "evidence_comparison_stable",
                comparison.get("status") == "manual_release_evidence_comparison_stable",
                "Manual release evidence revisions must compare as stable before the digest is healthy.",
                {
                    "status": comparison.get("status"),
                    "failed_check_count": comparison.get("failed_check_count"),
                    "artifact_hash_changes": comparison.get("artifact_hash_changes", []),
                },
            ),
            self._manual_release_evidence_check(
                "digest_remains_non_executable",
                release_package.get("decision", {}).get("release_approved_now") is False
                and integrity.get("decision", {}).get("release_approved_now") is False
                and rehearsal.get("decision", {}).get("release_approved_now") is False
                and verifier.get("decision", {}).get("release_approved_now") is False
                and comparison.get("decision", {}).get("release_approved_now") is False
                and comparison.get("decision", {}).get("execution_allowed_now") is False,
                "Digest must not convert healthy evidence into approval, migration permission, or execution.",
                {
                    "package_release_approved_now": release_package.get("decision", {}).get("release_approved_now"),
                    "integrity_release_approved_now": integrity.get("decision", {}).get("release_approved_now"),
                    "rehearsal_release_approved_now": rehearsal.get("decision", {}).get("release_approved_now"),
                    "verifier_release_approved_now": verifier.get("decision", {}).get("release_approved_now"),
                    "comparison_release_approved_now": comparison.get("decision", {}).get("release_approved_now"),
                    "comparison_execution_allowed_now": comparison.get("decision", {}).get("execution_allowed_now"),
                },
            ),
            self._manual_release_evidence_check(
                "live_trading_disabled",
                release_package.get("live_trading_enabled") is False
                and integrity.get("live_trading_enabled") is False
                and rehearsal.get("live_trading_enabled") is False
                and verifier.get("live_trading_enabled") is False
                and comparison.get("live_trading_enabled") is False
                and not settings.enable_live_trading,
                "Live trading must remain disabled while generating the health digest.",
                {"settings_live_trading_enabled": settings.enable_live_trading},
            ),
        ]
        failed_checks = [check for check in digest_checks if check["status"] == "failed"]
        status = (
            "manual_release_health_digest_healthy"
            if not failed_checks
            else "manual_release_health_digest_attention_required"
        )
        digest_id = self._stable_hash(
            {
                "module_statuses": {item["name"]: item["status"] for item in module_statuses},
                "failed_checks": [check["name"] for check in failed_checks],
                "package_id": release_package.get("package_id"),
                "integrity_id": integrity.get("integrity_id"),
                "rehearsal_id": rehearsal.get("rehearsal_id"),
                "verification_id": verifier.get("verification_id"),
                "comparison_id": comparison.get("comparison_id"),
            }
        )
        return {
            "schema_version": "trade_execution_audit_ledger_migration_manual_release_health_digest.v1",
            "status": status,
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "digest_id": digest_id,
            "module_statuses": module_statuses,
            "attention_items": attention_items,
            "health_flags": {
                "release_package_ready": release_package.get("status") == "release_package_ready_for_manual_review",
                "integrity_passed": integrity.get("status") == "integrity_review_passed",
                "rehearsal_ready": rehearsal.get("status") == "manual_release_rehearsal_ready",
                "evidence_verified": verifier.get("status") == "manual_release_evidence_verification_passed",
                "evidence_pair_stable": comparison.get("status") == "manual_release_evidence_comparison_stable",
                "live_trading_disabled": settings.enable_live_trading is False,
                "non_executable": True,
            },
            "summary": {
                "module_count": len(module_statuses),
                "attention_count": len(attention_items),
                "failed_check_count": len(failed_checks),
                "missing_artifact_count": len(verifier.get("missing_artifacts", [])),
                "changed_artifact_hash_count": len(comparison.get("artifact_hash_changes", [])),
                "pending_rehearsal_step_count": len(rehearsal.get("pending_steps", [])),
            },
            "checks": digest_checks,
            "failed_checks": failed_checks,
            "decision": {
                "digest_healthy": status == "manual_release_health_digest_healthy",
                "manual_review_recorded_now": False,
                "release_approved_now": False,
                "migration_allowed_now": False,
                "execution_allowed_now": False,
                "gateway_can_execute": False,
                "go_no_go": "health_digest_ready_for_offline_review" if status == "manual_release_health_digest_healthy" else "no_go",
                "next_required_action": "continue_offline_manual_release_review" if status == "manual_release_health_digest_healthy" else "resolve_manual_release_health_attention_items",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "safety_summary": self._safety_summary()
            | {
                "executes_sql": False,
                "runs_migration_now": False,
                "creates_table_now": False,
                "writes_database_now": False,
                "writes_audit_ledger_row_now": False,
                "writes_migration_file_now": False,
                "writes_file": False,
                "download_created": False,
                "persists_manual_release_evidence": False,
                "persists_manual_release_evidence_comparison": False,
                "persists_manual_release_health_digest": False,
                "mutates_evidence": False,
                "records_manual_review_now": False,
                "approves_release_now": False,
                "enables_gateway_now": False,
                "connects_broker": False,
                "places_real_trade": False,
                "stores_credentials": False,
            },
            "allowed_output": "review_only_manual_release_health_digest",
            "forbidden_actions": [
                "persist_manual_release_health_digest",
                "persist_manual_release_health_digest_history",
                "record_manual_release_review_by_api",
                "approve_release_from_health_digest",
                "execute_migration_from_health_digest",
                "create_health_digest_download",
                "write_health_digest_file",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def audit_ledger_migration_manual_release_health_digest_history_retention_proposal(
        self,
        baseline_evidence: dict[str, Any] | None = None,
        candidate_evidence: dict[str, Any] | None = None,
        limit: int = 50,
        max_age_days: int = 7,
        repeat_checks: int = 2,
    ) -> dict[str, Any]:
        digest = self.audit_ledger_migration_manual_release_health_digest(
            baseline_evidence=baseline_evidence,
            candidate_evidence=candidate_evidence,
            limit=limit,
            max_age_days=max_age_days,
            repeat_checks=repeat_checks,
        )
        retention_fields = [
            "digest_id",
            "digest_status",
            "generated_at",
            "stage",
            "module_statuses",
            "attention_item_names",
            "failed_check_names",
            "release_package_evidence_id",
            "integrity_evidence_id",
            "rehearsal_evidence_id",
            "verification_evidence_id",
            "comparison_evidence_id",
            "health_flags",
            "summary",
            "decision_go_no_go",
            "next_required_action",
            "safety_summary",
        ]
        excluded_fields = [
            "raw_manual_release_evidence",
            "artifact_file_contents",
            "artifact_paths",
            "operator_plaintext_notes",
            "broker_account",
            "broker_credentials",
            "orders",
            "positions",
            "plaintext_secrets",
            "sql_script_body",
            "migration_file_body",
        ]
        module_ids = {item["name"]: item.get("evidence_id") for item in digest.get("module_statuses", [])}
        review_gates = [
            self._manual_release_digest_history_gate(
                "schema_review_required",
                True,
                "Future history retention fields must be reviewed before any persistence is implemented.",
            ),
            self._manual_release_digest_history_gate(
                "metadata_only_required",
                all(field in excluded_fields for field in ["raw_manual_release_evidence", "artifact_file_contents", "broker_credentials", "orders"]),
                "Retention may store only digest metadata and must exclude raw evidence, broker data, orders, credentials, and secrets.",
            ),
            self._manual_release_digest_history_gate(
                "dedupe_policy_required",
                True,
                "Digest history must dedupe by digest id, status, failed checks, and attention item names before future persistence is reviewed.",
            ),
            self._manual_release_digest_history_gate(
                "migration_review_required",
                True,
                "Any future table requires a separately reviewed SQLite migration, rollback plan, and tests.",
            ),
            self._manual_release_digest_history_gate(
                "manual_enable_required",
                True,
                "This proposal must not create a retention job, write records, approve a release, or enable migration execution.",
            ),
            self._manual_release_digest_history_gate(
                "live_trading_disabled",
                settings.enable_live_trading is False and digest.get("live_trading_enabled") is False,
                "Live trading must stay disabled while proposing digest history retention.",
            ),
        ]
        blocked_gates = [gate for gate in review_gates if gate["status"] == "blocked"]
        proposal_id = self._stable_hash(
            {
                "digest_id": digest.get("digest_id"),
                "digest_status": digest.get("status"),
                "retention_fields": retention_fields,
                "excluded_fields": excluded_fields,
                "review_gates": {gate["name"]: gate["status"] for gate in review_gates},
            }
        )
        return {
            "schema_version": "trade_execution_audit_ledger_migration_manual_release_health_digest_history_retention_proposal.v1",
            "status": "history_retention_proposal_ready" if not blocked_gates else "history_retention_proposal_blocked",
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "proposal_id": proposal_id,
            "proposal": {
                "name": "audit_ledger_migration_manual_release_health_digest_history",
                "purpose": "operator_review_only_digest_trend_and_regression_tracking",
                "default_state": "not_persisted",
                "recommended_retention_days": 30,
                "max_records_per_day": 24,
                "dedupe_key": "digest_id + digest_status + failed_check_names + attention_item_names",
                "storage_mode": "future_reviewed_metadata_only_table",
                "required_fields": retention_fields,
                "excluded_fields": excluded_fields,
                "operator_review_required": True,
                "apply_automatically": False,
                "requires_future_migration": True,
                "writes_database_now": False,
                "writes_file": False,
                "download_created": False,
                "executes_commands": False,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "current_digest_summary": {
                "digest_id": digest.get("digest_id"),
                "digest_status": digest.get("status"),
                "digest_stage": digest.get("stage"),
                "module_statuses": {item["name"]: item.get("status") for item in digest.get("module_statuses", [])},
                "attention_item_names": [item["name"] for item in digest.get("attention_items", [])],
                "failed_check_names": [item["name"] for item in digest.get("failed_checks", [])],
                "release_package_evidence_id": module_ids.get("manual_release_package"),
                "integrity_evidence_id": module_ids.get("release_package_integrity"),
                "rehearsal_evidence_id": module_ids.get("manual_release_rehearsal"),
                "verification_evidence_id": module_ids.get("manual_release_evidence_verifier"),
                "comparison_evidence_id": module_ids.get("manual_release_evidence_comparison"),
                "summary": digest.get("summary", {}),
                "health_flags": digest.get("health_flags", {}),
                "decision_go_no_go": digest.get("decision", {}).get("go_no_go"),
                "next_required_action": digest.get("decision", {}).get("next_required_action"),
                "allowed_output": digest.get("allowed_output"),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "review_gates": review_gates,
            "summary": {
                "required_field_count": len(retention_fields),
                "excluded_field_count": len(excluded_fields),
                "blocked_gate_count": len(blocked_gates),
                "attention_item_count": len(digest.get("attention_items", [])),
                "failed_check_count": len(digest.get("failed_checks", [])),
                "writes_database_now": False,
                "persists_history_now": False,
            },
            "decision": {
                "proposal_ready_for_manual_review": not blocked_gates,
                "history_persistence_enabled_now": False,
                "can_create_table_now": False,
                "can_write_history_row_now": False,
                "can_run_migration_now": False,
                "can_write_migration_file_now": False,
                "release_approved_now": False,
                "migration_allowed_now": False,
                "execution_allowed_now": False,
                "gateway_can_execute": False,
                "go_no_go": "ready_for_future_retention_design_review" if not blocked_gates else "no_go",
                "next_required_action": "review_future_digest_history_migration_checklist",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "safety_summary": self._safety_summary()
            | {
                "persists_manual_release_health_digest": False,
                "persists_manual_release_health_digest_history": False,
                "persists_manual_release_evidence": False,
                "persists_manual_release_evidence_comparison": False,
                "writes_database_now": False,
                "creates_table_now": False,
                "writes_history_row_now": False,
                "executes_sql": False,
                "runs_migration_now": False,
                "writes_migration_file_now": False,
                "writes_file": False,
                "download_created": False,
                "executes_commands": False,
                "records_manual_review_now": False,
                "approves_release_now": False,
                "enables_gateway_now": False,
                "connects_broker": False,
                "places_real_trade": False,
                "stores_credentials": False,
            },
            "allowed_output": "review_only_manual_release_health_digest_history_retention_proposal",
            "forbidden_actions": [
                "persist_manual_release_health_digest_history",
                "persist_manual_release_health_digest",
                "persist_manual_release_evidence",
                "create_history_table",
                "write_history_row",
                "run_history_migration",
                "write_migration_file",
                "record_manual_release_review_by_api",
                "approve_release_from_history_proposal",
                "execute_migration_from_history_proposal",
                "create_history_download",
                "write_history_file",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def audit_ledger_migration_manual_release_health_digest_history_migration_readiness_checklist(
        self,
        baseline_evidence: dict[str, Any] | None = None,
        candidate_evidence: dict[str, Any] | None = None,
        limit: int = 50,
        max_age_days: int = 7,
        repeat_checks: int = 2,
    ) -> dict[str, Any]:
        proposal_payload = self.audit_ledger_migration_manual_release_health_digest_history_retention_proposal(
            baseline_evidence=baseline_evidence,
            candidate_evidence=candidate_evidence,
            limit=limit,
            max_age_days=max_age_days,
            repeat_checks=repeat_checks,
        )
        proposal = proposal_payload.get("proposal", {})
        required_fields = list(proposal.get("required_fields", []))
        excluded_fields = list(proposal.get("excluded_fields", []))
        sensitive_exclusions = [
            "raw_manual_release_evidence",
            "artifact_file_contents",
            "broker_credentials",
            "orders",
            "plaintext_secrets",
        ]
        metadata_json_fields = {
            "module_statuses",
            "attention_item_names",
            "failed_check_names",
            "health_flags",
            "summary",
            "safety_summary",
        }
        integer_fields = {"recommended_retention_days", "max_records_per_day"}
        field_mapping = [
            {
                "source_field": field,
                "target_field": field,
                "storage": "metadata_json" if field in metadata_json_fields else "integer" if field in integer_fields else "text",
                "required": True,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }
            for field in required_fields
        ]
        migration_plan = {
            "target_table": "manual_release_health_digest_history",
            "source_schema": proposal_payload.get("schema_version"),
            "source_proposal_id": proposal_payload.get("proposal_id"),
            "source_digest_stage": proposal_payload.get("current_digest_summary", {}).get("digest_stage"),
            "migration_type": "future_reviewed_sqlite_metadata_table",
            "table_exists_now": False,
            "create_table_now": False,
            "backfill_now": False,
            "writes_database_now": False,
            "writes_migration_file_now": False,
            "apply_automatically": False,
            "operator_review_required": True,
            "rollback_required": True,
            "test_required": True,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
        checks = [
            self._manual_release_digest_history_gate(
                "proposal_available",
                proposal_payload.get("status") == "history_retention_proposal_ready",
                "P16 readiness requires the P15 digest history retention proposal to be available and ready.",
            ),
            self._manual_release_digest_history_gate(
                "target_table_defined",
                "health_digest_history" in migration_plan["target_table"],
                "A future target table name must be explicit before drafting any reviewed migration spec.",
            ),
            self._manual_release_digest_history_gate(
                "required_fields_defined",
                len(required_fields) >= 10,
                "Future history migration must map the minimum digest metadata fields.",
            ),
            self._manual_release_digest_history_gate(
                "sensitive_fields_excluded",
                all(field in excluded_fields for field in sensitive_exclusions),
                "Future migration must exclude raw evidence, artifact contents, credentials, orders, and secrets.",
            ),
            self._manual_release_digest_history_gate(
                "retention_policy_defined",
                proposal.get("recommended_retention_days", 0) > 0 and proposal.get("max_records_per_day", 0) > 0,
                "Retention limits must be defined before a future table can be reviewed.",
            ),
            self._manual_release_digest_history_gate(
                "dedupe_key_defined",
                bool(proposal.get("dedupe_key")),
                "A deterministic dedupe key must exist before any future history persistence review.",
            ),
            self._manual_release_digest_history_gate(
                "manual_operator_review_required",
                proposal.get("operator_review_required") is True and proposal.get("apply_automatically") is False,
                "Future migration must require manual operator review and must not apply automatically.",
            ),
            self._manual_release_digest_history_gate(
                "migration_file_required",
                False,
                "A concrete migration file is intentionally not written in P16 and must be drafted in a later reviewed stage.",
                status_if_false="review_required",
            ),
            self._manual_release_digest_history_gate(
                "rollback_plan_required",
                False,
                "A concrete rollback plan is intentionally not attached in P16 and must be reviewed before migration execution.",
                status_if_false="review_required",
            ),
            self._manual_release_digest_history_gate(
                "test_plan_required",
                False,
                "A concrete migration test plan is intentionally not attached in P16 and must be reviewed before migration execution.",
                status_if_false="review_required",
            ),
            self._manual_release_digest_history_gate(
                "persistence_not_enabled_now",
                migration_plan["writes_database_now"] is False and migration_plan["create_table_now"] is False,
                "P16 must remain metadata-only and must not create tables or write history rows.",
            ),
            self._manual_release_digest_history_gate(
                "live_trading_disabled",
                settings.enable_live_trading is False and proposal_payload.get("live_trading_enabled") is False,
                "Live trading must stay disabled while reviewing future digest history migration readiness.",
            ),
        ]
        blocked_checks = [check for check in checks if check["status"] == "blocked"]
        review_required_checks = [check for check in checks if check["status"] == "review_required"]
        checklist_id = self._stable_hash(
            {
                "source_proposal_id": proposal_payload.get("proposal_id"),
                "target_table": migration_plan["target_table"],
                "field_mapping": [item["target_field"] for item in field_mapping],
                "check_statuses": {check["name"]: check["status"] for check in checks},
            }
        )
        status = "history_migration_readiness_review_ready" if not blocked_checks else "history_migration_readiness_blocked"
        return {
            "schema_version": "trade_execution_audit_ledger_migration_manual_release_health_digest_history_migration_readiness_checklist.v1",
            "status": status,
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "checklist_id": checklist_id,
            "source_proposal": {
                "proposal_id": proposal_payload.get("proposal_id"),
                "status": proposal_payload.get("status"),
                "schema_version": proposal_payload.get("schema_version"),
                "allowed_output": proposal_payload.get("allowed_output"),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "migration_plan": migration_plan,
            "field_mapping": field_mapping,
            "excluded_fields": excluded_fields,
            "checks": checks,
            "summary": {
                "check_count": len(checks),
                "passed_check_count": sum(1 for check in checks if check["status"] == "passed"),
                "review_required_count": len(review_required_checks),
                "blocked_check_count": len(blocked_checks),
                "field_mapping_count": len(field_mapping),
                "excluded_field_count": len(excluded_fields),
                "migration_allowed_now": False,
                "manual_review_required": True,
            },
            "decision": {
                "migration_readiness_review_ready": not blocked_checks,
                "history_persistence_enabled_now": False,
                "can_create_table_now": False,
                "can_write_history_row_now": False,
                "can_run_migration_now": False,
                "can_write_migration_file_now": False,
                "release_approved_now": False,
                "migration_allowed_now": False,
                "execution_allowed_now": False,
                "gateway_can_execute": False,
                "go_no_go": "ready_for_future_migration_spec_review" if not blocked_checks else "no_go",
                "next_required_action": "draft_review_only_history_migration_spec",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "safety_summary": self._safety_summary()
            | {
                "persists_manual_release_health_digest": False,
                "persists_manual_release_health_digest_history": False,
                "persists_manual_release_evidence": False,
                "persists_manual_release_evidence_comparison": False,
                "history_persistence_enabled_now": False,
                "writes_database_now": False,
                "creates_table_now": False,
                "writes_history_row_now": False,
                "executes_sql": False,
                "runs_migration_now": False,
                "writes_migration_file_now": False,
                "writes_file": False,
                "download_created": False,
                "executes_commands": False,
                "records_manual_review_now": False,
                "approves_release_now": False,
                "enables_gateway_now": False,
                "connects_broker": False,
                "places_real_trade": False,
                "stores_credentials": False,
            },
            "allowed_output": "review_only_manual_release_health_digest_history_migration_readiness_checklist",
            "forbidden_actions": [
                "create_history_table",
                "write_history_row",
                "run_history_migration",
                "write_migration_file",
                "persist_manual_release_health_digest_history",
                "persist_manual_release_health_digest",
                "persist_manual_release_evidence",
                "execute_sql",
                "approve_release_from_migration_readiness",
                "enable_gateway_from_migration_readiness",
                "connect_broker_from_migration_readiness",
                "create_history_download",
                "write_history_file",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def verify_audit_ledger_migration_manual_release_health_digest_history_migration_spec(
        self,
        spec_text: str | None = None,
        baseline_evidence: dict[str, Any] | None = None,
        candidate_evidence: dict[str, Any] | None = None,
        limit: int = 50,
        max_age_days: int = 7,
        repeat_checks: int = 2,
    ) -> dict[str, Any]:
        checklist = self.audit_ledger_migration_manual_release_health_digest_history_migration_readiness_checklist(
            baseline_evidence=baseline_evidence,
            candidate_evidence=candidate_evidence,
            limit=limit,
            max_age_days=max_age_days,
            repeat_checks=repeat_checks,
        )
        target_table = str(checklist.get("migration_plan", {}).get("target_table") or "manual_release_health_digest_history")
        field_mappings = [
            item
            for item in checklist.get("field_mapping", [])
            if isinstance(item, dict) and item.get("target_field")
        ]
        field_names = [str(item["target_field"]) for item in field_mappings]
        spec = spec_text if spec_text is not None else self._default_manual_release_health_digest_history_migration_spec(field_mappings)
        normalized = " ".join(spec.lower().split())
        dangerous_terms = [
            " drop ",
            " delete ",
            " insert ",
            " update ",
            " alter ",
            " pragma ",
            " attach ",
            " detach ",
            " vacuum ",
            " replace ",
            " truncate ",
            " execute ",
        ]
        sensitive_terms = [
            *[str(field) for field in checklist.get("excluded_fields", [])],
            "broker_account",
            "trading_password",
            "plaintext_secret",
            "account_funds",
            "live_positions",
            "sms_code",
        ]
        missing_fields = [field for field in field_names if field.lower() not in normalized]
        dangerous_matches = [term.strip() for term in dangerous_terms if term in f" {normalized} "]
        sensitive_matches = [term for term in sensitive_terms if term.lower() in normalized]
        checks = [
            self._migration_spec_check(
                "spec_text_present",
                bool(spec.strip()),
                "migration spec text must be provided or generated from the safe default",
            ),
            self._migration_spec_check(
                "target_table_named",
                target_table.lower() in normalized,
                "spec must name the future manual release health digest history target table",
            ),
            self._migration_spec_check(
                "create_table_shape_present",
                "create table" in normalized and "if not exists" in normalized,
                "dry-run spec may describe a guarded CREATE TABLE shape but must not execute it",
            ),
            self._migration_spec_check(
                "required_fields_covered",
                not missing_fields,
                "spec must cover every P15/P16 required metadata field",
                {"missing_fields": missing_fields[:20]},
            ),
            self._migration_spec_check(
                "safety_flags_present",
                all(flag in normalized for flag in ["review_only", "simulation_only", "live_trading_enabled"]),
                "spec must preserve review_only/simulation_only/live_trading_enabled=false evidence columns",
            ),
            self._migration_spec_check(
                "sensitive_fields_absent",
                not sensitive_matches,
                "spec must not include raw evidence, artifact contents, broker data, orders, credentials, secrets, funds, or positions",
                {"sensitive_matches": sensitive_matches},
            ),
            self._migration_spec_check(
                "dangerous_sql_absent",
                not dangerous_matches,
                "dry-run verifier rejects destructive, mutating, attachment, pragma, or execution SQL terms",
                {"dangerous_matches": dangerous_matches},
            ),
            self._migration_spec_check(
                "checklist_review_ready",
                checklist.get("decision", {}).get("migration_readiness_review_ready") is True,
                "P17 verification requires the P16 migration readiness checklist to be review-ready",
            ),
            self._migration_spec_check(
                "migration_not_allowed_now",
                checklist.get("summary", {}).get("migration_allowed_now") is False,
                "dry-run verification must not enable migration execution",
            ),
            self._migration_spec_check(
                "manual_review_required",
                checklist.get("summary", {}).get("manual_review_required") is True,
                "future migration spec still requires manual operator review",
            ),
            self._migration_spec_check(
                "live_trading_disabled",
                settings.enable_live_trading is False and checklist.get("live_trading_enabled") is False,
                "migration spec verification must preserve disabled live-trading state",
            ),
        ]
        failed = [item for item in checks if item["status"] != "passed"]
        spec_hash = hashlib.sha256(spec.encode("utf-8")).hexdigest()
        return {
            "schema_version": "trade_execution_audit_ledger_migration_manual_release_health_digest_history_migration_spec_verifier.v1",
            "status": "spec_verification_passed" if not failed else "spec_verification_failed",
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "verification_state": "dry_run_in_memory_only",
            "target_table": target_table,
            "spec_hash": spec_hash,
            "spec_excerpt": spec[:800],
            "checks": checks,
            "failed_checks": failed,
            "missing_fields": missing_fields,
            "dangerous_matches": dangerous_matches,
            "sensitive_matches": sensitive_matches,
            "safety_blocks": [
                {"name": "dangerous_sql", "matches": dangerous_matches, "blocked": bool(dangerous_matches)},
                {"name": "sensitive_fields", "matches": sensitive_matches, "blocked": bool(sensitive_matches)},
            ],
            "source_checklist_status": checklist.get("status"),
            "migration_allowed_now": False,
            "forbidden_actions": [
                "execute_sql",
                "create_history_table",
                "run_history_migration",
                "write_migration_file",
                "write_history_row",
                "persist_manual_release_health_digest_history",
                "write_file",
                "create_download",
                "approve_release_from_spec_verifier",
                "connect_broker",
                "submit_order",
                "store_credentials",
                "screen_click",
            ],
            "summary": {
                "required_field_count": len(field_names),
                "covered_field_count": len(field_names) - len(missing_fields),
                "dangerous_match_count": len(dangerous_matches),
                "sensitive_match_count": len(sensitive_matches),
                "failed_count": len(failed),
                "executes_sql": False,
                "creates_table_now": False,
                "writes_database_now": False,
                "runs_migration_now": False,
                "writes_migration_file_now": False,
                "writes_history_row_now": False,
            },
            "decision": {
                "spec_verification_ready_for_review": True,
                "spec_verification_passed": not failed,
                "can_execute_sql_now": False,
                "can_create_table_now": False,
                "can_run_migration_now": False,
                "can_write_migration_file_now": False,
                "can_write_history_row_now": False,
                "history_persistence_enabled_now": False,
                "release_approved_now": False,
                "migration_allowed_now": False,
                "execution_allowed_now": False,
                "gateway_can_execute": False,
                "next_required_action": "review_manual_release_health_digest_history_migration_spec_approval_metadata",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "safety_summary": self._safety_summary()
            | {
                "dry_run_verifier_only": True,
                "persists_manual_release_health_digest_history": False,
                "executes_sql": False,
                "creates_table_now": False,
                "writes_database_now": False,
                "runs_migration_now": False,
                "writes_migration_file_now": False,
                "writes_history_row_now": False,
                "writes_file": False,
                "download_created": False,
                "approves_release_now": False,
                "connects_broker": False,
                "places_real_trade": False,
                "stores_credentials": False,
            },
            "allowed_output": "review_only_manual_release_health_digest_history_migration_spec_verifier",
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def approve_audit_ledger_migration_manual_release_health_digest_history_migration_spec(
        self,
        spec_text: str | None = None,
        approved_by: str = "operator",
        note: str | None = None,
        baseline_evidence: dict[str, Any] | None = None,
        candidate_evidence: dict[str, Any] | None = None,
        limit: int = 50,
        max_age_days: int = 7,
        repeat_checks: int = 2,
    ) -> dict[str, Any]:
        verification = self.verify_audit_ledger_migration_manual_release_health_digest_history_migration_spec(
            spec_text=spec_text,
            baseline_evidence=baseline_evidence,
            candidate_evidence=candidate_evidence,
            limit=limit,
            max_age_days=max_age_days,
            repeat_checks=repeat_checks,
        )
        verification_passed = verification.get("status") == "spec_verification_passed"
        failed_count = int(verification.get("summary", {}).get("failed_count") or 0)
        now = datetime.now().isoformat(timespec="seconds")
        approval = {
            "schema_version": "trade_execution_audit_ledger_migration_manual_release_health_digest_history_migration_spec_approval.v1",
            "status": "approval_metadata_recorded" if verification_passed else "approval_blocked",
            "stage": self.stage,
            "approved_at": now,
            "approved_by": (approved_by or "operator")[:80],
            "approval_note": note,
            "approval_effect": "existing_event_metadata_only",
            "spec_hash": verification.get("spec_hash"),
            "verification_status": verification.get("status"),
            "verification_failed_count": failed_count,
            "target_table": verification.get("target_table"),
            "source_checklist_status": verification.get("source_checklist_status"),
            "migration_allowed_now": False,
            "future_migration_still_requires": [
                "reviewed_sqlite_migration_file",
                "operator_release_approval",
                "rollback_plan",
                "migration_unit_tests",
                "api_smoke_tests",
                "manual_release_health_digest_history_release_readiness",
                "forbidden_tracked_file_scan",
                "separate_live_integration_review",
            ],
            "safety_summary": self._safety_summary()
            | {
                "writes_existing_event_now": verification_passed,
                "persists_manual_release_health_digest_history": False,
                "writes_history_row_now": False,
                "creates_table_now": False,
                "runs_migration_now": False,
                "executes_sql": False,
                "writes_migration_file_now": False,
                "writes_file": False,
                "download_created": False,
                "approves_release_now": False,
                "connects_broker": False,
                "places_real_trade": False,
                "stores_credentials": False,
            },
            "allowed_output": "review_only_manual_release_health_digest_history_migration_spec_approval_metadata",
            "forbidden_actions": [
                "execute_sql",
                "run_history_migration",
                "create_history_table",
                "write_migration_file",
                "write_history_row",
                "persist_manual_release_health_digest_history",
                "approve_release_now",
                "enable_gateway_now",
                "connect_broker",
                "submit_order",
                "store_credentials",
                "screen_click",
                "keyboard_type",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
        if not verification_passed:
            approval["event_id"] = None
            approval["verification"] = verification
            return approval

        payload = dict(approval)
        payload["verification"] = {
            "schema_version": verification.get("schema_version"),
            "status": verification.get("status"),
            "spec_hash": verification.get("spec_hash"),
            "failed_count": failed_count,
            "target_table": verification.get("target_table"),
            "source_checklist_status": verification.get("source_checklist_status"),
            "allowed_output": verification.get("allowed_output"),
            "migration_allowed_now": verification.get("migration_allowed_now"),
            "live_trading_enabled": verification.get("live_trading_enabled"),
        }
        with self.store.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO events(event_type, payload_json)
                VALUES (?, ?)
                """,
                (
                    "trade_manual_release_health_digest_history_migration_spec_approval",
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            event_id = int(cursor.lastrowid or 0)
        approval["event_id"] = event_id
        approval["verification"] = payload["verification"]
        return approval

    def list_audit_ledger_migration_manual_release_health_digest_history_migration_spec_approvals(
        self,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            """
            SELECT id, event_type, payload_json, created_at
            FROM events
            WHERE event_type = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (
                "trade_manual_release_health_digest_history_migration_spec_approval",
                max(1, min(limit, 200)),
            ),
        )
        approvals: list[dict[str, Any]] = []
        for row in rows:
            payload = self._decode_json(row.get("payload_json") or "{}")
            item = payload if isinstance(payload, dict) else {}
            item["event_id"] = row.get("id")
            item["event_type"] = row.get("event_type")
            item["created_at"] = row.get("created_at")
            item["review_only"] = True
            item["simulation_only"] = True
            item["live_trading_enabled"] = settings.enable_live_trading
            approvals.append(item)
        return approvals

    def audit_ledger_migration_manual_release_health_digest_history_release_readiness(
        self,
        limit: int = 50,
        max_age_days: int = 7,
        repeat_checks: int = 2,
    ) -> dict[str, Any]:
        proposal = self.audit_ledger_migration_manual_release_health_digest_history_retention_proposal(
            limit=limit,
            max_age_days=max_age_days,
            repeat_checks=repeat_checks,
        )
        checklist = self.audit_ledger_migration_manual_release_health_digest_history_migration_readiness_checklist(
            limit=limit,
            max_age_days=max_age_days,
            repeat_checks=repeat_checks,
        )
        verification = self.verify_audit_ledger_migration_manual_release_health_digest_history_migration_spec(
            limit=limit,
            max_age_days=max_age_days,
            repeat_checks=repeat_checks,
        )
        approvals = self.list_audit_ledger_migration_manual_release_health_digest_history_migration_spec_approvals(
            limit=limit
        )
        latest_approval = approvals[0] if approvals else None
        proposal_ready = proposal.get("status") == "history_retention_proposal_ready"
        checklist_ready = checklist.get("status") == "history_migration_readiness_review_ready"
        verification_ready = verification.get("status") == "spec_verification_passed"
        approval_ready = (
            bool(latest_approval)
            and latest_approval.get("status") == "approval_metadata_recorded"
            and latest_approval.get("verification_status") == "spec_verification_passed"
        )
        approval_matches_spec = bool(latest_approval) and latest_approval.get("spec_hash") == verification.get("spec_hash")
        no_execution_enabled = (
            proposal.get("summary", {}).get("persists_history_now") is False
            and checklist.get("summary", {}).get("migration_allowed_now") is False
            and verification.get("migration_allowed_now") is False
            and (latest_approval or {}).get("migration_allowed_now", False) is False
        )
        safety_ready = (
            proposal.get("safety_summary", {}).get("persists_manual_release_health_digest_history") is False
            and checklist.get("safety_summary", {}).get("runs_migration_now") is False
            and verification.get("safety_summary", {}).get("executes_sql") is False
            and verification.get("safety_summary", {}).get("writes_history_row_now") is False
            and (latest_approval or {}).get("safety_summary", {}).get("runs_migration_now", False) is False
            and (latest_approval or {}).get("safety_summary", {}).get("writes_history_row_now", False) is False
            and not settings.enable_live_trading
        )
        gates = [
            self._release_readiness_gate(
                "history_retention_proposal_ready",
                proposal_ready,
                "V5.5-P15 health digest history retention proposal must be review-ready.",
            ),
            self._release_readiness_gate(
                "migration_checklist_ready",
                checklist_ready,
                "V5.5-P16 migration readiness checklist must be review-ready.",
            ),
            self._release_readiness_gate(
                "migration_spec_verified",
                verification_ready,
                "V5.5-P17 dry-run migration spec verifier must pass.",
            ),
            self._release_readiness_gate(
                "operator_approval_metadata_recorded",
                approval_ready,
                "V5.5-P18 operator approval metadata is required before manual release readiness can be reviewed.",
                status_if_false="review_required",
            ),
            self._release_readiness_gate(
                "latest_approval_matches_current_spec",
                approval_matches_spec,
                "latest approval metadata must match the currently verified history migration spec hash.",
                status_if_false="review_required",
            ),
            self._release_readiness_gate(
                "no_history_migration_execution_enabled",
                no_execution_enabled,
                "release readiness summary must not enable SQL, migrations, table creation, history-row writes, or release approval.",
            ),
            self._release_readiness_gate(
                "safety_summary_clean",
                safety_ready,
                "release readiness summary must preserve no SQL execution, no migration file, no history row, no broker access, and disabled live trading.",
            ),
        ]
        blocked = [gate for gate in gates if gate["status"] == "blocked"]
        review_required = [gate for gate in gates if gate["status"] == "review_required"]
        if blocked:
            status = "release_blocked"
        elif review_required:
            status = "release_review_required"
        else:
            status = "release_evidence_ready"
        return {
            "schema_version": "trade_execution_audit_ledger_migration_manual_release_health_digest_history_release_readiness.v1",
            "status": status,
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "decision": {
                "go_no_go": "go_for_manual_release_review" if status == "release_evidence_ready" else "no_go",
                "migration_allowed_now": False,
                "execution_allowed_now": False,
                "release_approved_now": False,
                "requires_human_release_approval": True,
                "reason": "all history migration evidence gates passed" if status == "release_evidence_ready" else "history migration release evidence is incomplete or requires review",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "evidence": {
                "proposal_status": proposal.get("status"),
                "checklist_status": checklist.get("status"),
                "verification_status": verification.get("status"),
                "verification_failed_count": verification.get("summary", {}).get("failed_count"),
                "approval_count": len(approvals),
                "latest_approval_status": latest_approval.get("status") if latest_approval else None,
                "latest_approval_event_id": latest_approval.get("event_id") if latest_approval else None,
                "target_table": verification.get("target_table"),
                "spec_hash": verification.get("spec_hash"),
                "approved_spec_hash": latest_approval.get("spec_hash") if latest_approval else None,
                "allowed_output": "review_only_manual_release_health_digest_history_release_readiness",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "gates": gates,
            "blocked_gates": blocked,
            "review_required_gates": review_required,
            "required_before_actual_migration": [
                "separate_reviewed_sqlite_migration_file",
                "explicit_operator_release_approval",
                "database_backup_and_restore_drill",
                "rollback_plan_review",
                "migration_unit_tests",
                "api_smoke_tests",
                "history_retention_policy_review",
                "forbidden_tracked_file_scan",
                "separate_live_integration_review",
            ],
            "safety_summary": self._safety_summary()
            | {
                "persists_manual_release_health_digest_history": False,
                "writes_history_row_now": False,
                "creates_table_now": False,
                "runs_migration_now": False,
                "executes_sql": False,
                "writes_database_now": False,
                "writes_migration_file_now": False,
                "writes_file": False,
                "download_created": False,
                "approves_release_now": False,
                "enables_gateway_now": False,
                "connects_broker": False,
                "places_real_trade": False,
                "stores_credentials": False,
            },
            "allowed_output": "review_only_manual_release_health_digest_history_release_readiness",
            "forbidden_actions": [
                "execute_sql",
                "run_history_migration",
                "create_history_table",
                "write_migration_file",
                "write_history_row",
                "persist_manual_release_health_digest_history",
                "write_file",
                "create_download",
                "approve_release_now",
                "enable_gateway_now",
                "connect_broker",
                "submit_order",
                "store_credentials",
                "screen_click",
                "keyboard_type",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def audit_ledger_migration_manual_release_health_digest_history_approval_review(
        self,
        limit: int = 50,
        max_age_days: int = 7,
        repeat_checks: int = 2,
    ) -> dict[str, Any]:
        safe_max_age_days = max(1, min(max_age_days, 365))
        release = self.audit_ledger_migration_manual_release_health_digest_history_release_readiness(
            limit=limit,
            max_age_days=safe_max_age_days,
            repeat_checks=repeat_checks,
        )
        verification = self.verify_audit_ledger_migration_manual_release_health_digest_history_migration_spec(
            limit=limit,
            max_age_days=safe_max_age_days,
            repeat_checks=repeat_checks,
        )
        approvals = self.list_audit_ledger_migration_manual_release_health_digest_history_migration_spec_approvals(
            limit=limit
        )
        latest_approval = approvals[0] if approvals else None
        now = datetime.now()
        approval_time = self._parse_datetime(
            latest_approval.get("approved_at") or latest_approval.get("created_at") if latest_approval else None
        )
        approval_age_hours = round((now - approval_time).total_seconds() / 3600, 3) if approval_time else None
        approval_age_days = round(float(approval_age_hours or 0) / 24, 3) if approval_age_hours is not None else None
        expires_at = (
            (approval_time + timedelta(days=safe_max_age_days)).isoformat(timespec="seconds")
            if approval_time
            else None
        )
        current_spec_hash = verification.get("spec_hash")
        approved_spec_hash = latest_approval.get("spec_hash") if latest_approval else None
        approval_recorded = bool(latest_approval)
        approval_not_expired = bool(approval_time) and approval_age_days is not None and approval_age_days <= safe_max_age_days
        spec_hash_matches = bool(latest_approval) and approved_spec_hash == current_spec_hash
        release_ready = release.get("status") == "release_evidence_ready"
        gates = [
            self._release_readiness_gate(
                "approval_recorded",
                approval_recorded,
                "latest health digest history migration approval metadata must exist before manual release review.",
                status_if_false="review_required",
            ),
            self._release_readiness_gate(
                "approval_within_validity_window",
                approval_not_expired,
                f"health digest history migration approval metadata must be newer than {safe_max_age_days} day(s).",
                status_if_false="review_required",
            ),
            self._release_readiness_gate(
                "approval_matches_current_spec",
                spec_hash_matches,
                "latest approval spec hash must match the currently verified health digest history migration spec hash.",
                status_if_false="review_required",
            ),
            self._release_readiness_gate(
                "release_readiness_evidence_ready",
                release_ready,
                "V5.5-P19 release readiness must be evidence-ready before approval can be treated as current.",
                status_if_false="review_required",
            ),
            self._release_readiness_gate(
                "no_history_migration_execution_enabled",
                release.get("decision", {}).get("migration_allowed_now") is False
                and release.get("decision", {}).get("execution_allowed_now") is False
                and verification.get("migration_allowed_now") is False
                and (latest_approval or {}).get("migration_allowed_now", False) is False,
                "approval review must not enable SQL, migrations, table creation, history-row writes, or release approval.",
            ),
            self._release_readiness_gate(
                "live_trading_disabled",
                not settings.enable_live_trading
                and release.get("live_trading_enabled") is False
                and verification.get("live_trading_enabled") is False,
                "live trading must remain disabled.",
            ),
        ]
        blocked = [gate for gate in gates if gate["status"] == "blocked"]
        review_required = [gate for gate in gates if gate["status"] == "review_required"]
        if blocked:
            status = "approval_review_blocked"
        elif not approval_recorded:
            status = "approval_review_required"
        elif review_required:
            status = "approval_rotation_required"
        else:
            status = "approval_current"
        next_required_action = "none"
        if status == "approval_review_required":
            next_required_action = "record_health_digest_history_migration_spec_approval_metadata"
        elif status == "approval_rotation_required":
            next_required_action = "refresh_health_digest_history_migration_spec_approval_metadata"
        elif status == "approval_review_blocked":
            next_required_action = "resolve_blocked_health_digest_history_release_evidence"
        return {
            "schema_version": "trade_execution_audit_ledger_migration_manual_release_health_digest_history_approval_review.v1",
            "status": status,
            "stage": self.stage,
            "generated_at": now.isoformat(timespec="seconds"),
            "review_policy": {
                "max_age_days": safe_max_age_days,
                "rotation_required_when": [
                    "approval_missing",
                    "approval_expired",
                    "spec_hash_changed",
                    "release_readiness_not_ready",
                ],
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "latest_approval": {
                "event_id": latest_approval.get("event_id") if latest_approval else None,
                "status": latest_approval.get("status") if latest_approval else None,
                "approved_at": latest_approval.get("approved_at") if latest_approval else None,
                "created_at": latest_approval.get("created_at") if latest_approval else None,
                "approved_by": latest_approval.get("approved_by") if latest_approval else None,
                "spec_hash": approved_spec_hash,
                "verification_status": latest_approval.get("verification_status") if latest_approval else None,
                "approval_age_hours": approval_age_hours,
                "approval_age_days": approval_age_days,
                "expires_at": expires_at,
                "is_expired": False if approval_not_expired else bool(latest_approval),
                "matches_current_spec": spec_hash_matches,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "current_spec": {
                "spec_hash": current_spec_hash,
                "verification_status": verification.get("status"),
                "failed_count": verification.get("summary", {}).get("failed_count"),
                "migration_allowed_now": False,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "release_readiness": {
                "status": release.get("status"),
                "go_no_go": release.get("decision", {}).get("go_no_go"),
                "approval_count": release.get("evidence", {}).get("approval_count"),
                "latest_approval_event_id": release.get("evidence", {}).get("latest_approval_event_id"),
                "migration_allowed_now": False,
                "execution_allowed_now": False,
                "release_approved_now": False,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "gates": gates,
            "blocked_gates": blocked,
            "review_required_gates": review_required,
            "decision": {
                "next_required_action": next_required_action,
                "migration_allowed_now": False,
                "execution_allowed_now": False,
                "release_approved_now": False,
                "approval_can_be_reused_for_manual_release_review": status == "approval_current",
                "requires_human_release_approval": True,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "safety_summary": self._safety_summary()
            | {
                "persists_manual_release_health_digest_history": False,
                "writes_history_row_now": False,
                "creates_table_now": False,
                "runs_migration_now": False,
                "executes_sql": False,
                "writes_database_now": False,
                "writes_migration_file_now": False,
                "writes_file": False,
                "download_created": False,
                "approves_release_now": False,
                "enables_gateway_now": False,
                "connects_broker": False,
                "places_real_trade": False,
                "stores_credentials": False,
            },
            "allowed_output": "review_only_manual_release_health_digest_history_approval_review",
            "forbidden_actions": [
                "execute_sql",
                "run_history_migration",
                "create_history_table",
                "write_migration_file",
                "write_history_row",
                "persist_manual_release_health_digest_history",
                "approve_release_now",
                "reuse_expired_approval_as_current",
                "enable_gateway_now",
                "connect_broker",
                "submit_order",
                "store_credentials",
                "screen_click",
                "keyboard_type",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def audit_ledger_migration_manual_release_health_digest_history_release_package(
        self,
        limit: int = 50,
        max_age_days: int = 7,
        repeat_checks: int = 2,
    ) -> dict[str, Any]:
        safe_max_age_days = max(1, min(max_age_days, 365))
        proposal = self.audit_ledger_migration_manual_release_health_digest_history_retention_proposal(
            limit=limit,
            max_age_days=safe_max_age_days,
            repeat_checks=repeat_checks,
        )
        checklist = self.audit_ledger_migration_manual_release_health_digest_history_migration_readiness_checklist(
            limit=limit,
            max_age_days=safe_max_age_days,
            repeat_checks=repeat_checks,
        )
        verification = self.verify_audit_ledger_migration_manual_release_health_digest_history_migration_spec(
            limit=limit,
            max_age_days=safe_max_age_days,
            repeat_checks=repeat_checks,
        )
        approvals = self.list_audit_ledger_migration_manual_release_health_digest_history_migration_spec_approvals(
            limit=limit
        )
        latest_approval = approvals[0] if approvals else None
        release = self.audit_ledger_migration_manual_release_health_digest_history_release_readiness(
            limit=limit,
            max_age_days=safe_max_age_days,
            repeat_checks=repeat_checks,
        )
        approval_review = self.audit_ledger_migration_manual_release_health_digest_history_approval_review(
            limit=limit,
            max_age_days=safe_max_age_days,
            repeat_checks=repeat_checks,
        )
        manifest_items = [
            self._release_package_item(
                "P15_health_digest_history_retention_proposal",
                proposal.get("status"),
                proposal.get("allowed_output"),
                proposal.get("generated_at"),
                proposal.get("status") == "history_retention_proposal_ready"
                and proposal.get("safety_summary", {}).get("persists_manual_release_health_digest_history") is False
                and proposal.get("safety_summary", {}).get("writes_database_now") is False,
            ),
            self._release_package_item(
                "P16_health_digest_history_migration_checklist",
                checklist.get("status"),
                checklist.get("allowed_output"),
                checklist.get("generated_at"),
                checklist.get("status") == "history_migration_readiness_review_ready"
                and checklist.get("summary", {}).get("migration_allowed_now") is False
                and checklist.get("safety_summary", {}).get("runs_migration_now") is False,
            ),
            self._release_package_item(
                "P17_health_digest_history_migration_spec_verifier",
                verification.get("status"),
                verification.get("allowed_output"),
                verification.get("generated_at"),
                verification.get("status") == "spec_verification_passed"
                and verification.get("summary", {}).get("failed_count") == 0
                and verification.get("safety_summary", {}).get("executes_sql") is False,
            ),
            self._release_package_item(
                "P18_health_digest_history_spec_approval_metadata",
                latest_approval.get("status") if latest_approval else "missing",
                latest_approval.get("allowed_output") if latest_approval else "missing",
                latest_approval.get("approved_at") if latest_approval else None,
                bool(latest_approval)
                and latest_approval.get("verification_status") == "spec_verification_passed"
                and latest_approval.get("migration_allowed_now") is False,
            ),
            self._release_package_item(
                "P19_health_digest_history_release_readiness",
                release.get("status"),
                release.get("allowed_output"),
                release.get("generated_at"),
                release.get("status") == "release_evidence_ready"
                and release.get("decision", {}).get("migration_allowed_now") is False
                and release.get("decision", {}).get("release_approved_now") is False,
            ),
            self._release_package_item(
                "P20_health_digest_history_approval_freshness",
                approval_review.get("status"),
                approval_review.get("allowed_output"),
                approval_review.get("generated_at"),
                approval_review.get("status") == "approval_current"
                and approval_review.get("decision", {}).get("migration_allowed_now") is False
                and approval_review.get("decision", {}).get("release_approved_now") is False,
            ),
        ]
        package_id_inputs = {
            "proposal_status": proposal.get("status"),
            "checklist_status": checklist.get("status"),
            "verification_status": verification.get("status"),
            "spec_hash": verification.get("spec_hash"),
            "latest_approval_event_id": latest_approval.get("event_id") if latest_approval else None,
            "latest_approval_spec_hash": latest_approval.get("spec_hash") if latest_approval else None,
            "release_status": release.get("status"),
            "approval_review_status": approval_review.get("status"),
            "max_age_days": safe_max_age_days,
            "repeat_checks": max(1, min(repeat_checks, 10)),
        }
        package_id = self._stable_hash(package_id_inputs)
        gates = [
            self._release_readiness_gate(
                "history_retention_proposal_ready",
                proposal.get("status") == "history_retention_proposal_ready",
                "V5.5-P15 health digest history retention proposal must be ready.",
                status_if_false="review_required",
            ),
            self._release_readiness_gate(
                "history_migration_checklist_ready",
                checklist.get("status") == "history_migration_readiness_review_ready",
                "V5.5-P16 health digest history migration checklist must be review-ready.",
                status_if_false="review_required",
            ),
            self._release_readiness_gate(
                "history_migration_spec_verified",
                verification.get("status") == "spec_verification_passed"
                and verification.get("summary", {}).get("failed_count") == 0,
                "V5.5-P17 health digest history dry-run verifier must pass without failed checks.",
                status_if_false="review_required",
            ),
            self._release_readiness_gate(
                "history_release_readiness_ready",
                release.get("status") == "release_evidence_ready",
                "V5.5-P19 health digest history release readiness must be evidence-ready.",
                status_if_false="review_required",
            ),
            self._release_readiness_gate(
                "history_approval_current",
                approval_review.get("status") == "approval_current",
                "V5.5-P20 approval freshness review must be current before package review.",
                status_if_false="review_required",
            ),
            self._release_readiness_gate(
                "no_history_migration_execution_enabled",
                proposal.get("safety_summary", {}).get("writes_database_now") is False
                and checklist.get("safety_summary", {}).get("runs_migration_now") is False
                and verification.get("safety_summary", {}).get("executes_sql") is False
                and release.get("safety_summary", {}).get("runs_migration_now") is False
                and approval_review.get("safety_summary", {}).get("writes_database_now") is False,
                "release package must not enable SQL, migrations, table creation, history-row writes, or release-file writes.",
            ),
            self._release_readiness_gate(
                "live_trading_disabled",
                not settings.enable_live_trading
                and proposal.get("live_trading_enabled") is False
                and release.get("live_trading_enabled") is False
                and approval_review.get("live_trading_enabled") is False,
                "live trading must remain disabled.",
            ),
        ]
        blocked = [gate for gate in gates if gate["status"] == "blocked"]
        review_required = [gate for gate in gates if gate["status"] == "review_required"]
        if blocked:
            status = "release_package_blocked"
        elif review_required:
            status = "release_package_review_required"
        else:
            status = "release_package_ready_for_manual_review"
        return {
            "schema_version": "trade_execution_audit_ledger_migration_manual_release_health_digest_history_release_package.v1",
            "status": status,
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "package_id": package_id,
            "package_id_inputs": package_id_inputs,
            "manifest": {
                "name": "trade_execution_audit_ledger_migration_manual_release_health_digest_history_package",
                "purpose": "manual review evidence for a future SQLite manual release health digest history migration",
                "items": manifest_items,
                "required_manual_artifacts_before_execution": [
                    "reviewed_sqlite_migration_file",
                    "explicit_operator_release_approval",
                    "database_backup_and_restore_drill",
                    "rollback_plan_review",
                    "migration_unit_tests",
                    "api_smoke_tests",
                    "health_digest_history_retention_policy_review",
                    "spec_hash_freshness_review",
                    "forbidden_tracked_file_scan",
                    "separate_live_integration_review",
                ],
                "delivery": "api_response_only",
                "writes_file": False,
                "download_created": False,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "evidence": {
                "proposal_status": proposal.get("status"),
                "checklist_status": checklist.get("status"),
                "verification_status": verification.get("status"),
                "verification_failed_count": verification.get("summary", {}).get("failed_count"),
                "latest_approval_event_id": latest_approval.get("event_id") if latest_approval else None,
                "latest_approval_status": latest_approval.get("status") if latest_approval else None,
                "release_readiness_status": release.get("status"),
                "approval_review_status": approval_review.get("status"),
                "spec_hash": verification.get("spec_hash"),
                "approved_spec_hash": latest_approval.get("spec_hash") if latest_approval else None,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "gates": gates,
            "blocked_gates": blocked,
            "review_required_gates": review_required,
            "decision": {
                "go_no_go": "ready_for_manual_release_review" if status == "release_package_ready_for_manual_review" else "no_go",
                "migration_allowed_now": False,
                "execution_allowed_now": False,
                "release_approved_now": False,
                "requires_human_release_approval": True,
                "next_required_action": "manual_release_review" if status == "release_package_ready_for_manual_review" else "complete_missing_release_evidence",
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "safety_summary": self._safety_summary()
            | {
                "persists_manual_release_health_digest_history": False,
                "writes_history_row_now": False,
                "creates_table_now": False,
                "runs_migration_now": False,
                "executes_sql": False,
                "writes_database_now": False,
                "writes_migration_file_now": False,
                "writes_file": False,
                "download_created": False,
                "approves_release_now": False,
                "enables_gateway_now": False,
                "connects_broker": False,
                "places_real_trade": False,
                "stores_credentials": False,
            },
            "allowed_output": "review_only_manual_release_health_digest_history_release_package",
            "forbidden_actions": [
                "execute_sql",
                "run_history_migration",
                "create_history_table",
                "write_migration_file",
                "write_history_row",
                "persist_manual_release_health_digest_history",
                "write_release_package_file",
                "create_download",
                "approve_release_now",
                "treat_package_as_release_approval",
                "enable_gateway_now",
                "connect_broker",
                "submit_order",
                "store_credentials",
                "screen_click",
                "keyboard_type",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def audit_ledger_migration_manual_release_health_digest_history_release_package_integrity_review(
        self,
        limit: int = 50,
        max_age_days: int = 7,
        repeat_checks: int = 2,
    ) -> dict[str, Any]:
        safe_repeat_checks = max(2, min(repeat_checks, 5))
        packages = [
            self.audit_ledger_migration_manual_release_health_digest_history_release_package(
                limit=limit,
                max_age_days=max_age_days,
                repeat_checks=safe_repeat_checks,
            )
            for _ in range(safe_repeat_checks)
        ]
        package = packages[0]
        repeated_package_ids = [item.get("package_id") for item in packages]
        manifest = package.get("manifest", {})
        evidence = package.get("evidence", {})
        decision = package.get("decision", {})
        safety_summary = package.get("safety_summary", {})
        items = manifest.get("items", [])
        item_names = [item.get("name") for item in items]
        required_item_names = [
            "P15_health_digest_history_retention_proposal",
            "P16_health_digest_history_migration_checklist",
            "P17_health_digest_history_migration_spec_verifier",
            "P18_health_digest_history_spec_approval_metadata",
            "P19_health_digest_history_release_readiness",
            "P20_health_digest_history_approval_freshness",
        ]
        missing_items = [name for name in required_item_names if name not in item_names]
        duplicate_items = sorted({name for name in item_names if item_names.count(name) > 1})
        required_manual_artifacts = [
            "reviewed_sqlite_migration_file",
            "explicit_operator_release_approval",
            "database_backup_and_restore_drill",
            "rollback_plan_review",
            "migration_unit_tests",
            "api_smoke_tests",
            "health_digest_history_retention_policy_review",
            "spec_hash_freshness_review",
            "forbidden_tracked_file_scan",
            "separate_live_integration_review",
        ]
        missing_manual_artifacts = [
            item
            for item in required_manual_artifacts
            if item not in manifest.get("required_manual_artifacts_before_execution", [])
        ]
        required_forbidden_actions = [
            "execute_sql",
            "run_history_migration",
            "create_history_table",
            "write_migration_file",
            "write_history_row",
            "persist_manual_release_health_digest_history",
            "write_release_package_file",
            "create_download",
            "approve_release_now",
            "treat_package_as_release_approval",
            "enable_gateway_now",
            "connect_broker",
            "submit_order",
            "store_credentials",
            "screen_click",
            "keyboard_type",
        ]
        missing_forbidden_actions = [
            action for action in required_forbidden_actions if action not in package.get("forbidden_actions", [])
        ]
        required_false_safety_fields = [
            "persists_manual_release_health_digest_history",
            "writes_history_row_now",
            "creates_table_now",
            "runs_migration_now",
            "executes_sql",
            "writes_database_now",
            "writes_migration_file_now",
            "writes_file",
            "download_created",
            "approves_release_now",
            "enables_gateway_now",
            "connects_broker",
            "places_real_trade",
            "stores_credentials",
        ]
        unsafe_safety_fields = [
            field for field in required_false_safety_fields if safety_summary.get(field) is not False
        ]
        recomputed_package_id = self._stable_hash(package.get("package_id_inputs", {}))
        checks = [
            self._release_integrity_check(
                "package_id_recomputable",
                recomputed_package_id == package.get("package_id"),
                "package_id must be recomputable from package_id_inputs.",
                {"expected_package_id": recomputed_package_id, "actual_package_id": package.get("package_id")},
            ),
            self._release_integrity_check(
                "package_id_stable_across_reads",
                len(set(repeated_package_ids)) == 1,
                "Repeated API-only package generation must produce the same package_id when source evidence is unchanged.",
                {"repeated_package_ids": repeated_package_ids},
            ),
            self._release_integrity_check(
                "required_manifest_items_present",
                not missing_items and not duplicate_items,
                "Manifest must contain each required P15-P20 evidence item once.",
                {"missing_items": missing_items, "duplicate_items": duplicate_items},
            ),
            self._release_integrity_check(
                "manifest_items_are_review_only",
                all(
                    item.get("included") is True
                    and item.get("review_only") is True
                    and item.get("simulation_only") is True
                    and item.get("live_trading_enabled") is False
                    for item in items
                ),
                "Every manifest item must remain review-only, simulation-only, and live-disabled.",
                {"item_count": len(items)},
            ),
            self._release_integrity_check(
                "manual_artifacts_complete",
                not missing_manual_artifacts,
                "Release package must list required manual artifacts before any future history migration execution review.",
                {"missing_manual_artifacts": missing_manual_artifacts},
            ),
            self._release_integrity_check(
                "api_response_only_delivery",
                manifest.get("delivery") == "api_response_only"
                and manifest.get("writes_file") is False
                and manifest.get("download_created") is False,
                "Release package must stay API-response-only with no file write or download creation.",
                {
                    "delivery": manifest.get("delivery"),
                    "writes_file": manifest.get("writes_file"),
                    "download_created": manifest.get("download_created"),
                },
            ),
            self._release_integrity_check(
                "decision_remains_non_executable",
                decision.get("migration_allowed_now") is False
                and decision.get("execution_allowed_now") is False
                and decision.get("release_approved_now") is False,
                "Integrity review must not convert package evidence into execution, migration, or release approval.",
                {
                    "migration_allowed_now": decision.get("migration_allowed_now"),
                    "execution_allowed_now": decision.get("execution_allowed_now"),
                    "release_approved_now": decision.get("release_approved_now"),
                },
            ),
            self._release_integrity_check(
                "safety_summary_allows_no_mutation",
                not unsafe_safety_fields,
                "Safety summary must explicitly deny SQL, migrations, file writes, history-row writes, gateway enablement, broker actions, and credentials.",
                {"unsafe_safety_fields": unsafe_safety_fields},
            ),
            self._release_integrity_check(
                "forbidden_actions_complete",
                not missing_forbidden_actions,
                "Forbidden actions must include history migration, file, broker, credential, order, and screen-control actions.",
                {"missing_forbidden_actions": missing_forbidden_actions},
            ),
            self._release_integrity_check(
                "evidence_matches_package_inputs",
                package.get("package_id_inputs", {}).get("proposal_status") == evidence.get("proposal_status")
                and package.get("package_id_inputs", {}).get("checklist_status") == evidence.get("checklist_status")
                and package.get("package_id_inputs", {}).get("spec_hash") == evidence.get("spec_hash")
                and package.get("package_id_inputs", {}).get("latest_approval_spec_hash") == evidence.get("approved_spec_hash")
                and package.get("package_id_inputs", {}).get("release_status") == evidence.get("release_readiness_status")
                and package.get("package_id_inputs", {}).get("approval_review_status") == evidence.get("approval_review_status"),
                "Package inputs must trace back to the evidence object that an operator reviews.",
                {"package_id_inputs": package.get("package_id_inputs"), "evidence": evidence},
            ),
            self._release_integrity_check(
                "live_trading_disabled",
                package.get("live_trading_enabled") is False
                and manifest.get("live_trading_enabled") is False
                and evidence.get("live_trading_enabled") is False
                and decision.get("live_trading_enabled") is False
                and not settings.enable_live_trading,
                "Live trading must remain disabled across package, manifest, evidence, and decision.",
                {
                    "package_live_trading_enabled": package.get("live_trading_enabled"),
                    "manifest_live_trading_enabled": manifest.get("live_trading_enabled"),
                    "evidence_live_trading_enabled": evidence.get("live_trading_enabled"),
                    "decision_live_trading_enabled": decision.get("live_trading_enabled"),
                    "settings_live_trading_enabled": settings.enable_live_trading,
                },
            ),
        ]
        failed_checks = [check for check in checks if check["status"] == "failed"]
        release_package_ready = package.get("status") == "release_package_ready_for_manual_review"
        if failed_checks:
            status = "integrity_review_failed"
            next_required_action = "repair_health_digest_history_release_package_integrity"
        elif release_package_ready:
            status = "integrity_review_passed"
            next_required_action = "manual_release_review"
        else:
            status = "integrity_review_passed_release_evidence_pending"
            next_required_action = "complete_missing_release_evidence"
        return {
            "schema_version": "trade_execution_audit_ledger_migration_manual_release_health_digest_history_release_package_integrity_review.v1",
            "status": status,
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source_package_id": package.get("package_id"),
            "source_package_status": package.get("status"),
            "recomputed_package_id": recomputed_package_id,
            "repeat_checks": safe_repeat_checks,
            "repeated_package_ids": repeated_package_ids,
            "checks": checks,
            "failed_checks": failed_checks,
            "failed_check_count": len(failed_checks),
            "manifest_summary": {
                "item_count": len(items),
                "required_item_names": required_item_names,
                "missing_items": missing_items,
                "duplicate_items": duplicate_items,
                "missing_manual_artifacts": missing_manual_artifacts,
                "delivery": manifest.get("delivery"),
                "writes_file": manifest.get("writes_file"),
                "download_created": manifest.get("download_created"),
                "review_only": manifest.get("review_only"),
                "simulation_only": manifest.get("simulation_only"),
                "live_trading_enabled": manifest.get("live_trading_enabled"),
            },
            "decision": {
                "package_id_stable": len(set(repeated_package_ids)) == 1,
                "manifest_integrity_passed": not failed_checks,
                "release_package_ready": release_package_ready,
                "go_no_go": "ready_for_manual_release_review" if status == "integrity_review_passed" else "no_go",
                "migration_allowed_now": False,
                "execution_allowed_now": False,
                "release_approved_now": False,
                "next_required_action": next_required_action,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "safety_summary": self._safety_summary()
            | {
                "persists_manual_release_health_digest_history": False,
                "writes_history_row_now": False,
                "creates_table_now": False,
                "runs_migration_now": False,
                "executes_sql": False,
                "writes_database_now": False,
                "writes_migration_file_now": False,
                "writes_file": False,
                "download_created": False,
                "approves_release_now": False,
                "enables_gateway_now": False,
                "connects_broker": False,
                "places_real_trade": False,
                "stores_credentials": False,
                "mutates_source_package": False,
            },
            "allowed_output": "review_only_manual_release_health_digest_history_release_package_integrity_review",
            "forbidden_actions": package.get("forbidden_actions", [])
            + [
                "mutate_release_package",
                "approve_release_from_integrity_review",
                "persist_integrity_snapshot",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def audit_ledger_migration_manual_release_health_digest_history_release_rehearsal(
        self,
        limit: int = 50,
        max_age_days: int = 7,
        repeat_checks: int = 2,
    ) -> dict[str, Any]:
        integrity = self.audit_ledger_migration_manual_release_health_digest_history_release_package_integrity_review(
            limit=limit,
            max_age_days=max_age_days,
            repeat_checks=repeat_checks,
        )
        integrity_passed = integrity.get("decision", {}).get("manifest_integrity_passed") is True
        release_package_ready = integrity.get("decision", {}).get("release_package_ready") is True
        source_package_id = integrity.get("source_package_id")
        source_package_status = integrity.get("source_package_status")
        manifest_summary = integrity.get("manifest_summary", {})
        missing_manual_artifacts = manifest_summary.get("missing_manual_artifacts", [])
        steps = [
            self._manual_release_rehearsal_step(
                "confirm_health_digest_history_package_identity",
                integrity.get("decision", {}).get("package_id_stable") is True
                and source_package_id == integrity.get("recomputed_package_id"),
                "Operator compares the health digest history package id with the recomputed id and repeated package-id evidence.",
                {"source_package_id": source_package_id, "recomputed_package_id": integrity.get("recomputed_package_id")},
            ),
            self._manual_release_rehearsal_step(
                "review_health_digest_history_integrity_checks",
                integrity_passed and integrity.get("failed_check_count") == 0,
                "Operator reviews all health digest history package integrity checks and confirms no failed checks are present.",
                {"failed_check_count": integrity.get("failed_check_count"), "check_count": len(integrity.get("checks", []))},
            ),
            self._manual_release_rehearsal_step(
                "confirm_health_digest_history_release_evidence_ready",
                release_package_ready,
                "Operator confirms health digest history release package evidence is ready before any future manual release discussion.",
                {"source_package_status": source_package_status},
                pending_reason="Health digest history release package evidence is still pending.",
            ),
            self._manual_release_rehearsal_step(
                "review_health_digest_history_required_manual_artifacts",
                not missing_manual_artifacts,
                "Operator reviews required manual artifacts: migration file review, release approval, backup/restore drill, rollback, tests, retention policy, spec freshness, forbidden-file scan, and separate live integration review.",
                {"missing_manual_artifacts": missing_manual_artifacts},
            ),
            self._manual_release_rehearsal_step(
                "verify_no_api_release_approval",
                integrity.get("decision", {}).get("release_approved_now") is False,
                "Operator confirms this API cannot approve release or convert rehearsal evidence into approval.",
                {"release_approved_now": integrity.get("decision", {}).get("release_approved_now")},
            ),
            self._manual_release_rehearsal_step(
                "verify_no_history_migration_execution",
                integrity.get("decision", {}).get("migration_allowed_now") is False
                and integrity.get("decision", {}).get("execution_allowed_now") is False,
                "Operator confirms rehearsal cannot execute history migrations or trading actions.",
                {
                    "migration_allowed_now": integrity.get("decision", {}).get("migration_allowed_now"),
                    "execution_allowed_now": integrity.get("decision", {}).get("execution_allowed_now"),
                },
            ),
            self._manual_release_rehearsal_step(
                "verify_no_history_persistence_or_download",
                integrity.get("safety_summary", {}).get("writes_file") is False
                and integrity.get("safety_summary", {}).get("download_created") is False
                and integrity.get("safety_summary", {}).get("writes_database_now") is False
                and integrity.get("safety_summary", {}).get("writes_history_row_now") is False,
                "Operator confirms rehearsal returns API metadata only and does not persist review snapshots, history rows, or downloads.",
                {
                    "writes_file": integrity.get("safety_summary", {}).get("writes_file"),
                    "download_created": integrity.get("safety_summary", {}).get("download_created"),
                    "writes_database_now": integrity.get("safety_summary", {}).get("writes_database_now"),
                    "writes_history_row_now": integrity.get("safety_summary", {}).get("writes_history_row_now"),
                },
            ),
            self._manual_release_rehearsal_step(
                "verify_live_trading_disabled",
                integrity.get("live_trading_enabled") is False and not settings.enable_live_trading,
                "Operator confirms live trading stays disabled during health digest history rehearsal.",
                {
                    "integrity_live_trading_enabled": integrity.get("live_trading_enabled"),
                    "settings_live_trading_enabled": settings.enable_live_trading,
                },
            ),
        ]
        pending_steps = [step for step in steps if step["status"] == "pending_evidence"]
        failed_steps = [step for step in steps if step["status"] == "blocked"]
        if failed_steps:
            status = "manual_release_rehearsal_blocked"
            next_required_action = "repair_health_digest_history_rehearsal_blockers"
        elif pending_steps:
            status = "manual_release_rehearsal_waiting_for_evidence"
            next_required_action = "complete_missing_release_evidence"
        else:
            status = "manual_release_rehearsal_ready"
            next_required_action = "perform_offline_manual_release_review"
        rehearsal_id = self._stable_hash(
            {
                "source_package_id": source_package_id,
                "integrity_status": integrity.get("status"),
                "source_package_status": source_package_status,
                "step_statuses": {step["name"]: step["status"] for step in steps},
                "max_age_days": max(1, min(max_age_days, 365)),
            }
        )
        return {
            "schema_version": "trade_execution_audit_ledger_migration_manual_release_health_digest_history_release_rehearsal.v1",
            "status": status,
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "rehearsal_id": rehearsal_id,
            "source_package_id": source_package_id,
            "source_package_status": source_package_status,
            "integrity_status": integrity.get("status"),
            "steps": steps,
            "pending_steps": pending_steps,
            "failed_steps": failed_steps,
            "operator_rehearsal_policy": {
                "api_can_record_operator_review": False,
                "api_can_mark_rehearsal_complete": False,
                "api_can_approve_release": False,
                "api_can_execute_migration": False,
                "offline_human_review_required": True,
                "dual_control_required_before_future_execution": True,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "required_offline_artifacts": [
                "signed_manual_release_health_digest_history_review",
                "reviewed_sqlite_migration_file",
                "database_backup_and_restore_drill_evidence",
                "rollback_plan_signoff",
                "migration_test_report",
                "api_smoke_report",
                "health_digest_history_retention_policy_signoff",
                "spec_hash_freshness_signoff",
                "forbidden_tracked_file_scan_report",
                "separate_live_integration_review",
            ],
            "decision": {
                "rehearsal_ready_for_operator": status == "manual_release_rehearsal_ready",
                "manual_review_recorded_now": False,
                "release_approved_now": False,
                "migration_allowed_now": False,
                "execution_allowed_now": False,
                "gateway_can_execute": False,
                "go_no_go": "ready_for_offline_manual_review" if status == "manual_release_rehearsal_ready" else "no_go",
                "next_required_action": next_required_action,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "safety_summary": self._safety_summary()
            | {
                "executes_sql": False,
                "runs_migration_now": False,
                "creates_table_now": False,
                "writes_database_now": False,
                "writes_history_row_now": False,
                "writes_migration_file_now": False,
                "writes_file": False,
                "download_created": False,
                "records_manual_review_now": False,
                "marks_rehearsal_complete_now": False,
                "approves_release_now": False,
                "enables_gateway_now": False,
                "connects_broker": False,
                "places_real_trade": False,
                "stores_credentials": False,
            },
            "allowed_output": "review_only_manual_release_health_digest_history_release_rehearsal",
            "forbidden_actions": integrity.get("forbidden_actions", [])
            + [
                "record_manual_release_review_by_api",
                "mark_rehearsal_complete_by_api",
                "approve_release_from_rehearsal",
                "execute_migration_from_rehearsal",
                "persist_rehearsal_snapshot",
            ],
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def verify_audit_ledger_migration_manual_release_health_digest_history_release_evidence(
        self,
        evidence: dict[str, Any] | None = None,
        limit: int = 50,
        max_age_days: int = 7,
        repeat_checks: int = 2,
    ) -> dict[str, Any]:
        rehearsal = self.audit_ledger_migration_manual_release_health_digest_history_release_rehearsal(
            limit=limit,
            max_age_days=max_age_days,
            repeat_checks=repeat_checks,
        )
        payload = evidence or {}
        artifacts = payload.get("artifacts") if isinstance(payload, dict) else None
        artifact_list = artifacts if isinstance(artifacts, list) else []
        artifacts_by_name = {
            str(item.get("name")): item
            for item in artifact_list
            if isinstance(item, dict) and item.get("name")
        }
        artifact_names = [
            str(item.get("name"))
            for item in artifact_list
            if isinstance(item, dict) and item.get("name")
        ]
        required_artifacts = list(rehearsal.get("required_offline_artifacts", []))
        missing_artifacts = [name for name in required_artifacts if name not in artifacts_by_name]
        duplicate_artifacts = sorted({name for name in artifact_names if artifact_names.count(name) > 1})
        artifacts_missing_hash = [
            name
            for name, item in artifacts_by_name.items()
            if item.get("present") is not True
            or not isinstance(item.get("artifact_hash"), str)
            or len(item.get("artifact_hash", "")) < 16
        ]
        artifacts_missing_review = [
            name
            for name, item in artifacts_by_name.items()
            if not item.get("reviewed_by") or not item.get("reviewed_at")
        ]
        forbidden_evidence_fields = [
            "sql_text",
            "shell_command",
            "broker_credentials",
            "trading_password",
            "account_funds",
            "live_positions",
            "order_action",
            "screen_click",
            "raw_health_digest_history",
            "database_path",
        ]
        forbidden_field_hits = sorted(
            {
                field
                for item in artifact_list
                if isinstance(item, dict)
                for field in forbidden_evidence_fields
                if field in item
            }
        )
        checks = [
            self._manual_release_evidence_check(
                "health_digest_history_rehearsal_ready",
                rehearsal.get("status") == "manual_release_rehearsal_ready",
                "Health digest history release evidence can only pass after the rehearsal is ready for offline operator review.",
                {"rehearsal_status": rehearsal.get("status")},
            ),
            self._manual_release_evidence_check(
                "source_package_id_matches",
                payload.get("source_package_id") == rehearsal.get("source_package_id"),
                "Evidence must reference the current health digest history release package id.",
                {
                    "expected_source_package_id": rehearsal.get("source_package_id"),
                    "actual_source_package_id": payload.get("source_package_id"),
                },
            ),
            self._manual_release_evidence_check(
                "rehearsal_id_matches",
                payload.get("rehearsal_id") == rehearsal.get("rehearsal_id"),
                "Evidence must reference the current health digest history release rehearsal id.",
                {
                    "expected_rehearsal_id": rehearsal.get("rehearsal_id"),
                    "actual_rehearsal_id": payload.get("rehearsal_id"),
                },
            ),
            self._manual_release_evidence_check(
                "required_artifacts_present_once",
                not missing_artifacts and not duplicate_artifacts,
                "All required offline health digest history release artifacts must be represented exactly once.",
                {"missing_artifacts": missing_artifacts, "duplicate_artifacts": duplicate_artifacts},
            ),
            self._manual_release_evidence_check(
                "artifact_hashes_present",
                not artifacts_missing_hash and len(artifacts_by_name) >= len(required_artifacts),
                "Every health digest history release artifact must be marked present and carry a non-empty evidence hash.",
                {"artifacts_missing_hash": artifacts_missing_hash},
            ),
            self._manual_release_evidence_check(
                "artifact_reviews_present",
                not artifacts_missing_review and len(artifacts_by_name) >= len(required_artifacts),
                "Every health digest history release artifact must include offline reviewer and review timestamp metadata.",
                {"artifacts_missing_review": artifacts_missing_review},
            ),
            self._manual_release_evidence_check(
                "no_forbidden_evidence_fields",
                not forbidden_field_hits,
                "Evidence payload must not contain SQL text, shell commands, broker credentials, account data, order actions, screen-control fields, raw history snapshots, or database paths.",
                {"forbidden_field_hits": forbidden_field_hits},
            ),
            self._manual_release_evidence_check(
                "payload_safety_flags",
                payload.get("review_only") is True
                and payload.get("simulation_only") is True
                and payload.get("live_trading_enabled") is False,
                "Evidence payload must keep review-only, simulation-only, and live-trading-disabled flags.",
                {
                    "review_only": payload.get("review_only"),
                    "simulation_only": payload.get("simulation_only"),
                    "live_trading_enabled": payload.get("live_trading_enabled"),
                },
            ),
            self._manual_release_evidence_check(
                "verifier_remains_non_executable",
                rehearsal.get("decision", {}).get("release_approved_now") is False
                and rehearsal.get("decision", {}).get("migration_allowed_now") is False
                and rehearsal.get("decision", {}).get("execution_allowed_now") is False,
                "Verifier must not convert evidence into release approval, migration permission, or execution.",
                {
                    "release_approved_now": rehearsal.get("decision", {}).get("release_approved_now"),
                    "migration_allowed_now": rehearsal.get("decision", {}).get("migration_allowed_now"),
                    "execution_allowed_now": rehearsal.get("decision", {}).get("execution_allowed_now"),
                },
            ),
            self._manual_release_evidence_check(
                "live_trading_disabled",
                rehearsal.get("live_trading_enabled") is False and not settings.enable_live_trading,
                "Live trading must remain disabled while verifying health digest history release evidence.",
                {
                    "rehearsal_live_trading_enabled": rehearsal.get("live_trading_enabled"),
                    "settings_live_trading_enabled": settings.enable_live_trading,
                },
            ),
        ]
        failed_checks = [check for check in checks if check["status"] == "failed"]
        if not artifact_list:
            status = "manual_release_health_digest_history_evidence_missing"
            next_required_action = "collect_offline_health_digest_history_release_artifacts"
        elif failed_checks:
            status = "manual_release_health_digest_history_evidence_verification_failed"
            next_required_action = "repair_health_digest_history_release_evidence"
        else:
            status = "manual_release_health_digest_history_evidence_verification_passed"
            next_required_action = "offline_health_digest_history_release_review_can_continue"
        verification_id = self._stable_hash(
            {
                "source_package_id": rehearsal.get("source_package_id"),
                "rehearsal_id": rehearsal.get("rehearsal_id"),
                "artifact_names": sorted(artifacts_by_name),
                "check_statuses": {check["name"]: check["status"] for check in checks},
                "payload_review_only": payload.get("review_only"),
                "payload_simulation_only": payload.get("simulation_only"),
                "payload_live_trading_enabled": payload.get("live_trading_enabled"),
            }
        )
        return {
            "schema_version": "trade_execution_audit_ledger_migration_manual_release_health_digest_history_release_evidence_verifier.v1",
            "status": status,
            "stage": self.stage,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "verification_id": verification_id,
            "source_package_id": rehearsal.get("source_package_id"),
            "rehearsal_id": rehearsal.get("rehearsal_id"),
            "rehearsal_status": rehearsal.get("status"),
            "required_artifacts": required_artifacts,
            "provided_artifact_names": sorted(artifacts_by_name),
            "missing_artifacts": missing_artifacts,
            "duplicate_artifacts": duplicate_artifacts,
            "checks": checks,
            "failed_checks": failed_checks,
            "failed_check_count": len(failed_checks),
            "decision": {
                "evidence_complete": status == "manual_release_health_digest_history_evidence_verification_passed",
                "manual_review_recorded_now": False,
                "release_approved_now": False,
                "migration_allowed_now": False,
                "execution_allowed_now": False,
                "gateway_can_execute": False,
                "go_no_go": "evidence_complete_for_offline_review"
                if status == "manual_release_health_digest_history_evidence_verification_passed"
                else "no_go",
                "next_required_action": next_required_action,
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            },
            "safety_summary": self._safety_summary()
            | {
                "executes_sql": False,
                "runs_migration_now": False,
                "creates_table_now": False,
                "writes_database_now": False,
                "writes_history_row_now": False,
                "writes_migration_file_now": False,
                "writes_file": False,
                "download_created": False,
                "persists_manual_release_health_digest_history_evidence": False,
                "records_manual_review_now": False,
                "approves_release_now": False,
                "enables_gateway_now": False,
                "connects_broker": False,
                "places_real_trade": False,
                "stores_credentials": False,
            },
            "allowed_output": "review_only_manual_release_health_digest_history_evidence_verification",
            "forbidden_actions": rehearsal.get("forbidden_actions", [])
            + [
                "persist_manual_release_health_digest_history_evidence",
                "record_manual_release_review_by_api",
                "approve_release_from_health_digest_history_evidence_verifier",
                "execute_migration_from_health_digest_history_evidence_verifier",
                "create_health_digest_history_evidence_download",
            ],
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
                "V5.5-P13 preserves threat categories and mitigations without implementing broker connectivity.",
            ),
            self._gate(
                "broker_adapter_interface_draft_required",
                "passed",
                "broker_adapter_interface_draft_review_ready",
                "future_broker_adapter_interface_draft",
                "V5.5-P13 preserves provider-neutral interface metadata without executable adapter methods.",
            ),
            self._gate(
                "broker_adapter_contract_verification_required",
                "passed",
                "fixture_contract_verification_passed",
                "fixture_only_broker_adapter_contract_verifier",
                "V5.5-P13 preserves fixture contract verification with no broker connectivity.",
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
            self._gate(
                "disabled_audit_ledger_storage_plan_required",
                "passed",
                "disabled_audit_ledger_storage_plan_ready",
                "review_only_audit_ledger_storage_plan",
                "V5.5-P4 defines future audit ledger storage without creating tables, writing rows, or running migrations.",
            ),
            self._gate(
                "audit_ledger_migration_spec_dry_run_required",
                "passed",
                "audit_ledger_migration_spec_dry_run_passed",
                "review_only_audit_ledger_migration_spec_verifier",
                "V5.5-P5 verifies the future audit ledger migration spec in memory without executing SQL or writing files.",
            ),
            self._gate(
                "audit_ledger_migration_spec_approval_metadata_required",
                "passed",
                "audit_ledger_migration_spec_approval_metadata_ready",
                "review_only_existing_event_metadata",
                "V5.5-P6 can record operator approval metadata for a verified spec in existing events without running migrations or writing audit ledger rows.",
            ),
            self._gate(
                "audit_ledger_migration_release_readiness_required",
                "passed",
                "audit_ledger_migration_release_readiness_summary_ready",
                "review_only_release_readiness_summary",
                "V5.5-P7 summarizes storage plan, dry-run verification, and approval metadata for manual release review without approving or executing migrations.",
            ),
            self._gate(
                "audit_ledger_migration_approval_freshness_required",
                "passed",
                "audit_ledger_migration_approval_freshness_ready",
                "review_only_approval_freshness_review",
                "V5.5-P8 reviews approval freshness, expiry, and spec-hash rotation without approving releases or executing migrations.",
            ),
            self._gate(
                "audit_ledger_migration_manual_release_package_required",
                "passed",
                "audit_ledger_migration_manual_release_package_ready",
                "review_only_manual_release_package_manifest",
                "V5.5-P9 aggregates audit ledger migration evidence into an API-only manual release package manifest without writing files or enabling execution.",
            ),
            self._gate(
                "audit_ledger_migration_release_package_integrity_review_required",
                "passed",
                "audit_ledger_migration_release_package_integrity_review_ready",
                "review_only_release_package_integrity_review",
                "V5.5-P10 verifies package-id stability, manifest completeness, safety flags, and evidence traceability without approving releases or mutating package evidence.",
            ),
            self._gate(
                "audit_ledger_migration_manual_release_rehearsal_required",
                "passed",
                "audit_ledger_migration_manual_release_rehearsal_ready",
                "review_only_manual_release_review_rehearsal",
                "V5.5-P11 rehearses the offline manual release review checklist without recording approval, marking completion, or executing migrations.",
            ),
            self._gate(
                "audit_ledger_migration_manual_release_evidence_verifier_required",
                "passed",
                "audit_ledger_migration_manual_release_evidence_verifier_ready",
                "review_only_manual_release_evidence_verifier",
                "V5.5-P12 verifies offline manual release evidence payloads in memory without persisting evidence, approving release, or executing migrations.",
            ),
            self._gate(
                "audit_ledger_migration_manual_release_evidence_comparison_required",
                "passed",
                "audit_ledger_migration_manual_release_evidence_comparison_ready",
                "review_only_manual_release_evidence_comparison",
                "V5.5-P13 compares two manual release evidence verifier summaries in memory without persisting snapshots, approving release, or executing migrations.",
            ),
            self._gate(
                "audit_ledger_migration_manual_release_health_digest_required",
                "passed",
                "audit_ledger_migration_manual_release_health_digest_ready",
                "review_only_manual_release_health_digest",
                "V5.5-P14 summarizes manual release package, integrity, rehearsal, verifier, comparison, and safety flags without persisting snapshots, approving release, or executing migrations.",
            ),
            self._gate(
                "audit_ledger_migration_manual_release_health_digest_history_retention_proposal_required",
                "passed",
                "audit_ledger_migration_manual_release_health_digest_history_retention_proposal_ready",
                "review_only_manual_release_health_digest_history_retention_proposal",
                "V5.5-P15 proposes metadata-only future health digest history retention without creating tables, writing records, or running migrations.",
            ),
            self._gate(
                "audit_ledger_migration_manual_release_health_digest_history_migration_readiness_checklist_required",
                "passed",
                "audit_ledger_migration_manual_release_health_digest_history_migration_readiness_checklist_ready",
                "review_only_manual_release_health_digest_history_migration_readiness_checklist",
                "V5.5-P16 checks future health digest history migration readiness without creating tables, writing rows, writing files, or running migrations.",
            ),
            self._gate(
                "audit_ledger_migration_manual_release_health_digest_history_migration_spec_verifier_required",
                "passed",
                "audit_ledger_migration_manual_release_health_digest_history_migration_spec_verifier_ready",
                "review_only_manual_release_health_digest_history_migration_spec_verifier",
                "V5.5-P17 dry-run verifies future health digest history migration specs in memory without executing SQL, writing files, creating tables, or writing history rows.",
            ),
            self._gate(
                "audit_ledger_migration_manual_release_health_digest_history_migration_spec_approval_metadata_required",
                "passed",
                "audit_ledger_migration_manual_release_health_digest_history_migration_spec_approval_metadata_ready",
                "review_only_manual_release_health_digest_history_migration_spec_approval_metadata",
                "V5.5-P18 can record operator approval metadata for verified history migration specs in existing events without executing SQL, writing files, creating tables, or writing history rows.",
            ),
            self._gate(
                "audit_ledger_migration_manual_release_health_digest_history_release_readiness_required",
                "passed",
                "audit_ledger_migration_manual_release_health_digest_history_release_readiness_ready",
                "review_only_manual_release_health_digest_history_release_readiness",
                "V5.5-P19 summarizes P15-P18 health digest history migration evidence for manual release review without approving or executing migrations.",
            ),
            self._gate(
                "audit_ledger_migration_manual_release_health_digest_history_approval_freshness_required",
                "passed",
                "audit_ledger_migration_manual_release_health_digest_history_approval_freshness_ready",
                "review_only_manual_release_health_digest_history_approval_freshness_review",
                "V5.5-P20 reviews history migration approval freshness, expiry, and spec-hash rotation without approving releases or executing migrations.",
            ),
            self._gate(
                "audit_ledger_migration_manual_release_health_digest_history_release_package_required",
                "passed",
                "audit_ledger_migration_manual_release_health_digest_history_release_package_ready",
                "review_only_manual_release_health_digest_history_release_package",
                "V5.5-P21 packages P15-P20 health digest history migration evidence into an API-only manifest without writing files, approving releases, or executing migrations.",
            ),
            self._gate(
                "audit_ledger_migration_manual_release_health_digest_history_release_package_integrity_review_required",
                "passed",
                "audit_ledger_migration_manual_release_health_digest_history_release_package_integrity_review_ready",
                "review_only_manual_release_health_digest_history_release_package_integrity_review",
                "V5.5-P22 verifies P21 package-id stability, manifest completeness, safety flags, and evidence traceability without approving releases or mutating package evidence.",
            ),
            self._gate(
                "audit_ledger_migration_manual_release_health_digest_history_release_rehearsal_required",
                "passed",
                "audit_ledger_migration_manual_release_health_digest_history_release_rehearsal_ready",
                "review_only_manual_release_health_digest_history_release_rehearsal",
                "V5.5-P23 rehearses the offline manual review checklist for health digest history migration without recording approval, marking completion, or executing migrations.",
            ),
            self._gate(
                "audit_ledger_migration_manual_release_health_digest_history_release_evidence_verifier_required",
                "passed",
                "audit_ledger_migration_manual_release_health_digest_history_release_evidence_verifier_ready",
                "review_only_manual_release_health_digest_history_evidence_verification",
                "V5.5-P24 verifies offline health digest history release evidence payloads in memory without persisting evidence, approving release, or executing migrations.",
            ),
        ]
        blocked = any(gate["status"] == "blocked" for gate in gates)
        review_required = any(gate["status"] == "review_required" for gate in gates)
        return {
            "schema_version": "trade_execution_gateway_review_gates.v1",
            "status": "blocked_by_safety_gate" if blocked else "audit_ledger_migration_manual_release_health_digest_history_release_evidence_verifier_ready" if not review_required else "review_required",
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
                "disabled_audit_ledger_storage_plan_ready": True,
                "audit_ledger_migration_spec_dry_run_ready": True,
                "audit_ledger_migration_spec_approval_metadata_ready": True,
                "audit_ledger_migration_release_readiness_ready": True,
                "audit_ledger_migration_approval_freshness_ready": True,
                "audit_ledger_migration_manual_release_package_ready": True,
                "audit_ledger_migration_release_package_integrity_review_ready": True,
                "audit_ledger_migration_manual_release_rehearsal_ready": True,
                "audit_ledger_migration_manual_release_evidence_verifier_ready": True,
                "audit_ledger_migration_manual_release_evidence_comparison_ready": True,
                "audit_ledger_migration_manual_release_health_digest_ready": True,
                "audit_ledger_migration_manual_release_health_digest_history_retention_proposal_ready": True,
                "audit_ledger_migration_manual_release_health_digest_history_migration_readiness_checklist_ready": True,
                "audit_ledger_migration_manual_release_health_digest_history_migration_spec_verifier_ready": True,
                "audit_ledger_migration_manual_release_health_digest_history_migration_spec_approval_metadata_ready": True,
                "audit_ledger_migration_manual_release_health_digest_history_release_readiness_ready": True,
                "audit_ledger_migration_manual_release_health_digest_history_approval_freshness_ready": True,
                "audit_ledger_migration_manual_release_health_digest_history_release_package_ready": True,
                "audit_ledger_migration_manual_release_health_digest_history_release_package_integrity_review_ready": True,
                "audit_ledger_migration_manual_release_health_digest_history_release_rehearsal_ready": True,
                "audit_ledger_migration_manual_release_health_digest_history_release_evidence_verifier_ready": True,
                "ready_for_live_enablement": False,
                "live_trading_enabled": settings.enable_live_trading,
                "next_required_action": "review_audit_ledger_migration_manual_release_health_digest_history_release_evidence_verifier",
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
            {
                "name": "DisabledAuditLedgerStoragePlan",
                "status": "review_storage_plan_defined_not_persisted",
                "required_before": "any_audit_ledger_migration",
                "review_only": True,
            },
            {
                "name": "AuditLedgerMigrationSpecDryRunVerifier",
                "status": "review_dry_run_spec_verifier_defined",
                "required_before": "any_audit_ledger_migration_approval",
                "review_only": True,
            },
            {
                "name": "AuditLedgerMigrationSpecApprovalMetadata",
                "status": "review_approval_metadata_defined_existing_events_only",
                "required_before": "any_audit_ledger_migration_release_summary",
                "review_only": True,
            },
            {
                "name": "AuditLedgerMigrationReleaseReadinessSummary",
                "status": "review_release_readiness_summary_defined",
                "required_before": "any_manual_audit_ledger_migration_release_review",
                "review_only": True,
            },
            {
                "name": "AuditLedgerMigrationApprovalFreshnessReview",
                "status": "review_approval_freshness_defined",
                "required_before": "any_reuse_of_audit_ledger_migration_approval",
                "review_only": True,
            },
            {
                "name": "AuditLedgerMigrationManualReleasePackageManifest",
                "status": "review_manual_release_package_defined",
                "required_before": "any_manual_audit_ledger_migration_release",
                "review_only": True,
            },
            {
                "name": "AuditLedgerMigrationReleasePackageIntegrityReview",
                "status": "review_release_package_integrity_defined",
                "required_before": "any_manual_audit_ledger_migration_release",
                "review_only": True,
            },
            {
                "name": "AuditLedgerMigrationManualReleaseReviewRehearsal",
                "status": "review_manual_release_rehearsal_defined",
                "required_before": "any_manual_audit_ledger_migration_release",
                "review_only": True,
            },
            {
                "name": "AuditLedgerMigrationManualReleaseEvidenceVerifier",
                "status": "review_manual_release_evidence_verifier_defined",
                "required_before": "any_manual_audit_ledger_migration_release",
                "review_only": True,
            },
            {
                "name": "AuditLedgerMigrationManualReleaseEvidenceComparison",
                "status": "review_manual_release_evidence_comparison_defined",
                "required_before": "any_manual_audit_ledger_migration_release",
                "review_only": True,
            },
            {
                "name": "AuditLedgerMigrationManualReleaseHealthDigest",
                "status": "review_manual_release_health_digest_defined",
                "required_before": "any_manual_audit_ledger_migration_release",
                "review_only": True,
            },
            {
                "name": "AuditLedgerMigrationManualReleaseHealthDigestHistoryRetentionProposal",
                "status": "review_manual_release_health_digest_history_retention_proposal_defined",
                "required_before": "any_manual_release_health_digest_history_persistence",
                "review_only": True,
            },
            {
                "name": "AuditLedgerMigrationManualReleaseHealthDigestHistoryMigrationReadinessChecklist",
                "status": "review_manual_release_health_digest_history_migration_readiness_checklist_defined",
                "required_before": "any_manual_release_health_digest_history_migration_spec",
                "review_only": True,
            },
            {
                "name": "AuditLedgerMigrationManualReleaseHealthDigestHistoryMigrationSpecVerifier",
                "status": "review_manual_release_health_digest_history_migration_spec_verifier_defined",
                "required_before": "any_manual_release_health_digest_history_migration_spec_approval",
                "review_only": True,
            },
            {
                "name": "AuditLedgerMigrationManualReleaseHealthDigestHistoryMigrationSpecApprovalMetadata",
                "status": "review_manual_release_health_digest_history_migration_spec_approval_metadata_defined",
                "required_before": "any_manual_release_health_digest_history_release_readiness",
                "review_only": True,
            },
            {
                "name": "AuditLedgerMigrationManualReleaseHealthDigestHistoryReleaseReadiness",
                "status": "review_manual_release_health_digest_history_release_readiness_defined",
                "required_before": "any_manual_release_health_digest_history_approval_freshness_review",
                "review_only": True,
            },
            {
                "name": "AuditLedgerMigrationManualReleaseHealthDigestHistoryApprovalFreshnessReview",
                "status": "review_manual_release_health_digest_history_approval_freshness_defined",
                "required_before": "any_manual_release_health_digest_history_release_package",
                "review_only": True,
            },
            {
                "name": "AuditLedgerMigrationManualReleaseHealthDigestHistoryReleasePackageManifest",
                "status": "review_manual_release_health_digest_history_release_package_defined",
                "required_before": "any_manual_release_health_digest_history_release_package_integrity_review",
                "review_only": True,
            },
            {
                "name": "AuditLedgerMigrationManualReleaseHealthDigestHistoryReleasePackageIntegrityReview",
                "status": "review_manual_release_health_digest_history_release_package_integrity_defined",
                "required_before": "any_manual_release_health_digest_history_release_rehearsal",
                "review_only": True,
            },
            {
                "name": "AuditLedgerMigrationManualReleaseHealthDigestHistoryReleaseRehearsal",
                "status": "review_manual_release_health_digest_history_release_rehearsal_defined",
                "required_before": "any_manual_release_health_digest_history_release_evidence_verification",
                "review_only": True,
            },
            {
                "name": "AuditLedgerMigrationManualReleaseHealthDigestHistoryReleaseEvidenceVerifier",
                "status": "review_manual_release_health_digest_history_release_evidence_verifier_defined",
                "required_before": "any_manual_release_health_digest_history_migration",
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

    def _storage_column(
        self,
        name: str,
        column_type: str,
        nullable: bool,
        purpose: str,
        source: str,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "type": column_type,
            "nullable": nullable,
            "purpose": purpose,
            "source": source,
            "create_now": False,
            "stores_sensitive_plaintext": False,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _migration_spec_check(
        self,
        name: str,
        passed: bool,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "status": "passed" if passed else "failed",
            "reason": reason,
            "details": details or {},
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _release_readiness_gate(
        self,
        name: str,
        passed: bool,
        reason: str,
        *,
        status_if_false: str = "blocked",
    ) -> dict[str, Any]:
        return {
            "name": name,
            "status": "passed" if passed else status_if_false,
            "reason": reason,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _release_package_item(
        self,
        name: str,
        status: Any,
        allowed_output: Any,
        generated_at: Any,
        safety_passed: bool,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "status": status,
            "allowed_output": allowed_output,
            "generated_at": generated_at,
            "safety_passed": safety_passed,
            "included": True,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _release_integrity_check(
        self,
        name: str,
        passed: bool,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "status": "passed" if passed else "failed",
            "reason": reason,
            "details": details or {},
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _manual_release_rehearsal_step(
        self,
        name: str,
        ready: bool,
        instruction: str,
        evidence: dict[str, Any] | None = None,
        *,
        pending_reason: str = "Required evidence is not ready.",
    ) -> dict[str, Any]:
        return {
            "name": name,
            "status": "ready_for_manual_review" if ready else "pending_evidence",
            "instruction": instruction,
            "pending_reason": None if ready else pending_reason,
            "evidence": evidence or {},
            "operator_action_required": True,
            "api_can_mark_complete": False,
            "api_can_record_approval": False,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _manual_release_evidence_check(
        self,
        name: str,
        passed: bool,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "status": "passed" if passed else "failed",
            "reason": reason,
            "details": details or {},
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _manual_release_digest_module(
        self,
        name: str,
        status: Any,
        evidence_id: Any,
        go_no_go: Any,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "status": status,
            "evidence_id": evidence_id,
            "go_no_go": go_no_go,
            "included": True,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }

    def _manual_release_digest_history_gate(
        self,
        name: str,
        passed: bool,
        reason: str,
        status_if_false: str = "blocked",
    ) -> dict[str, Any]:
        return {
            "name": name,
            "status": "passed" if passed else status_if_false,
            "reason": reason,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": settings.enable_live_trading,
        }
    def _manual_release_artifact_hashes(self, evidence: dict[str, Any]) -> dict[str, str]:
        artifacts = evidence.get("artifacts") if isinstance(evidence, dict) else None
        if not isinstance(artifacts, list):
            return {}
        return {
            str(item.get("name")): str(item.get("artifact_hash", ""))
            for item in artifacts
            if isinstance(item, dict) and item.get("name")
        }

    def _manual_release_artifact_reviews(self, evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
        artifacts = evidence.get("artifacts") if isinstance(evidence, dict) else None
        if not isinstance(artifacts, list):
            return {}
        return {
            str(item.get("name")): {
                "reviewed_by": item.get("reviewed_by"),
                "reviewed_at": item.get("reviewed_at"),
            }
            for item in artifacts
            if isinstance(item, dict) and item.get("name")
        }

    def _default_audit_ledger_migration_spec(self, storage_plan: dict[str, Any]) -> str:
        columns = ",\n  ".join(
            f"{item['name']} {item['type']}{'' if item['nullable'] else ' NOT NULL'}"
            for item in storage_plan["planned_columns"]
        )
        indexes = "\n".join(
            f"CREATE {'UNIQUE ' if item['unique'] else ''}INDEX IF NOT EXISTS {item['name']} "
            f"ON {storage_plan['target_future_table']} ({', '.join(item['columns'])});"
            for item in storage_plan["proposed_indexes"]
        )
        return (
            f"CREATE TABLE IF NOT EXISTS {storage_plan['target_future_table']} (\n"
            f"  {columns},\n"
            "  CHECK (safety_flags_json LIKE '%live_trading_enabled%')\n"
            ");\n"
            f"{indexes}\n"
            "-- Dry-run review text only. API does not run this text."
        )

    def _default_manual_release_health_digest_history_migration_spec(self, field_mappings: list[dict[str, Any]]) -> str:
        lines = [
            "CREATE TABLE IF NOT EXISTS manual_release_health_digest_history (",
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,",
        ]
        for item in field_mappings:
            field = str(item.get("target_field"))
            storage = str(item.get("storage", "text"))
            column_type = "INTEGER" if storage == "integer" or field.endswith("_count") else "JSON" if storage == "metadata_json" else "TEXT"
            nullability = " NOT NULL" if item.get("required") else ""
            lines.append(f"  {field} {column_type}{nullability},")
        lines.extend(
            [
                "  created_at TEXT NOT NULL,",
                "  review_only INTEGER NOT NULL DEFAULT 1,",
                "  simulation_only INTEGER NOT NULL DEFAULT 1,",
                "  live_trading_enabled INTEGER NOT NULL DEFAULT 0,",
                "  CHECK (review_only = 1),",
                "  CHECK (simulation_only = 1),",
                "  CHECK (live_trading_enabled = 0)",
                ");",
                "-- Dry-run review text only. API does not run this text, create tables, write rows, or write migration files.",
            ]
        )
        return "\n".join(lines)

    def _decode_json(self, raw: str) -> Any:
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return {}

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None

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
