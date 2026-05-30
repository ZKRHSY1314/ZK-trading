from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.models import DecisionAnalysis, Explanation


@dataclass(frozen=True)
class ModelGatewayResult:
    provider: str
    operation: str
    prompt: dict[str, Any]
    response: dict[str, Any]
    safety: dict[str, Any]


class ModelGateway(Protocol):
    def explain(self, analysis: DecisionAnalysis) -> Explanation:
        ...

    def propose_parameter_patch(self, trades: list[dict[str, Any]]) -> ModelGatewayResult:
        ...

    def explain_code_evolution(
        self,
        record: dict[str, Any],
        context: dict[str, Any],
    ) -> ModelGatewayResult:
        ...

    def summarize_experience_review(
        self,
        review: dict[str, Any],
        events: list[dict[str, Any]],
    ) -> ModelGatewayResult:
        ...


class DisabledModelGateway:
    provider = "mock_local_rule"

    def explain(self, analysis: DecisionAnalysis) -> Explanation:
        snapshot = analysis.snapshot
        decision = analysis.decision
        knowledge = analysis.knowledge

        signal_summary = (
            f"[{snapshot.symbol}] composite score {decision.score}, "
            f"tier {decision.tier.value}, price {snapshot.price}."
        )
        if decision.blocked:
            signal_summary += " Current decision is blocked by hard risk controls."

        matched_rules = [hit.name for hit in decision.hits if hit.passed]
        risk_blockers = analysis.risk_notes.copy()

        data_quality = snapshot.metadata.get("source", "AKShare (local)")
        if snapshot.metadata.get("is_fallback"):
            data_quality += " (fallback source used due to primary failure)"

        similar_cases = knowledge.related_cases[:3] if knowledge.related_cases else []

        uncertainty_notes = [
            "Local deterministic explanation only; no external model is connected.",
            "Delayed or incomplete market data may affect signal confidence.",
        ]

        return Explanation(
            signal_summary=signal_summary,
            matched_rules=matched_rules,
            risk_blockers=risk_blockers,
            data_quality=data_quality,
            similar_cases=similar_cases,
            uncertainty_notes=uncertainty_notes,
            simulation_disclaimer=(
                "SIMULATION ONLY: This is an AI-generated analysis for simulation "
                "and review purposes only. Not investment advice."
            ),
        )

    def propose_parameter_patch(self, trades: list[dict[str, Any]]) -> ModelGatewayResult:
        prompt = {
            "trade_count": len(trades),
            "simulation_only": True,
            "allowed_outputs": ["explanation", "parameter_proposal", "validation_request"],
        }
        proposed_patch = {
            "rules": [
                {
                    "id": "constitution_no_high_position",
                    "weight": 20,
                    "hard_block": False,
                }
            ],
            "min_market_cap": 3000000000,
            "max_position_ratio": 0.5,
            "candidate_tiers": {"strong_min_score": 85},
        }
        safety_blocks = []
        if proposed_patch.get("min_market_cap", 10000000000) < 5000000000:
            proposed_patch["min_market_cap"] = 5000000000
            safety_blocks.append("min_market_cap increased to safe floor of 5B")
        if proposed_patch.get("max_position_ratio", 0) > 0.2:
            proposed_patch["max_position_ratio"] = 0.2
            safety_blocks.append("max_position_ratio capped at safe limit of 20%")
        for rule in proposed_patch.get("rules", []):
            if "hard_block" in rule and not rule["hard_block"]:
                rule["hard_block"] = True
                safety_blocks.append(f"hard_block enforced for rule {rule['id']}")
        return ModelGatewayResult(
            provider="local_disabled_gateway",
            operation="parameter_proposal",
            prompt=prompt,
            response={
                "proposed_patch": proposed_patch,
                "review_only": True,
                "simulation_only": True,
            },
            safety={
                "safety_blocks_applied": safety_blocks,
                "live_trading_enabled": False,
            },
        )

    def explain_code_evolution(
        self,
        record: dict[str, Any],
        context: dict[str, Any],
    ) -> ModelGatewayResult:
        evidence = record.get("rationale", {}).get("evidence", {})
        events = context.get("experience_events", [])
        reviews = context.get("experience_reviews", [])
        closed_trades = context.get("closed_trades", [])
        snapshots = context.get("strategy_snapshots", [])
        record_type = str(record.get("record_type") or "code_maintenance")
        risk_level = str(record.get("rationale", {}).get("severity") or "medium")
        tags = self._attribution_tags(record_type, evidence)
        similar_groups = self._similar_groups(record_type, events, reviews, closed_trades, snapshots)
        prompt = {
            "record_id": record.get("id"),
            "record_type": record_type,
            "context_counts": {
                "experience_events": len(events),
                "experience_reviews": len(reviews),
                "closed_trades": len(closed_trades),
                "strategy_snapshots": len(snapshots),
            },
            "allowed_outputs": [
                "explanation",
                "attribution",
                "similar_groups",
                "validation_request",
            ],
            "review_only": True,
            "simulation_only": True,
        }
        response = {
            "explanation": {
                "summary": self._summary_for_type(record_type, record),
                "why_now": self._why_now(record_type, evidence),
                "risk_level": risk_level,
            },
            "attribution": {
                "tags": tags,
                "primary_cause": tags[0] if tags else "maintenance_gap",
                "confidence": 0.72 if similar_groups else 0.58,
            },
            "similar_groups": similar_groups,
            "validation_request": {
                "required_checks": [
                    "backend_compileall",
                    "pytest",
                    "frontend_typecheck",
                    "vite_build",
                    "git_diff_check",
                    "forbidden_tracked_file_scan",
                ],
                "blocking": True,
                "note": "Record validation through CLI only; API does not execute local commands.",
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }
        return ModelGatewayResult(
            provider=self.provider,
            operation="code_evolution_explanation",
            prompt=prompt,
            response=response,
            safety={
                "allowed_outputs": prompt["allowed_outputs"],
                "safety_blocks_applied": [],
                "live_trading_enabled": False,
            },
        )

    def summarize_experience_review(
        self,
        review: dict[str, Any],
        events: list[dict[str, Any]],
    ) -> ModelGatewayResult:
        summary = review.get("summary") or {}
        event_categories = sorted({str(event.get("category")) for event in events if event.get("category")})
        prompt = {
            "review_id": review.get("id"),
            "event_count": len(events),
            "allowed_outputs": ["explanation", "attribution", "validation_request"],
            "review_only": True,
            "simulation_only": True,
        }
        response = {
            "summary": {
                "title": review.get("title") or "experience review",
                "portfolio_posture": (summary.get("portfolio_risk") or {}).get("posture", "unknown"),
                "backtest_warning_count": len(summary.get("backtest_warnings") or []),
                "event_categories": event_categories[:8],
            },
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        }
        return ModelGatewayResult(
            provider=self.provider,
            operation="experience_review_summary",
            prompt=prompt,
            response=response,
            safety={
                "allowed_outputs": prompt["allowed_outputs"],
                "safety_blocks_applied": [],
                "live_trading_enabled": False,
            },
        )

    def _summary_for_type(self, record_type: str, record: dict[str, Any]) -> str:
        title = record.get("title") or "Review item"
        summaries = {
            "data_quality_fix": "Data quality evidence should be closed before scans expand.",
            "risk_control_review": "Blocked risk gates require review before new simulated entries.",
            "strategy_attribution": "Failed trades need attribution before changing strategy rules.",
            "backtest_execution_review": "Execution warnings should remain realistic and auditable.",
            "code_maintenance": "Validation and evidence panels need continuous maintenance.",
        }
        return f"{title}: {summaries.get(record_type, 'Review-only code evolution item.')}"

    def _why_now(self, record_type: str, evidence: dict[str, Any]) -> list[str]:
        reasons = []
        if evidence.get("events"):
            reasons.append("recent_experience_events")
        if evidence.get("warnings"):
            reasons.append("backtest_or_data_warnings")
        if evidence.get("blocked_gates"):
            reasons.append("blocked_portfolio_risk_gate")
        if evidence.get("failure_cases"):
            reasons.append("closed_trade_failure_cases")
        if not reasons:
            reasons.append(f"{record_type}_periodic_review")
        return reasons

    def _attribution_tags(self, record_type: str, evidence: dict[str, Any]) -> list[str]:
        mapping = {
            "data_quality_fix": ["data_gap", "price_readiness", "benchmark_coverage"],
            "risk_control_review": ["portfolio_risk", "stop_new_entries", "drawdown_control"],
            "strategy_attribution": ["failed_trade", "entry_timing", "market_regime"],
            "backtest_execution_review": ["execution_model", "liquidity", "limit_block"],
            "code_maintenance": ["validation_pipeline", "frontend_evidence", "auditability"],
        }
        tags = mapping.get(record_type, ["review_only"])
        if evidence.get("warnings"):
            tags.append("warning_driven")
        if evidence.get("events"):
            tags.append("event_driven")
        return list(dict.fromkeys(tags))

    def _similar_groups(
        self,
        record_type: str,
        events: list[dict[str, Any]],
        reviews: list[dict[str, Any]],
        closed_trades: list[dict[str, Any]],
        snapshots: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        groups: list[dict[str, Any]] = []
        if record_type == "data_quality_fix":
            matches = [event for event in events if event.get("category") == "data_quality"]
            groups.append(self._group("data_quality_events", matches))
        elif record_type == "risk_control_review":
            matches = [
                review
                for review in reviews
                if (review.get("summary") or {}).get("portfolio_risk", {}).get("posture") == "stop_new_entries"
            ]
            groups.append(self._group("stop_new_entries_reviews", matches))
        elif record_type == "strategy_attribution":
            matches = [trade for trade in closed_trades if float(trade.get("realized_pnl") or 0) < 0]
            groups.append(self._group("losing_closed_trades", matches))
        elif record_type == "backtest_execution_review":
            matches = [event for event in events if event.get("category") == "backtest_execution"]
            groups.append(self._group("execution_warning_events", matches))
        else:
            groups.append(self._group("strategy_snapshots", snapshots))
        return [group for group in groups if group["count"] > 0]

    def _group(self, group: str, items: list[dict[str, Any]]) -> dict[str, Any]:
        examples = []
        for item in items[:3]:
            examples.append(
                {
                    "id": item.get("id"),
                    "symbol": item.get("symbol"),
                    "label": item.get("outcome_label") or item.get("title") or item.get("strategy_name"),
                }
            )
        return {"group": group, "count": len(items), "examples": examples}


class OpenAIModelGateway:
    def explain(self, analysis: DecisionAnalysis) -> Explanation:
        raise NotImplementedError("OpenAI gateway is disabled until an API key is explicitly configured.")

    def propose_parameter_patch(self, trades: list[dict[str, Any]]) -> ModelGatewayResult:
        raise NotImplementedError("OpenAI parameter proposal is disabled.")

    def explain_code_evolution(self, record: dict[str, Any], context: dict[str, Any]) -> ModelGatewayResult:
        raise NotImplementedError("OpenAI code evolution explanation is disabled.")

    def summarize_experience_review(self, review: dict[str, Any], events: list[dict[str, Any]]) -> ModelGatewayResult:
        raise NotImplementedError("OpenAI experience review summary is disabled.")


class QwenModelGateway:
    def explain(self, analysis: DecisionAnalysis) -> Explanation:
        raise NotImplementedError("Qwen gateway is disabled until credentials are explicitly configured.")

    def propose_parameter_patch(self, trades: list[dict[str, Any]]) -> ModelGatewayResult:
        raise NotImplementedError("Qwen parameter proposal is disabled.")

    def explain_code_evolution(self, record: dict[str, Any], context: dict[str, Any]) -> ModelGatewayResult:
        raise NotImplementedError("Qwen code evolution explanation is disabled.")

    def summarize_experience_review(self, review: dict[str, Any], events: list[dict[str, Any]]) -> ModelGatewayResult:
        raise NotImplementedError("Qwen experience review summary is disabled.")


class LocalModelGateway:
    def explain(self, analysis: DecisionAnalysis) -> Explanation:
        raise NotImplementedError("Local model gateway is disabled until a local model endpoint is configured.")

    def propose_parameter_patch(self, trades: list[dict[str, Any]]) -> ModelGatewayResult:
        raise NotImplementedError("Local model parameter proposal is disabled.")

    def explain_code_evolution(self, record: dict[str, Any], context: dict[str, Any]) -> ModelGatewayResult:
        raise NotImplementedError("Local model code evolution explanation is disabled.")

    def summarize_experience_review(self, review: dict[str, Any], events: list[dict[str, Any]]) -> ModelGatewayResult:
        raise NotImplementedError("Local model experience review summary is disabled.")
