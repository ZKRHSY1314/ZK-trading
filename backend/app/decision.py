from app.config import settings
from app.knowledge.repository import KnowledgeRepository
from app.models import DecisionAnalysis, KnowledgeContext, MarketSnapshot
from app.rules.engine import RuleEngine
from app.rules.loader import load_rule_config
from app.storage.sqlite_store import SQLiteStore
from app.ai.model_gateway import DisabledModelGateway


class DecisionAnalyzer:
    def __init__(self) -> None:
        self.store = SQLiteStore(settings.database_path)
        self.store.init()
        self.repository = KnowledgeRepository(self.store)
        self.engine = RuleEngine(load_rule_config())
        self.ai = DisabledModelGateway()

    def analyze(self, snapshot: MarketSnapshot) -> DecisionAnalysis:
        decision = self.engine.evaluate(snapshot)
        keywords = self.repository.keywords_for_stock(snapshot.symbol, snapshot.name)
        rule_ids = [hit.rule_id for hit in decision.hits if hit.passed]

        knowledge = KnowledgeContext(
            principles=self.repository.list_principles(),
            related_strategies=self.repository.related_strategies(rule_ids),
            related_cases=self.repository.search_cases(keywords),
            stock_profiles=self.repository.search_stock_profiles(keywords),
            trade_records=self.repository.search_trade_records(keywords),
            user_notes=self.repository.search_user_notes(keywords),
        )

        analysis = DecisionAnalysis(
            snapshot=snapshot,
            decision=decision,
            knowledge=knowledge,
            risk_notes=self._risk_notes(decision, knowledge),
            suggested_next_actions=self._suggested_next_actions(decision, knowledge),
        )
        analysis.explanation = self.ai.explain(analysis)
        return analysis

    def _risk_notes(self, decision, knowledge: KnowledgeContext) -> list[str]:
        notes: list[str] = []
        failed_hard_hits = [
            hit for hit in decision.hits if hit.hard_block and not hit.passed
        ]
        if failed_hard_hits:
            notes.extend(f"{hit.name}: {hit.reason}" for hit in failed_hard_hits)

        failure_cases = [
            case for case in knowledge.related_cases if case.get("case_type") == "failure"
        ]
        if failure_cases:
            notes.append(f"发现 {len(failure_cases)} 条相似失败案例，需优先复核买早、追高、未执行计划风险。")

        profiles_with_risk = [
            profile
            for profile in knowledge.stock_profiles
            if profile.get("risk_level") and profile.get("risk_level") != "小"
        ]
        if profiles_with_risk:
            risk_levels = sorted({profile["risk_level"] for profile in profiles_with_risk})
            notes.append(f"自选股档案存在风险标记: {', '.join(risk_levels)}。")

        focus_notes = [
            note
            for note in knowledge.user_notes
            if note.get("note_type")
            in {
                "focus_priority",
                "method_success",
                "training_candidate",
                "completed_distribution_training",
            }
        ]
        if focus_notes:
            notes.append("存在用户确认知识，应提高解释权重并纳入训练/复盘。")

        if decision.blocked:
            notes.append("当前命中硬红线，系统不应给出积极买入建议。")
        return notes

    def _suggested_next_actions(self, decision, knowledge: KnowledgeContext) -> list[str]:
        if decision.blocked:
            return ["放入剔除名单或等待重新满足低位/风控条件。"]

        actions = []
        if decision.tier.value == "strong":
            actions.append("加入强候选池，进入1分钟盘中监控。")
        elif decision.tier.value == "watch":
            actions.append("加入观察候选池，等待更明确的量价信号。")
        else:
            actions.append("暂不进入候选池，保留复盘记录。")

        if knowledge.related_cases:
            actions.append("展示相似案例，优先提醒失败案例中的执行纪律问题。")
        if knowledge.stock_profiles:
            actions.append("结合自选股成本线、卖点和风险评级生成模拟盘计划。")
        return actions
