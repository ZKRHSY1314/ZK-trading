from typing import Protocol
from app.models import DecisionAnalysis, Explanation


class ModelGateway(Protocol):
    def explain(self, analysis: DecisionAnalysis) -> Explanation:
        ...


class DisabledModelGateway:
    def explain(self, analysis: DecisionAnalysis) -> Explanation:
        # Deterministic local explanation generator
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
            "若数据源存在延迟，可能影响评级准确性。"
        ]

        return Explanation(
            signal_summary=signal_summary,
            matched_rules=matched_rules,
            risk_blockers=risk_blockers,
            data_quality=data_quality,
            similar_cases=similar_cases,
            uncertainty_notes=uncertainty_notes,
            simulation_disclaimer="SIMULATION ONLY: This is an AI-generated analysis for simulation and review purposes only. Not investment advice."
        )


class OpenAIModelGateway:
    def explain(self, analysis: DecisionAnalysis) -> Explanation:
        raise NotImplementedError("OpenAI 接口将在配置 API Key 后接入")


class QwenModelGateway:
    def explain(self, analysis: DecisionAnalysis) -> Explanation:
        raise NotImplementedError("通义千问接口将在配置 API Key 后接入")


class LocalModelGateway:
    def explain(self, analysis: DecisionAnalysis) -> Explanation:
        raise NotImplementedError("本地模型接口将在模型路径确认后接入")
