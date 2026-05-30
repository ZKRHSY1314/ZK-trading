from app.models import CandidateDecision, CandidateTier, DecisionAnalysis, KnowledgeContext, MarketSnapshot
from app.simulation.planner import SimulationPlanner


def test_planner_downgrades_fallback_to_observe(monkeypatch):
    class MockAnalyzer:
        def analyze(self, snapshot):
            decision = CandidateDecision(
                symbol=snapshot.symbol,
                score=90.0,
                tier=CandidateTier.strong,
                blocked=False,
                hits=[],
            )
            return DecisionAnalysis(
                snapshot=snapshot,
                decision=decision,
                knowledge=KnowledgeContext(),
            )

    monkeypatch.setattr("app.simulation.planner.DecisionAnalyzer", MockAnalyzer)

    snapshot = MarketSnapshot(
        symbol="SH600000",
        price=10.0,
        metadata={"data_quality": "fallback_profile", "profile_risk_level": "low"},
    )
    plan = SimulationPlanner().create_plan(snapshot)

    assert plan.tier == CandidateTier.watch
    assert plan.action == "observe"
    assert plan.allowed is False
    assert plan.quantity == 0
    assert plan.position_ratio == 0
