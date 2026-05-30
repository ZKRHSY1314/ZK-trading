from app.config import settings
from app.decision import DecisionAnalyzer
from app.learning.phase_matcher import PhaseSimilarityService
from app.models import CandidateTier, MarketSnapshot, SimulationPlan


class SimulationPlanner:
    def create_plan(self, snapshot: MarketSnapshot) -> SimulationPlan:
        analysis = DecisionAnalyzer().analyze(snapshot)
        decision = analysis.decision
        metadata = snapshot.metadata
        reference_price = snapshot.price
        completed_distribution_note = any(
            note.get("note_type") == "completed_distribution_training"
            for note in analysis.knowledge.user_notes
        )
        phase_guardrail = PhaseSimilarityService().latest_guardrail(snapshot.symbol)

        if phase_guardrail:
            return SimulationPlan(
                symbol=snapshot.symbol,
                name=snapshot.name,
                action="observe",
                allowed=False,
                tier=CandidateTier.watch,
                reference_price=reference_price,
                quantity=0,
                position_ratio=0,
                estimated_amount=0,
                stop_loss=self._stop_loss(snapshot),
                target_price=self._target_price(snapshot),
                reasons=[phase_guardrail["reason"]],
                risk_notes=analysis.risk_notes
                + [
                    phase_guardrail.get("diagnosis")
                    or "阶段匹配触发保守观察，模拟盘不生成买入订单。",
                ],
                live_trading_enabled=settings.enable_live_trading,
            )

        if (
            completed_distribution_note
            or
            metadata.get("profile_risk_level") == "短期不追高"
            or metadata.get("profile_rating") == "出货完成训练样本"
        ):
            return SimulationPlan(
                symbol=snapshot.symbol,
                name=snapshot.name,
                action="observe",
                allowed=False,
                tier=CandidateTier.watch,
                reference_price=reference_price,
                quantity=0,
                position_ratio=0,
                estimated_amount=0,
                stop_loss=self._stop_loss(snapshot),
                target_price=self._target_price(snapshot),
                reasons=["主力拉升出货完成训练样本，短期只复盘不追高"],
                risk_notes=analysis.risk_notes + ["当前样本用于学习吸筹、试盘、拉升、出货阶段，不生成买入订单。"],
                live_trading_enabled=settings.enable_live_trading,
            )

        if decision.blocked:
            return SimulationPlan(
                symbol=snapshot.symbol,
                name=snapshot.name,
                action="observe",
                allowed=False,
                tier=decision.tier,
                reference_price=reference_price,
                quantity=0,
                position_ratio=0,
                estimated_amount=0,
                stop_loss=self._stop_loss(snapshot),
                target_price=self._target_price(snapshot),
                reasons=["命中硬红线，模拟盘不生成买入订单"],
                risk_notes=analysis.risk_notes,
                live_trading_enabled=settings.enable_live_trading,
            )

        tier = decision.tier
        data_quality = metadata.get("data_quality")
        downgraded_data_quality = data_quality in {"fallback_profile", "realtime_quote_fallback"}
        if downgraded_data_quality:
            if tier == CandidateTier.strong:
                tier = CandidateTier.watch

        position_ratio = self._position_ratio(tier, metadata.get("profile_risk_level"))
        quantity = self._quantity(reference_price, position_ratio)
        allowed = quantity >= settings.min_order_lot
        action = "buy" if allowed else "observe"
        if downgraded_data_quality:
            position_ratio = 0
            quantity = 0
            allowed = False
            action = "observe"

        reasons = [
            f"候选层级: {tier.value}",
            f"规则评分: {decision.score:g}",
            f"建议仓位: {position_ratio:.1%}",
        ]
        if data_quality in {"fallback_profile", "realtime_quote_fallback"}:
            reasons.append("当前使用降级报价或兜底行情，强候选已降级并需等待实时行情确认")

        return SimulationPlan(
            symbol=snapshot.symbol,
            name=snapshot.name,
            action=action,
            allowed=allowed,
            tier=tier,
            reference_price=reference_price,
            quantity=quantity,
            position_ratio=position_ratio,
            estimated_amount=round(quantity * reference_price, 2),
            stop_loss=self._stop_loss(snapshot),
            target_price=self._target_price(snapshot),
            reasons=reasons,
            risk_notes=analysis.risk_notes,
            live_trading_enabled=settings.enable_live_trading,
        )

    def _position_ratio(self, tier: CandidateTier, risk_level: str | None) -> float:
        if risk_level and risk_level != "小":
            return 0.02
        if tier == CandidateTier.strong:
            return 0.10
        if tier == CandidateTier.watch:
            return 0.03
        return 0.01

    def _quantity(self, price: float, position_ratio: float) -> int:
        budget = settings.default_cash * position_ratio
        lots = int(budget // (price * settings.min_order_lot))
        return lots * settings.min_order_lot

    def _stop_loss(self, snapshot: MarketSnapshot) -> float | None:
        candidates = [
            snapshot.low,
            snapshot.metadata.get("profile_operation_cost_line"),
        ]
        prices = [float(value) for value in candidates if value]
        return round(max(prices), 3) if prices else None

    def _target_price(self, snapshot: MarketSnapshot) -> float | None:
        target = snapshot.metadata.get("profile_sell_target")
        if target:
            return round(float(target), 3)
        if snapshot.high:
            return round(snapshot.high * 1.1, 3)
        return None
