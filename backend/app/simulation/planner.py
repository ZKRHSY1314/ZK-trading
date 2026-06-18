import json
import sqlite3
from pathlib import Path

from app.config import settings
from app.decision import DecisionAnalyzer
from app.learning.phase_matcher import PhaseSimilarityService
from app.models import CandidateTier, MarketSnapshot, SimulationPlan
from app.models import RiskBlockCause


RELAXABLE_SIMULATION_BLOCKERS = {
    "constitution_no_high_position",
}
RELAXED_SIMULATION_FIRST_PROBE_CASH_RATIO = 0.03
MAX_RELAXABLE_PHASE_GUARDRAIL_SCORE = 82.0
STABLE_CANDIDATE_LOOKBACK_RUNS = 12


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
        phase_guardrail = self._latest_phase_guardrail(snapshot.symbol)
        review_reasons, review_notes = self._offhour_review_messages(snapshot.symbol)

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
            if self._can_relax_phase_guardrail_for_simulation(snapshot, phase_guardrail):
                stage_ratio = self._main_force_stage_ratio(snapshot)
                quantity = self._relaxed_first_probe_quantity(reference_price, stage_ratio)
                allowed = quantity >= settings.min_order_lot
                if allowed:
                    return SimulationPlan(
                        symbol=snapshot.symbol,
                        name=snapshot.name,
                        action="buy",
                        allowed=True,
                        tier=CandidateTier.watch,
                        reference_price=reference_price,
                        quantity=quantity,
                        position_ratio=round((quantity * reference_price) / settings.default_cash, 6),
                        estimated_amount=round(quantity * reference_price, 2),
                        stop_loss=self._stop_loss(snapshot),
                        target_price=self._target_price(snapshot),
                        reasons=[
                            "Simulation-only phase guardrail relaxation: distribution-like phase risk is downgraded to a 100-share learning probe after main-force markup confirmation.",
                            f"phase guardrail score: {self._phase_guardrail_score(phase_guardrail):.1f}",
                            f"stage target: {stage_ratio:.1%}",
                            "first probe capped at 100 shares and 3% simulated cash.",
                            "follow-up requires readback, fresh quote, and no failed-markup/distribution confirmation.",
                        ]
                        + review_reasons,
                        risk_notes=analysis.risk_notes
                        + [
                            phase_guardrail.get("diagnosis")
                            or "Phase similarity guardrail remains active as a review warning.",
                            "This relaxed path is simulation-only. It does not enable real orders, screen clicks, broker access, rules.yaml edits, or larger sizing.",
                        ]
                        + review_notes,
                        risk_blocked=[],
                        blocked_reason=None,
                        live_trading_enabled=settings.enable_live_trading,
                    )
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
                reasons=[phase_guardrail["reason"]] + review_reasons,
                risk_notes=analysis.risk_notes
                + [
                    phase_guardrail.get("diagnosis")
                    or "Phase similarity guardrail triggered; simulation stays observe-only.",
                ]
                + review_notes,
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
                reasons=["Completed distribution training sample; observe only."] + review_reasons,
                risk_blocked=risk_blocked,
                blocked_reason=risk_blocked[0].rule_id,
                risk_notes=analysis.risk_notes
                + [
                    "This sample is used for phase learning and does not generate a buy order.",
                ]
                + review_notes,
                live_trading_enabled=settings.enable_live_trading,
            )

        regime_data = self._latest_market_regime()
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
                reasons=regime_data.get("reasons", ["extreme market risk"]) + review_reasons,
                risk_blocked=risk_blocked,
                blocked_reason=risk_blocked[0].rule_id,
                risk_notes=analysis.risk_notes + ["Market regime blocks new simulated entries."] + review_notes,
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
            if self._can_relax_for_simulation(snapshot, blocked_causes):
                stage_ratio = self._main_force_stage_ratio(snapshot)
                quantity = self._relaxed_first_probe_quantity(reference_price, stage_ratio)
                allowed = quantity >= settings.min_order_lot
                position_ratio = round((quantity * reference_price) / settings.default_cash, 6) if allowed else 0
                reasons = [
                    "Simulation-only relaxation: high-position rule downgraded to staged probe after main-force markup confirmation.",
                    f"candidate tier: {CandidateTier.watch.value}",
                    f"rule score: {decision.score:g}",
                    f"stage target: {stage_ratio:.1%}",
                    "first probe capped at 100 shares and 3% simulated cash.",
                    "staged add-on path: probe -> add_1 after pullback/hold confirmation -> add_2 after follow-through confirmation.",
                ]
                risk_notes = analysis.risk_notes + [
                    "Only the simulation cockpit may use this relaxed path; real trading remains blocked.",
                    "First action stays small and auditable. Add-on requires verified holding/readback, fresh quote, and all portfolio gates passing.",
                ]
                reasons.extend(review_reasons)
                risk_notes.extend(review_notes)
                return SimulationPlan(
                    symbol=snapshot.symbol,
                    name=snapshot.name,
                    action="buy" if allowed else "observe",
                    allowed=allowed,
                    tier=CandidateTier.watch,
                    reference_price=reference_price,
                    quantity=quantity,
                    position_ratio=position_ratio,
                    estimated_amount=round(quantity * reference_price, 2),
                    stop_loss=self._stop_loss(snapshot),
                    target_price=self._target_price(snapshot),
                    reasons=reasons,
                    risk_blocked=[] if allowed else blocked_causes,
                    blocked_reason=None if allowed else blocked_causes[0].rule_id,
                    risk_notes=risk_notes,
                    live_trading_enabled=settings.enable_live_trading,
                )
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
                risk_notes=analysis.risk_notes + review_notes,
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

        reasons.extend(review_reasons)
        risk_notes = analysis.risk_notes + review_notes

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
            risk_notes=risk_notes,
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

    def _latest_phase_guardrail(self, symbol: str) -> dict | None:
        try:
            return PhaseSimilarityService().latest_guardrail(symbol)
        except sqlite3.OperationalError as exc:
            if "main_force_phase_matches" in str(exc):
                return None
            raise

    def _latest_market_regime(self) -> dict:
        from app.market_regime.service import MarketRegimeService

        try:
            return MarketRegimeService().get_latest_regime()
        except sqlite3.OperationalError as exc:
            if "daily_bar_cache" in str(exc):
                return {
                    "regime": "neutral",
                    "confidence": 0,
                    "reasons": ["daily_bar_cache unavailable; market regime defaults to neutral."],
                }
            raise

    def _stable_candidate_review_messages(self) -> tuple[list[str], list[str]]:
        context = self._latest_stable_candidate_context()
        candidate = context.get("candidate") if context else None
        if not candidate:
            return [], []

        tracks = context.get("tracks") if context else {}
        params = candidate.get("parameters") or {}
        validation = candidate.get("source_validation_metrics") or {}
        entry_delay = params.get("entry_delay_days")
        horizon = params.get("horizon_days")
        confirmation = params.get("confirmation_filter") or "unspecified"
        track_name = self._candidate_track_name(candidate)
        validation_return = self._format_pct(validation.get("equal_weight_cumulative_return_pct"))
        validation_win_rate = self._format_rate(validation.get("win_rate"))
        walk_forward_return = self._format_pct(candidate.get("total_equal_weight_cumulative_return_pct"))
        walk_forward_win_rate = self._format_rate(candidate.get("weighted_win_rate"))
        run_id = candidate.get("run_id")
        selection = context.get("selection") or {}
        selected_from = selection.get("selected_from_candidate_count")
        lookback_runs = selection.get("lookback_runs")
        champion_score = selection.get("champion_score")

        reasons = [
            (
                "off-hour stable candidate review: "
                f"run {run_id}, track={track_name}, entry_delay={entry_delay}, horizon={horizon}, "
                f"confirmation={confirmation}, selected_from={selected_from}/{lookback_runs} recent candidates."
            )
        ]
        risk_notes = [
            (
                "Dataset1/Dataset2 stable candidate is review-only and simulation-only: "
                f"validation_return={validation_return}, validation_win_rate={validation_win_rate}, "
                f"walk_forward_return={walk_forward_return}, walk_forward_win_rate={walk_forward_win_rate}. "
                f"champion_score={champion_score}. "
                "It does not change production rules, risk gates, position sizing, or order permissions."
            )
        ]
        track_note = self._stable_candidate_track_note(tracks)
        if track_note:
            risk_notes.append(track_note)
        complete_window_note = self._stable_candidate_complete_window_note(candidate, context.get("optimization") if context else {})
        if complete_window_note:
            risk_notes.append(complete_window_note)
        learning_filter_note = self._stable_candidate_learning_filter_note(context.get("optimization") if context else {})
        if learning_filter_note:
            risk_notes.append(learning_filter_note)
        tradeoff_note = self._stable_candidate_tradeoff_note(context.get("tradeoff_attribution") if context else {})
        if tradeoff_note:
            risk_notes.append(tradeoff_note)
        return reasons, risk_notes

    def _offhour_review_messages(self, symbol: str) -> tuple[list[str], list[str]]:
        stable_reasons, stable_notes = self._stable_candidate_review_messages()
        reclaim_note = self._reclaim_watch_note(symbol)
        if reclaim_note:
            stable_notes.append(reclaim_note)
        phase_note = self._phase_similarity_note(symbol)
        if phase_note:
            stable_notes.append(phase_note)
        simulation_plan_note = self._latest_simulation_review_plan_note(symbol)
        if simulation_plan_note:
            stable_notes.append(simulation_plan_note)
        rule_family_note = self._latest_rule_family_performance_note()
        if rule_family_note:
            stable_notes.append(rule_family_note)
        return stable_reasons, stable_notes

    def _latest_simulation_review_plan_note(self, symbol: str) -> str | None:
        item, plan, run_id = self._latest_simulation_review_plan_item(symbol)
        if not item:
            return None
        quality = item.get("evidence_quality") or {}
        if not isinstance(quality, dict):
            quality = {}
        position_plan = item.get("position_plan") or {}
        if not isinstance(position_plan, dict):
            position_plan = {}
        best_strategy = item.get("best_strategy") or {}
        if not isinstance(best_strategy, dict):
            best_strategy = {}
        permission = plan.get("permission_policy") or {}
        if not isinstance(permission, dict):
            permission = {}
        confidence_tier = quality.get("confidence_tier") or "unscored"
        confidence_score = quality.get("confidence_score")
        adjusted_score = item.get("confidence_adjusted_priority_score")
        raw_score = item.get("priority_score")
        blockers = item.get("blockers") or []
        cautions = item.get("caution_flags") or []
        warning_text = ",".join(str(value) for value in (blockers or cautions)[:4]) or "none"
        reasons = quality.get("reasons") or []
        reason_text = ",".join(str(value) for value in reasons[:4]) if isinstance(reasons, list) else "not_available"
        return (
            "Latest offhour simulation review plan context: "
            f"run={run_id}, symbol={symbol}, status={plan.get('status')}, "
            f"mode={item.get('recommended_mode')}, confidence_tier={confidence_tier}, "
            f"confidence_score={confidence_score}, adjusted_priority={adjusted_score}, raw_priority={raw_score}, "
            f"max_initial_cash={position_plan.get('max_initial_cash')}, "
            f"strategy={best_strategy.get('experiment_id') or 'unknown'}, "
            f"win_rate={self._format_rate(best_strategy.get('win_rate'))}, "
            f"avg_return={self._format_pct(best_strategy.get('average_return_pct'))}, "
            f"warnings={warning_text}, reasons={reason_text}. "
            f"permissions: submit={permission.get('may_submit_order') is True}, "
            f"screen_click={permission.get('may_enable_screen_click') is True}. "
            "Use this to rank manual review and dry-run attention only; it does not change action, allowed, "
            "quantity, position sizing, risk gates, screen-click permission, or production rules."
        )

    def _latest_simulation_review_plan_item(self, symbol: str) -> tuple[dict | None, dict, int | None]:
        if settings.enable_live_trading:
            return None, {}, None
        try:
            with sqlite3.connect(settings.database_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    """
                    SELECT id, backtest_json, artifact_json
                    FROM offhour_research_runs
                    WHERE backtest_json LIKE '%simulation_review_plan%'
                       OR artifact_json LIKE '%simulation_review_plan%'
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ).fetchone()
        except (sqlite3.Error, TypeError, ValueError):
            return None, {}, None
        if not row:
            return None, {}, None
        artifact = self._json_loads(row["artifact_json"])
        backtest = self._json_loads(row["backtest_json"])
        plan = artifact.get("simulation_review_plan") or backtest.get("simulation_review_plan") or {}
        if not plan and artifact.get("artifact_written") and artifact.get("artifact_path"):
            try:
                payload = json.loads(Path(str(artifact["artifact_path"])).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                payload = {}
            if isinstance(payload, dict):
                plan = payload.get("simulation_review_plan") or {}
        if not isinstance(plan, dict):
            return None, {}, int(row["id"])
        if plan.get("review_only") is False or plan.get("simulation_only") is False:
            return None, plan, int(row["id"])
        candidates = plan.get("candidates") or []
        if not isinstance(candidates, list):
            return None, plan, int(row["id"])
        matched = next(
            (
                dict(candidate)
                for candidate in candidates
                if isinstance(candidate, dict) and str(candidate.get("symbol") or "") == symbol
            ),
            None,
        )
        return matched, plan, int(row["id"])

    def _latest_rule_family_performance_note(self) -> str | None:
        if settings.enable_live_trading:
            return None
        try:
            with sqlite3.connect(settings.database_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    """
                    SELECT id, payload_json
                    FROM events
                    WHERE event_type = 'dataset2_training_run'
                      AND payload_json LIKE '%rule_family_performance_memory%'
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ).fetchone()
        except (sqlite3.Error, TypeError, ValueError):
            return None
        if not row:
            return None
        payload = self._json_loads(row["payload_json"])
        memory = payload.get("rule_family_performance_memory") or {}
        if not isinstance(memory, dict):
            return None
        if memory.get("review_only") is False or memory.get("simulation_only") is False:
            return None
        summary = memory.get("summary") or {}
        groups = memory.get("top_backtest_groups") or []
        top = next((group for group in groups if isinstance(group, dict)), None)
        if not top:
            return (
                "Dataset2 rule-family performance memory is available but has no backtest group yet: "
                f"event={row['id']}, staging_groups={summary.get('staging_group_count')}, "
                f"backtest_trades={summary.get('backtest_trade_count')}. "
                "This is review-only and does not change action, allowed, quantity, position sizing, risk gates, or production rules."
            )
        return (
            "Dataset2 rule-family performance memory: "
            f"event={row['id']}, staging_groups={summary.get('staging_group_count')}, "
            f"backtest_trades={summary.get('backtest_trade_count')}, "
            f"top_family={top.get('pattern_id') or 'unknown'}"
            f"/{top.get('pattern_name') or 'unknown'}"
            f"/{top.get('action_label') or 'unknown'}, "
            f"trades={top.get('trade_count')}, win_rate={self._format_rate(top.get('win_rate'))}, "
            f"avg_return={self._format_pct(top.get('average_return_pct'))}, "
            f"worst_return={self._format_pct(top.get('worst_return_pct'))}. "
            "Use this only to prioritize review/dry-run evidence; it does not change action, allowed, quantity, "
            "position sizing, risk gates, or production rules."
        )

    def _phase_similarity_note(self, symbol: str) -> str | None:
        item, group, run_id = self._latest_phase_similarity_item(symbol)
        if not item:
            return None
        best = item.get("best_match") or {}
        group_key = item.get("group_key") or (group or {}).get("key") or "unknown"
        treatment = (group or {}).get("suggested_treatment") or "collect_more_samples"
        win_rate = self._format_rate((group or {}).get("win_rate"))
        average_return = self._format_pct((group or {}).get("average_close_return_pct"))
        average_min = self._format_pct((group or {}).get("average_min_return_pct"))
        sample_count = (group or {}).get("sample_count")
        core_symbol = best.get("core_symbol") or (group or {}).get("core_symbol") or "unknown"
        latest_phase = best.get("target_latest_phase") or (group or {}).get("target_latest_phase") or "unknown"
        confidence_tier = (group or {}).get("confidence_tier") or "unscored_phase_confidence"
        confidence_score = (group or {}).get("confidence_score")
        confidence_reasons = (group or {}).get("confidence_reasons") or []
        confidence_reason_text = (
            ",".join(str(reason) for reason in confidence_reasons[:4])
            if isinstance(confidence_reasons, list)
            else "not_available"
        )
        downside_note = (group or {}).get("downside_risk_note") or "downside risk not scored."
        if treatment == "observe_only_distribution_risk":
            guidance = "distribution-like phase evidence; keep observe-only unless a new signal clears Dataset1 and risk gates."
        elif treatment == "downgrade_to_smallest_dry_run_or_observe":
            guidance = "post-distribution or late-cycle evidence; downgrade to observe or smallest dry-run review."
        elif treatment == "raise_review_priority_dry_run_only":
            guidance = "Sanwei-like markup evidence can raise dry-run review priority only."
        elif treatment == "review_momentum_but_require_distribution_check":
            guidance = "momentum evidence needs a distribution-risk check before any dry-run review."
        else:
            guidance = "collect more phase evidence before changing simulation review priority."
        return (
            "Phase similarity context: "
            f"run={run_id}, symbol={symbol}, group={group_key}, core={core_symbol}, "
            f"latest_phase={latest_phase}, samples={sample_count}, win_rate={win_rate}, "
            f"avg_return={average_return}, avg_min_return={average_min}, treatment={treatment}, "
            f"confidence_tier={confidence_tier}, confidence_score={confidence_score}, "
            f"confidence_reasons={confidence_reason_text}. {downside_note} {guidance} "
            "This is review-only and does not change action, allowed, quantity, position sizing, risk gates, or production rules."
        )

    def _latest_phase_similarity_item(self, symbol: str) -> tuple[dict | None, dict | None, int | None]:
        if settings.enable_live_trading:
            return None, None, None
        try:
            with sqlite3.connect(settings.database_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    """
                    SELECT id, backtest_json
                    FROM offhour_research_runs
                    WHERE backtest_json LIKE '%phase_similarity_performance%'
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ).fetchone()
        except (sqlite3.Error, TypeError, ValueError):
            return None, None, None
        if not row:
            return None, None, None
        backtest = self._json_loads(row["backtest_json"])
        performance = backtest.get("phase_similarity_performance") or {}
        if not isinstance(performance, dict):
            return None, None, int(row["id"])
        items = performance.get("items") or []
        if not isinstance(items, list):
            return None, None, int(row["id"])
        matched_item = next(
            (
                dict(item)
                for item in items
                if isinstance(item, dict) and str(item.get("symbol") or "") == symbol
            ),
            None,
        )
        if not matched_item:
            return None, None, int(row["id"])
        group_key = matched_item.get("group_key")
        groups = performance.get("by_group") or []
        matched_group = next(
            (
                dict(group)
                for group in groups
                if isinstance(group, dict) and group.get("key") == group_key
            ),
            None,
        )
        return matched_item, matched_group, int(row["id"])

    def _reclaim_watch_note(self, symbol: str) -> str | None:
        item, run_id, backtest = self._latest_reclaim_watch_item(symbol)
        if not item:
            return None
        status = item.get("status") or "unknown"
        signal_date = item.get("signal_date") or "n/a"
        latest_date = item.get("latest_trade_date") or "n/a"
        allowed_effect = item.get("allowed_effect") or "observe_only"
        close_vs_signal = self._format_pct(item.get("close_vs_signal_pct"))
        risk_tags = item.get("risk_tags") or []
        risk_text = ",".join(str(tag) for tag in risk_tags) if risk_tags else "none"
        attribution_note = self._reclaim_risk_attribution_note(backtest, status, risk_tags)
        if status == "reclaim_review":
            guidance = "eligible for manual review or dry-run evidence only; still requires fresh quote, portfolio gates, and sim-cockpit gates."
        elif status == "near_reclaim_watch":
            guidance = "watch for a fresh close or verified intraday reclaim before dry-run review."
        elif status == "pending_future_data":
            guidance = "waiting for the next ready bar; do not infer confirmation from the old signal."
        elif status == "blocked_failed_markup_risk":
            guidance = "failed-markup risk evidence; keep observe-only unless later bars clear risk and Dataset1 confirmation returns."
        elif status == "stale_historical_signal":
            guidance = "historical research only; require a new recent Dataset2 signal."
        else:
            guidance = "review-only context; no order permission is granted."
        return (
            "Dataset2 reclaim watch context: "
            f"run={run_id}, symbol={symbol}, status={status}, signal_date={signal_date}, "
            f"latest_trade_date={latest_date}, close_vs_signal={close_vs_signal}, "
            f"allowed_effect={allowed_effect}, risk_tags={risk_text}. {guidance} "
            f"{attribution_note}"
            "This does not change action, allowed, quantity, position sizing, or production rules."
        )

    def _reclaim_risk_attribution_note(
        self,
        backtest: dict,
        status: str,
        risk_tags: list,
    ) -> str:
        study = backtest.get("dataset2_reclaim_transition_study") or {}
        attribution = study.get("risk_tag_attribution") or {}
        rows = attribution.get("by_status_tag") or []
        if not isinstance(rows, list):
            return ""
        keys = [f"{status}:{tag}" for tag in (risk_tags or ["no_risk_tag"])]
        matched = [
            row
            for row in rows
            if isinstance(row, dict) and row.get("key") in keys
        ]
        if not matched:
            return ""
        matched.sort(
            key=lambda row: (
                0
                if row.get("suggested_treatment")
                in {"observe_only_hard_risk", "downgrade_to_smallest_dry_run_or_observe"}
                else 1,
                -int(row.get("sample_count") or 0),
            )
        )
        row = matched[0]
        key = row.get("key")
        sample_count = row.get("sample_count")
        win_rate = self._format_rate(row.get("win_rate"))
        average_return = self._format_pct(row.get("average_return_pct"))
        treatment = row.get("suggested_treatment") or "collect_more_samples_before_risk_tag_weight_change"
        return (
            "Risk attribution context: "
            f"{key} samples={sample_count}, win_rate={win_rate}, avg_return={average_return}, "
            f"treatment={treatment}; use this only to downgrade or require extra review, not to increase size. "
        )

    def _latest_reclaim_watch_item(self, symbol: str) -> tuple[dict | None, int | None, dict]:
        if settings.enable_live_trading:
            return None, None, {}
        try:
            with sqlite3.connect(settings.database_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    """
                    SELECT id, backtest_json
                    FROM offhour_research_runs
                    WHERE backtest_json LIKE '%dataset2_reclaim_watchlist%'
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ).fetchone()
        except (sqlite3.Error, TypeError, ValueError):
            return None, None, {}
        if not row:
            return None, None, {}
        backtest = self._json_loads(row["backtest_json"])
        watchlist = backtest.get("dataset2_reclaim_watchlist") or {}
        for item in watchlist.get("items") or []:
            if str(item.get("symbol") or "") == symbol:
                return dict(item), int(row["id"]), backtest
        return None, int(row["id"]), backtest

    def _latest_stable_candidate_context(self) -> dict | None:
        rows = self._stable_candidate_rows(limit=STABLE_CANDIDATE_LOOKBACK_RUNS)
        best_context: dict | None = None
        accepted_count = 0
        for row in rows:
            context = self._stable_candidate_context_from_row(row)
            if not context:
                continue
            accepted_count += 1
            score = self._stable_candidate_champion_score(context["candidate"])
            context["selection"] = {
                "schema_version": "stable_candidate_champion_selection.v1",
                "policy": "best_recent_passed_candidate",
                "lookback_runs": len(rows),
                "lookback_limit": STABLE_CANDIDATE_LOOKBACK_RUNS,
                "selected_from_candidate_count": accepted_count,
                "champion_score": round(score, 6),
                "review_only": True,
                "simulation_only": True,
                "live_trading_enabled": settings.enable_live_trading,
            }
            context["candidate"]["champion_score"] = round(score, 6)
            if not best_context or score > float((best_context.get("selection") or {}).get("champion_score") or 0):
                best_context = context
        if best_context and best_context.get("selection"):
            best_context["selection"]["selected_from_candidate_count"] = accepted_count
        return best_context

    def _latest_stable_candidate(self) -> dict | None:
        context = self._latest_stable_candidate_context()
        return dict(context["candidate"]) if context else None

    def _latest_stable_candidate_row(self) -> sqlite3.Row | None:
        rows = self._stable_candidate_rows(limit=1)
        return rows[0] if rows else None

    def _stable_candidate_rows(self, limit: int) -> list[sqlite3.Row]:
        if settings.enable_live_trading:
            return []
        try:
            with sqlite3.connect(settings.database_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT id, backtest_json
                    FROM offhour_research_runs
                    WHERE backtest_json LIKE '%selected_stable_candidate%'
                    ORDER BY id DESC
                    LIMIT 1
                    """.replace("LIMIT 1", "LIMIT ?"),
                    (max(1, min(int(limit or 1), 50)),),
                ).fetchall()
        except (sqlite3.Error, TypeError, ValueError):
            return []
        return list(rows)

    def _stable_candidate_context_from_row(self, row: sqlite3.Row) -> dict | None:
        backtest = self._json_loads(row["backtest_json"])
        optimization = backtest.get("dataset2_signal_optimization") or {}
        candidate = optimization.get("selected_stable_candidate")
        if not isinstance(candidate, dict):
            return None
        if candidate.get("status") != "passed_for_simulation_review":
            return None
        if candidate.get("review_only") is False or candidate.get("simulation_only") is False:
            return None
        candidate = dict(candidate)
        candidate["run_id"] = row["id"]
        tracks = optimization.get("stable_candidate_tracks")
        tradeoff = optimization.get("track_tradeoff_attribution")
        return {
            "candidate": candidate,
            "tracks": tracks if isinstance(tracks, dict) else {},
            "tradeoff_attribution": tradeoff if isinstance(tradeoff, dict) else {},
            "optimization": optimization,
            "run_id": row["id"],
        }

    def _stable_candidate_champion_score(self, candidate: dict) -> float:
        validation = candidate.get("source_validation_metrics") or {}
        return (
            self._metric_float(candidate, "total_equal_weight_cumulative_return_pct") * 0.35
            + self._metric_float(validation, "equal_weight_cumulative_return_pct") * 0.35
            + self._metric_float(candidate, "weighted_win_rate") * 10.0
            + self._metric_float(validation, "win_rate") * 10.0
            + min(self._metric_float(candidate, "trade_count"), 80.0) * 0.5
            + self._metric_float(candidate, "min_fold_cumulative_return_pct") * 0.05
            + self._metric_float(candidate, "min_fold_win_rate") * 5.0
        )

    def _metric_float(self, payload: dict, key: str) -> float:
        try:
            return float((payload or {}).get(key) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _candidate_track_name(self, candidate: dict) -> str:
        params = candidate.get("parameters") or {}
        confirmation = str(params.get("confirmation_filter") or "none")
        attribution = str(params.get("attribution_filter") or "none")
        if confirmation == "none" and attribution in {"", "none"}:
            return "broad_momentum_candidate"
        return "dataset1_stabilized_candidate"

    def _stable_candidate_track_note(self, tracks: dict) -> str | None:
        if not tracks:
            return None

        def track_status(name: str) -> str:
            track = tracks.get(name) or {}
            status = track.get("status") or "unknown"
            candidate = track.get("candidate") or {}
            params = candidate.get("parameters") or {}
            confirmation = params.get("confirmation_filter") or "none"
            attribution = params.get("attribution_filter") or "none"
            validation = candidate.get("source_validation_metrics") or {}
            validation_return = self._format_pct(validation.get("equal_weight_cumulative_return_pct"))
            walk_forward_return = self._format_pct(candidate.get("total_equal_weight_cumulative_return_pct"))
            return (
                f"{name}={status}"
                f"(confirmation={confirmation}, attribution={attribution}, validation_return={validation_return}, "
                f"walk_forward_return={walk_forward_return})"
            )

        return (
            "Stable candidate tracks are separated for supervision: "
            f"{track_status('broad_momentum_candidate')}; "
            f"{track_status('dataset1_stabilized_candidate')}. "
            "Broad momentum raises attention; Dataset1 stabilization reduces early-entry and chase risk."
        )

    def _stable_candidate_complete_window_note(self, candidate: dict, optimization: dict) -> str | None:
        complete_window = candidate.get("complete_window")
        if not isinstance(complete_window, dict):
            budget = (optimization.get("optimization_budget") or {}).get("complete_window") if optimization else None
            checks = budget.get("checks") if isinstance(budget, dict) else []
            params = candidate.get("parameters") or {}
            entry_delay = int(params.get("entry_delay_days") or 0)
            horizon = int(params.get("horizon_days") or 0)
            complete_window = next(
                (
                    item
                    for item in checks or []
                    if int(item.get("entry_delay_days") or 0) == entry_delay
                    and int(item.get("horizon_days") or 0) == horizon
                ),
                None,
            )
        if not isinstance(complete_window, dict):
            return None
        return (
            "Stable candidate complete-window evidence: "
            f"entry_delay={complete_window.get('entry_delay_days')}, "
            f"horizon={complete_window.get('horizon_days')}, "
            f"input_signals={complete_window.get('input_signal_count')}, "
            f"eligible_signals={complete_window.get('eligible_signal_count')}, "
            f"no_entry_bar={complete_window.get('no_entry_bar_count')}, "
            f"incomplete_exit_window={complete_window.get('incomplete_exit_window_count')}. "
            "Latest signals without a full future window remain watch/research only and do not grant order permission."
        )

    def _stable_candidate_learning_filter_note(self, optimization: dict) -> str | None:
        if not isinstance(optimization, dict):
            return None
        learning_filters = optimization.get("learning_filter_candidates") or []
        if not isinstance(learning_filters, list) or not learning_filters:
            return None
        top = next((item for item in learning_filters if isinstance(item, dict)), None)
        if not top:
            return None
        params = top.get("parameters") or {}
        validation = top.get("validation_metrics") or {}
        budget = (optimization.get("optimization_budget") or {}).get("learning_filter_budget") or {}
        return (
            "Learning-filter evidence: "
            f"accepted_candidates={budget.get('accepted_candidate_count')}, "
            f"filter_count={budget.get('filter_count')}, "
            f"top_confirmation={params.get('confirmation_filter') or 'none'}, "
            f"top_attribution={params.get('attribution_filter') or 'none'}, "
            f"top_validation_win_rate={self._format_rate(validation.get('win_rate'))}, "
            f"top_validation_return={self._format_pct(validation.get('equal_weight_cumulative_return_pct'))}. "
            "Learning filters can raise review priority or add caution, but cannot write rules or change order sizing."
        )

    def _stable_candidate_tradeoff_note(self, tradeoff: dict) -> str | None:
        if not tradeoff or tradeoff.get("status") != "completed":
            return None
        verdict = tradeoff.get("verdict") or {}
        broad_only = tradeoff.get("broad_only_summary") or {}
        tag_summary = tradeoff.get("broad_only_tag_summary") or {}
        shared_delta = tradeoff.get("shared_signal_return_delta_summary") or {}
        supervision = tradeoff.get("broad_only_supervision") or {}
        watch = supervision.get("enhanced_watch_track") or {}
        near = supervision.get("near_reclaim_watch_track") or {}
        block = supervision.get("failed_markup_block") or {}
        phase_counts = tag_summary.get("phase_counts") or {}
        phase_text = ", ".join(f"{name}:{count}" for name, count in list(phase_counts.items())[:3]) or "none"
        return (
            "Stable track tradeoff attribution: "
            f"verdict={verdict.get('label') or 'unknown'}, "
            f"broad_only_count={broad_only.get('count')}, "
            f"broad_only_avg={self._format_pct(broad_only.get('average_return_pct'))}, "
            f"broad_only_risk_trades={tag_summary.get('risk_trade_count')}, "
            f"broad_only_hard_risk_trades={tag_summary.get('hard_risk_trade_count')}, "
            f"broad_only_opportunity_trades={tag_summary.get('opportunity_trade_count')}, "
            f"mixed_opportunity_risk={tag_summary.get('mixed_opportunity_risk_count')}, "
            f"top_phases={phase_text}, "
            f"enhanced_watch={watch.get('status') or 'unknown'}"
            f"(raw={watch.get('raw_opportunity_count')}, confirmed={watch.get('sample_count')}, "
            f"rejected={watch.get('secondary_confirmation_rejected_count')}, "
            f"suggested_review_position_ratio={watch.get('suggested_review_position_ratio')}), "
            f"near_reclaim_watch={near.get('status') or 'unknown'}"
            f"(samples={near.get('sample_count')}), "
            f"failed_markup_block={block.get('status') or 'unknown'}"
            f"(samples={block.get('sample_count')}), "
            f"shared_avg_delta={self._format_pct(shared_delta.get('average_return_pct'))}. "
            f"Next action: {verdict.get('next_action') or 'review'}."
        )

    def _json_loads(self, payload: str | None) -> dict:
        if not payload:
            return {}
        try:
            data = json.loads(payload)
        except (TypeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _format_pct(self, value: object) -> str:
        try:
            return f"{float(value):.2f}%"
        except (TypeError, ValueError):
            return "n/a"

    def _format_rate(self, value: object) -> str:
        try:
            return f"{float(value) * 100:.2f}%"
        except (TypeError, ValueError):
            return "n/a"

    def _can_relax_for_simulation(
        self,
        snapshot: MarketSnapshot,
        blocked_causes: list[RiskBlockCause],
    ) -> bool:
        if settings.enable_live_trading:
            return False
        if not blocked_causes:
            return False
        if any(cause.rule_id not in RELAXABLE_SIMULATION_BLOCKERS for cause in blocked_causes):
            return False
        if not self._snapshot_quality_allows_simulation_probe(snapshot):
            return False
        return self._main_force_markup_confirmed(snapshot)

    def _can_relax_phase_guardrail_for_simulation(
        self,
        snapshot: MarketSnapshot,
        phase_guardrail: dict,
    ) -> bool:
        if settings.enable_live_trading:
            return False
        if not self._snapshot_quality_allows_simulation_probe(snapshot):
            return False
        if not self._main_force_markup_confirmed(snapshot):
            return False
        best = phase_guardrail.get("best_match") or {}
        latest_phase = best.get("target_latest_phase") or phase_guardrail.get("target_latest_phase")
        if latest_phase == "distribution":
            return False
        score = self._phase_guardrail_score(phase_guardrail)
        if score > MAX_RELAXABLE_PHASE_GUARDRAIL_SCORE:
            return False
        return str(phase_guardrail.get("risk_level") or "") == "phase_distribution_guardrail"

    def _snapshot_quality_allows_simulation_probe(self, snapshot: MarketSnapshot) -> bool:
        quality = snapshot.metadata.get("data_quality")
        if quality == "fallback_profile":
            return False
        if quality == "realtime_quote_fallback":
            return self._main_force_markup_confirmed(snapshot)
        return True

    def _phase_guardrail_score(self, phase_guardrail: dict) -> float:
        best = phase_guardrail.get("best_match") or {}
        try:
            return float(best.get("score") or phase_guardrail.get("score") or 0)
        except (TypeError, ValueError):
            return 0.0

    def _main_force_markup_confirmed(self, snapshot: MarketSnapshot) -> bool:
        pct_change = snapshot.pct_change
        volume_ratio = snapshot.metadata.get("volume_ratio")
        five_day_pct = snapshot.metadata.get("five_day_pct")
        amount = snapshot.amount
        limit_up_threshold = float(snapshot.metadata.get("limit_up_threshold") or 9.8)
        high = snapshot.high or snapshot.price
        close_near_high = bool(high and snapshot.price >= float(high) * 0.985)

        strong_price = pct_change is not None and float(pct_change) >= min(limit_up_threshold, 9.8)
        strong_volume = (
            volume_ratio is not None and float(volume_ratio) >= 1.2
        ) or (
            amount is not None and float(amount) >= 100_000_000
        )
        trend_confirmed = five_day_pct is None or float(five_day_pct) >= 3.0
        return strong_price and strong_volume and close_near_high and trend_confirmed

    def _main_force_stage_ratio(self, snapshot: MarketSnapshot) -> float:
        pct_change = float(snapshot.pct_change or 0)
        volume_ratio = snapshot.metadata.get("volume_ratio")
        ratio = 0.03
        if pct_change >= 9.8 and volume_ratio is not None and float(volume_ratio) >= 2.0:
            ratio = 0.04
        return min(ratio, 0.05)

    def _relaxed_first_probe_quantity(self, price: float, stage_ratio: float) -> int:
        quantity = min(self._quantity(price, stage_ratio), settings.min_order_lot)
        max_amount = settings.default_cash * RELAXED_SIMULATION_FIRST_PROBE_CASH_RATIO
        if quantity * price > max_amount:
            return 0
        return quantity

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
