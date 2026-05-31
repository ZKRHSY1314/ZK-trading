from __future__ import annotations

from datetime import datetime
from typing import Any

from app.config import settings
from app.risk.portfolio import DEFAULT_LIMITS


class TradeExecutionGatewayService:
    """V5.0 starts as a review-only safety boundary, not an executor."""

    stage = "V5.0-P2"

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
                "requires_future_risk_contract": True,
                "requires_future_audit_storage": True,
                "requires_future_rollback_runbook": True,
                "next_required_action": "review_portfolio_and_symbol_risk_gate_contract",
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
                "next_required_action": "design_review_only_risk_gate_contract",
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
                "requires_future_rollback_runbook": True,
                "next_required_action": "design_review_only_rollback_runbook",
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
                "review_required",
                "audit_schema_review_ready_without_rollback",
                "immutable_audit_log_and_manual_rollback_plan",
                "V5.0-P1 defines the audit evidence schema, but rollback remains a future review requirement.",
            ),
        ]
        return {
            "schema_version": "trade_execution_gateway_review_gates.v1",
            "status": "blocked_by_safety_gate" if any(gate["status"] == "blocked" for gate in gates) else "review_required",
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
                "live_trading_enabled": settings.enable_live_trading,
                "next_required_action": "design_review_only_rollback_runbook",
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
                "status": "not_implemented",
                "required_before": "any_live_integration_review",
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
