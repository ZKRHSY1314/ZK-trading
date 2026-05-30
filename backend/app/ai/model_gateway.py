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


class DisabledModelGateway:
    def explain(self, analysis: DecisionAnalysis) -> Explanation:
        snapshot = analysis.snapshot
        decision = analysis.decision
        knowledge = analysis.knowledge

        signal_summary = f"[{snapshot.symbol}] 综合得分 {decision.score}, 评级 {decision.tier.value}。价格: {snapshot.price}。"
        if decision.blocked:
            signal_summary += " 当前受到硬风控阻断。"

        matched_rules = [hit.name for hit in decision.hits if hit.passed]
        risk_blockers = analysis.risk_notes.copy()

        data_quality = snapshot.metadata.get("source", "AKShare (local)")
        if snapshot.metadata.get("is_fallback"):
            data_quality += " (Fallback source used due to primary failure)"

        similar_cases = []
        if knowledge.related_cases:
            similar_cases = knowledge.related_cases[:3]

        uncertainty_notes = [
            "当前未连接外部大模型，此为基于规则引擎的本地确定性解释。",
            "若数据源存在延迟，可能影响评级准确性。",
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


class OpenAIModelGateway:
    def explain(self, analysis: DecisionAnalysis) -> Explanation:
        raise NotImplementedError("OpenAI 接口将在配置 API Key 后接入")

    def propose_parameter_patch(self, trades: list[dict[str, Any]]) -> ModelGatewayResult:
        raise NotImplementedError("OpenAI 参数提案接口将在配置 API Key 后接入")


class QwenModelGateway:
    def explain(self, analysis: DecisionAnalysis) -> Explanation:
        raise NotImplementedError("通义千问接口将在配置 API Key 后接入")

    def propose_parameter_patch(self, trades: list[dict[str, Any]]) -> ModelGatewayResult:
        raise NotImplementedError("通义千问参数提案接口将在配置 API Key 后接入")


class LocalModelGateway:
    def explain(self, analysis: DecisionAnalysis) -> Explanation:
        raise NotImplementedError("本地模型接口将在模型路径确认后接入")

    def propose_parameter_patch(self, trades: list[dict[str, Any]]) -> ModelGatewayResult:
        raise NotImplementedError("本地模型参数提案接口将在模型路径确认后接入")
