from app.config import settings
from app.decision import DecisionAnalyzer
from app.learning.phase_matcher import PhaseSimilarityService
from app.models import CandidateTier, MarketSnapshot, SimulationPlan
from app.models import RiskBlockCause


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
            risk_blocked = [
                RiskBlockCause(
                    rule_id="phase_guardrail",
                    rule_name="Phase similarity guardrail",
                    layer="execution",
                    trigger_level="hard",
                    reason=str(phase_guardrail["reason"]),
                    threshold={"match_core_symbol": phase_guardrail.get("best_core_symbol")},
                    evidence=phase_guardrail,
                    evidence_snippet=phase_guardrail.get("diagnosis"),
                    source="simulation_planner",
                )
            ]
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
                    or "Phase similarity guardrail triggered; simulation stays observe-only.",
                ],
                risk_blocked=risk_blocked,
                blocked_reason=risk_blocked[0].rule_id,
                live_trading_enabled=settings.enable_live_trading,
            )

        profile_risk_level = str(metadata.get("profile_risk_level") or "")
        profile_rating = str(metadata.get("profile_rating") or "")
        completed_distribution_profile = (
            "short_term_no_chase" in profile_risk_level
            or "\u77ed\u671f\u4e0d\u8ffd\u9ad8" in profile_risk_level
            or "completed_distribution_training_sample" in profile_rating
            or "\u51fa\u8d27\u5b8c\u6210\u8bad\u7ec3\u6837\u672c" in profile_rating
        )

        if (
            completed_distribution_note
            or completed_distribution_profile
        ):
            risk_blocked = [
                RiskBlockCause(
                    rule_id="distribution_training_sample",
                    rule_name="Completed distribution training sample",
                    layer="execution",
                    trigger_level="hard",
                    reason="Completed distribution training sample; observe only.",
                    threshold={"sample_scope": "distribution_cycle"},
                    evidence={"symbol": snapshot.symbol},
                    evidence_snippet="This sample is used for phase learning and does not generate a buy order.",
                    source="simulation_planner",
                )
            ]
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
                reasons=["Completed distribution training sample; observe only."],
                risk_blocked=risk_blocked,
                blocked_reason=risk_blocked[0].rule_id,
                risk_notes=analysis.risk_notes
                + [
                    "This sample is used for phase learning and does not generate a buy order.",
                ],
                live_trading_enabled=settings.enable_live_trading,
            )

        from app.market_regime.service import MarketRegimeService

        regime_data = MarketRegimeService().get_latest_regime()
        regime = regime_data.get("regime", "neutral")
        if regime == "extreme_risk":
            risk_blocked = [
                RiskBlockCause(
                    rule_id="market_regime_extreme_risk",
                    rule_name="Market regime guardrail",
                    layer="execution",
                    trigger_level="hard",
                    reason="Market regime blocks new simulated entries.",
                    threshold={"regime": regime},
                    evidence=regime_data,
                    evidence_snippet="Extreme risk regime detected.",
                    source="simulation_planner",
                )
            ]
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
                reasons=regime_data.get("reasons", ["extreme market risk"]),
                risk_blocked=risk_blocked,
                blocked_reason=risk_blocked[0].rule_id,
                risk_notes=analysis.risk_notes + ["Market regime blocks new simulated entries."],
                live_trading_enabled=settings.enable_live_trading,
            )

        if decision.blocked:
            blocked_causes = list(analysis.risk_blocked) if analysis.risk_blocked else []
            if not blocked_causes:
                blocked_causes = [
                    RiskBlockCause(
                        rule_id="decision_blocked",
                        rule_name="Decision hard block",
                        layer="rules",
                        trigger_level="hard",
                        reason="Decision hard block triggered.",
                        threshold={"symbol": snapshot.symbol},
                        evidence={"symbol": snapshot.symbol},
                        evidence_snippet="Decision layer hard block triggered.",
                        source="simulation_planner",
                    )
                ]
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
                reasons=["Hard rule blocked; simulation does not create a buy order."],
                risk_blocked=blocked_causes,
                blocked_reason=blocked_causes[0].rule_id,
                risk_notes=analysis.risk_notes,
                live_trading_enabled=settings.enable_live_trading,
            )

        tier = decision.tier
        data_quality = metadata.get("data_quality")
        downgraded_data_quality = data_quality in {"fallback_profile", "realtime_quote_fallback"}
        if downgraded_data_quality and tier == CandidateTier.strong:
            tier = CandidateTier.watch

        position_ratio = self._position_ratio(tier, metadata.get("profile_risk_level"), regime=regime)
        quantity = self._quantity(reference_price, position_ratio)
        allowed = quantity >= settings.min_order_lot
        action = "buy" if allowed else "observe"
        if downgraded_data_quality:
            risk_blocked = [
                RiskBlockCause(
                    rule_id="data_quality_fallback",
                    rule_name="Data quality fallback guardrail",
                    layer="execution",
                    trigger_level="hard",
                    reason="Low-quality fallback data is observe-only until confirmed by daily bars.",
                    threshold={"quality": data_quality},
                    evidence={"symbol": snapshot.symbol, "data_quality": data_quality},
                    evidence_snippet="Fallback source used for snapshot.",
                    source="simulation_planner",
                )
            ]
            position_ratio = 0
            quantity = 0
            allowed = False
            action = "observe"

        reasons = [
            f"candidate tier: {tier.value}",
            f"rule score: {decision.score:g}",
            f"suggested position: {position_ratio:.1%}",
        ]
        if downgraded_data_quality:
            reasons.append("Low-quality fallback data is observe-only until confirmed by daily bars.")
        else:
            risk_blocked = []

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
            risk_blocked=risk_blocked,
            blocked_reason=risk_blocked[0].rule_id if risk_blocked else None,
            reasons=reasons,
            risk_notes=analysis.risk_notes,
            live_trading_enabled=settings.enable_live_trading,
        )

    def _position_ratio(
        self,
        tier: CandidateTier,
        risk_level: str | None,
        regime: str = "neutral",
    ) -> float:
        if risk_level and risk_level not in {"low", "\u5c0f"}:
            ratio = 0.02
        elif tier == CandidateTier.strong:
            ratio = 0.10
        elif tier == CandidateTier.watch:
            ratio = 0.03
        else:
            ratio = 0.01

        if regime == "weak":
            ratio *= 0.5
        return ratio

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
