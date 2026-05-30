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

        if rule_id == "constitution_no_high_position":
            passed, reason = self.signals.is_low_position(snapshot, params)
        elif rule_id == "dengzhan_low_position_limit_up":
            passed, reason = self.signals.is_low_position_limit_up(snapshot, params)
        elif rule_id == "dengzhan_forced_divergence":
            passed, reason = self.signals.has_forced_divergence(snapshot, params)
        elif rule_id == "risk_no_chasing_after_big_rise":
            passed, reason = self.signals.no_chasing_after_big_rise(snapshot, params)
        else:
            passed, reason = False, f"规则 {rule_id} 尚未实现"

        score_delta = 0.0
        if passed and rule.get("group") not in ("constitution", "risk"):
            score_delta = float(rule.get("weight", 0))

        return RuleHit(
            rule_id=rule_id,
            name=rule["name"],
            group=rule["group"],
            passed=passed,
            score_delta=score_delta,
            hard_block=bool(rule.get("hard_block", False)),
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
