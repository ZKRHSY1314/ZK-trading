from __future__ import annotations

from datetime import datetime
from typing import Any

from app.config import settings


class TradeExecutionGatewayService:
    """V5.0 starts as a review-only safety boundary, not an executor."""

    stage = "V5.0-P0"

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
                "review_required",
                "not_implemented",
                "explicit_operator_confirmation_contract",
                "A future gateway must define human confirmation before any real-money action is even considered.",
            ),
            self._gate(
                "risk_gate_contract_required",
                "review_required",
                "not_implemented",
                "portfolio_and_symbol_risk_contract",
                "A future gateway must bind portfolio risk, symbol risk, cooldowns, and rollback before execution.",
            ),
            self._gate(
                "audit_and_rollback_required",
                "review_required",
                "not_implemented",
                "immutable_audit_log_and_manual_rollback_plan",
                "A future gateway must persist audit evidence and define manual rollback before live integration.",
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
                "manual_confirmation_contract_ready": False,
                "risk_contract_ready": False,
                "audit_contract_ready": False,
                "live_trading_enabled": settings.enable_live_trading,
                "next_required_action": "design_manual_confirmation_and_risk_contract",
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
                "status": "not_implemented",
                "required_before": "any_real_money_action",
                "review_only": True,
            },
            {
                "name": "PortfolioRiskGateContract",
                "status": "not_implemented",
                "required_before": "any_gateway_enablement",
                "review_only": True,
            },
            {
                "name": "ExecutionAuditLedger",
                "status": "not_implemented",
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
