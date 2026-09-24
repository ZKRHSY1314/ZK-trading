import itertools
import logging
from typing import Any

from app.models import CandidateDecision, CandidateTier, MarketSnapshot, RuleHit
from app.strategies.dengzhan import UNKNOWN, DengZhanSignals, SignalResult

logger = logging.getLogger(__name__)


class RuleEngine:
    def __init__(self, config: dict):
        self.config = config
        self.signals = DengZhanSignals()
        logger.info("rule engine tier reachability: %s", self.tier_reachability())

    def evaluate(self, snapshot: MarketSnapshot) -> CandidateDecision:
        hits: list[RuleHit] = []
        raw_score = 0.0
        blocked = False

        for rule in self.config.get("rules", []):
            if not rule.get("enabled", True):
                continue

            hit = self._evaluate_rule(snapshot, rule)
            hits.append(hit)
            raw_score += hit.score_delta
            blocked = blocked or (hit.hard_block and not hit.passed)

        max_score = self._max_strategy_score()
        # The configured thresholds use a 0-100 scale, while individual
        # strategy weights are intentionally small and auditable. Normalize
        # only enabled positive strategy weights so the default policy can
        # actually reach its configured tiers without changing rules.yaml.
        score = self._normalized_score(raw_score, max_score)
        soft_risk_failed = any(
            hit.group == "risk" and not hit.hard_block and not hit.passed
            for hit in hits
        )
        tier = self._tier(score, blocked)
        if tier == CandidateTier.strong and soft_risk_failed:
            tier = CandidateTier.watch
        if (
            tier == CandidateTier.strong
            and snapshot.metadata.get("data_quality") in {"fallback_profile", "realtime_quote_fallback"}
        ):
            tier = CandidateTier.watch
        unknown_rule_ids = [hit.rule_id for hit in hits if hit.evaluation == UNKNOWN]
        missing_inputs = sorted({name for hit in hits for name in hit.missing_inputs})
        return CandidateDecision(
            symbol=snapshot.symbol,
            name=snapshot.name,
            unknown_rule_ids=unknown_rule_ids,
            missing_inputs=missing_inputs,
            score=score,
            raw_score=round(raw_score, 6),
            max_score=round(max_score, 6),
            soft_risk_failed=soft_risk_failed,
            tier=tier,
            blocked=blocked,
            hits=hits,
        )

    def tier_reachability(self) -> dict[str, Any]:
        """Which combinations of enabled strategy rules can actually reach a tier.

        A configuration where no combination reaches ``strong`` produces zero
        entries no matter what the market does. That must be visible at startup,
        not discovered after a backtest returns no trades.
        """

        strategy_rules = [
            (str(rule["id"]), max(0.0, float(rule.get("weight", 0))))
            for rule in self.config.get("rules", [])
            if rule.get("enabled", True) and rule.get("group") == "strategy"
        ]
        max_score = sum(weight for _, weight in strategy_rules)
        tiers = self.config.get("candidate_tiers", {})
        report: dict[str, Any] = {"max_strategy_score": max_score}
        for tier_name, key in (("strong", "strong_min_score"), ("watch", "watch_min_score")):
            threshold = float(tiers.get(key, 80 if tier_name == "strong" else 60))
            combos = []
            for size in range(1, len(strategy_rules) + 1):
                for combo in itertools.combinations(strategy_rules, size):
                    raw = sum(weight for _, weight in combo)
                    if self._normalized_score(raw, max_score) >= threshold:
                        combos.append(sorted(rule_id for rule_id, _ in combo))
            minimal = [
                combo
                for combo in combos
                if not any(set(other) < set(combo) for other in combos)
            ]
            report[tier_name] = {
                "min_score": threshold,
                "reachable": bool(minimal),
                "minimal_rule_sets": minimal,
            }
        return report

    def _max_strategy_score(self) -> float:
        return sum(
            max(0.0, float(rule.get("weight", 0)))
            for rule in self.config.get("rules", [])
            if rule.get("enabled", True) and rule.get("group") == "strategy"
        )

    def _normalized_score(self, raw_score: float, max_score: float) -> float:
        if max_score <= 0:
            return 0.0
        return round(max(0.0, min(100.0, raw_score / max_score * 100.0)), 6)

    def _evaluate_rule(self, snapshot: MarketSnapshot, rule: dict) -> RuleHit:
        rule_id = rule["id"]
        params = rule.get("params", {})
        threshold = dict(params) if isinstance(params, dict) else {}
        is_hard_block = bool(rule.get("hard_block", False))
        evidence: dict[str, Any] = {}
        hard_block_failed = False

        if rule_id == "constitution_no_high_position":
            result = self.signals.is_low_position(snapshot, params)
            passed, reason = result.passed, result.reason
            if not passed and is_hard_block:
                hard_block_failed = True
                evidence = {
                    "symbol": snapshot.symbol,
                    "price": snapshot.price,
                    "high_reference": float(
                        snapshot.metadata.get("rolling_high_250")
                        or snapshot.metadata.get("high_250")
                        or snapshot.historical_high
                        or 0
                    ),
                }
        elif rule_id == "dengzhan_low_position_limit_up":
            result = self.signals.is_low_position_limit_up(snapshot, params)
            passed, reason = result.passed, result.reason
            if not passed and is_hard_block:
                hard_block_failed = True
                evidence = {
                    "symbol": snapshot.symbol,
                    "price": snapshot.price,
                    "pct_change": snapshot.pct_change,
                    "pb": snapshot.pb,
                    "market_cap_billion": snapshot.market_cap_billion,
                    "limit_up_threshold": snapshot.metadata.get("limit_up_threshold"),
                }
        elif rule_id == "dengzhan_forced_divergence":
            result = self.signals.has_forced_divergence(snapshot, params)
            passed, reason = result.passed, result.reason
            if not passed and is_hard_block:
                hard_block_failed = True
                evidence = {
                    "symbol": snapshot.symbol,
                    "volume_ratio": snapshot.metadata.get("volume_ratio"),
                }
        elif rule_id == "risk_no_chasing_after_big_rise":
            result = self.signals.no_chasing_after_big_rise(snapshot, params)
            passed, reason = result.passed, result.reason
            if not passed and is_hard_block:
                hard_block_failed = True
                evidence = {
                    "symbol": snapshot.symbol,
                    "five_day_pct": snapshot.metadata.get("five_day_pct"),
                }
        else:
            reason = f"规则 {rule_id} 尚未实现"
            result = SignalResult(False, reason, UNKNOWN, ("rule_implementation",))
            passed = False

            if is_hard_block:
                hard_block_failed = True

        score_delta = 0.0
        if passed and rule.get("group") not in ("constitution", "risk"):
            score_delta = float(rule.get("weight", 0))

        return RuleHit(
            rule_id=rule_id,
            name=rule["name"],
            group=rule["group"],
            passed=passed,
            score_delta=score_delta,
            hard_block=is_hard_block,
            threshold=threshold if is_hard_block and not passed else None,
            evidence=evidence if hard_block_failed else None,
            evidence_snippet=reason,
            layer="rules",
            trigger_level="hard" if is_hard_block else "soft",
            source="rules-engine",
            reason=reason,
            evaluation=result.status,
            missing_inputs=list(result.missing),
        )

    def _tier(self, score: float, blocked: bool) -> CandidateTier:
        if blocked:
            return CandidateTier.rejected

        tiers = self.config.get("candidate_tiers", {})
        if score >= tiers.get("strong_min_score", 80):
            return CandidateTier.strong
        if score >= tiers.get("watch_min_score", 60):
            return CandidateTier.watch
        return CandidateTier.rejected
