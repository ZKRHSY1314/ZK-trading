from typing import Any

from app.models import CandidateDecision, CandidateTier, MarketSnapshot, RuleHit
from app.strategies.dengzhan import DengZhanSignals


class RuleEngine:
    def __init__(self, config: dict):
        self.config = config
        self.signals = DengZhanSignals()

    def evaluate(self, snapshot: MarketSnapshot) -> CandidateDecision:
        hits: list[RuleHit] = []
        score = 0.0
        blocked = False

        for rule in self.config.get("rules", []):
            if not rule.get("enabled", True):
                continue

            hit = self._evaluate_rule(snapshot, rule)
            hits.append(hit)
            score += hit.score_delta
            blocked = blocked or (hit.hard_block and not hit.passed)

        tier = self._tier(score, blocked)
        if (
            tier == CandidateTier.strong
            and snapshot.metadata.get("data_quality") in {"fallback_profile", "realtime_quote_fallback"}
        ):
            tier = CandidateTier.watch
        return CandidateDecision(
            symbol=snapshot.symbol,
            name=snapshot.name,
            score=score,
            tier=tier,
            blocked=blocked,
            hits=hits,
        )

    def _evaluate_rule(self, snapshot: MarketSnapshot, rule: dict) -> RuleHit:
        rule_id = rule["id"]
        params = rule.get("params", {})
        threshold = dict(params) if isinstance(params, dict) else {}
        is_hard_block = bool(rule.get("hard_block", False))
        evidence: dict[str, Any] = {}
        hard_block_failed = False

        if rule_id == "constitution_no_high_position":
            passed, reason = self.signals.is_low_position(snapshot, params)
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
            passed, reason = self.signals.is_low_position_limit_up(snapshot, params)
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
            passed, reason = self.signals.has_forced_divergence(snapshot, params)
            if not passed and is_hard_block:
                hard_block_failed = True
                evidence = {
                    "symbol": snapshot.symbol,
                    "volume_ratio": snapshot.metadata.get("volume_ratio"),
                }
        elif rule_id == "risk_no_chasing_after_big_rise":
            passed, reason = self.signals.no_chasing_after_big_rise(snapshot, params)
            if not passed and is_hard_block:
                hard_block_failed = True
                evidence = {
                    "symbol": snapshot.symbol,
                    "five_day_pct": snapshot.metadata.get("five_day_pct"),
                }
        else:
            passed, reason = False, f"规则 {rule_id} 尚未实现"

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
