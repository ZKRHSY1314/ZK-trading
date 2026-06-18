import json

from app.models import CandidateDecision, CandidateTier, DecisionAnalysis, KnowledgeContext, MarketSnapshot
from app.models import RiskBlockCause, RuleHit
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


def test_planner_relaxes_high_position_for_confirmed_markup(monkeypatch):
    class MockAnalyzer:
        def analyze(self, snapshot):
            decision = CandidateDecision(
                symbol=snapshot.symbol,
                score=20.0,
                tier=CandidateTier.rejected,
                blocked=True,
                hits=[
                    RuleHit(
                        rule_id="constitution_no_high_position",
                        name="No high-position chase",
                        group="constitution",
                        passed=False,
                        hard_block=True,
                        reason="high-position red line",
                    )
                ],
            )
            return DecisionAnalysis(
                snapshot=snapshot,
                decision=decision,
                knowledge=KnowledgeContext(),
                risk_blocked=[
                    RiskBlockCause(
                        rule_id="constitution_no_high_position",
                        rule_name="No high-position chase",
                        reason="high-position red line",
                    )
                ],
            )

    class MockRegime:
        def get_latest_regime(self):
            return {"regime": "neutral", "reasons": []}

    monkeypatch.setattr("app.simulation.planner.DecisionAnalyzer", MockAnalyzer)
    monkeypatch.setattr("app.market_regime.service.MarketRegimeService", MockRegime)
    monkeypatch.setattr("app.simulation.planner.settings.default_cash", 200_000)

    snapshot = MarketSnapshot(
        symbol="SZ300593",
        name="markup",
        price=37.64,
        pct_change=19.99,
        high=37.64,
        amount=1_800_000_000,
        metadata={
            "data_quality": "daily_bar",
            "limit_up_threshold": 19.8,
            "volume_ratio": 1.3,
            "five_day_pct": 5.3,
        },
    )

    plan = SimulationPlanner().create_plan(snapshot)

    assert plan.allowed is True
    assert plan.action == "buy"
    assert plan.quantity == 100
    assert plan.position_ratio == 0.01882
    assert plan.risk_blocked == []
    assert "Simulation-only relaxation" in plan.reasons[0]
    assert "first probe capped" in plan.reasons[4]


def test_planner_keeps_high_position_block_without_markup_confirmation(monkeypatch):
    class MockAnalyzer:
        def analyze(self, snapshot):
            decision = CandidateDecision(
                symbol=snapshot.symbol,
                score=20.0,
                tier=CandidateTier.rejected,
                blocked=True,
                hits=[],
            )
            return DecisionAnalysis(
                snapshot=snapshot,
                decision=decision,
                knowledge=KnowledgeContext(),
                risk_blocked=[
                    RiskBlockCause(
                        rule_id="constitution_no_high_position",
                        rule_name="No high-position chase",
                        reason="high-position red line",
                    )
                ],
            )

    monkeypatch.setattr("app.simulation.planner.DecisionAnalyzer", MockAnalyzer)

    snapshot = MarketSnapshot(
        symbol="SZ300593",
        name="weak markup",
        price=37.64,
        pct_change=4.0,
        high=37.64,
        amount=30_000_000,
        metadata={
            "data_quality": "daily_bar",
            "limit_up_threshold": 19.8,
            "volume_ratio": 0.8,
            "five_day_pct": 2.0,
        },
    )

    plan = SimulationPlanner().create_plan(snapshot)

    assert plan.allowed is False
    assert plan.quantity == 0
    assert plan.blocked_reason == "constitution_no_high_position"


def test_planner_relaxes_phase_guardrail_for_confirmed_simulation_probe(monkeypatch):
    class MockAnalyzer:
        def analyze(self, snapshot):
            decision = CandidateDecision(
                symbol=snapshot.symbol,
                score=40.0,
                tier=CandidateTier.watch,
                blocked=False,
                hits=[],
            )
            return DecisionAnalysis(
                snapshot=snapshot,
                decision=decision,
                knowledge=KnowledgeContext(),
                risk_notes=["base phase risk note"],
            )

    monkeypatch.setattr("app.simulation.planner.DecisionAnalyzer", MockAnalyzer)
    monkeypatch.setattr("app.simulation.planner.settings.default_cash", 200_000)
    monkeypatch.setattr(
        SimulationPlanner,
        "_latest_phase_guardrail",
        lambda self, symbol: {
            "match_id": 140,
            "risk_level": "phase_distribution_guardrail",
            "reason": "similar to completed distribution sample",
            "best_match": {
                "core_symbol": "SZ002081",
                "score": 79.0,
                "target_latest_phase": "post_distribution_watch",
            },
            "diagnosis": "distribution-like phase warning",
        },
    )

    snapshot = MarketSnapshot(
        symbol="SZ301310",
        name="phase relaxed",
        price=46.75,
        pct_change=19.99,
        high=46.75,
        amount=820_000_000,
        metadata={
            "data_quality": "realtime_quote_fallback",
            "limit_up_threshold": 19.8,
            "five_day_pct": None,
        },
    )

    plan = SimulationPlanner().create_plan(snapshot)

    assert plan.allowed is True
    assert plan.action == "buy"
    assert plan.quantity == 100
    assert plan.position_ratio == 0.023375
    assert plan.risk_blocked == []
    assert plan.blocked_reason is None
    assert "Simulation-only phase guardrail relaxation" in plan.reasons[0]
    assert any("does not enable real orders" in note for note in plan.risk_notes)


def test_planner_keeps_phase_guardrail_hard_when_distribution_score_extreme(monkeypatch):
    class MockAnalyzer:
        def analyze(self, snapshot):
            decision = CandidateDecision(
                symbol=snapshot.symbol,
                score=40.0,
                tier=CandidateTier.watch,
                blocked=False,
                hits=[],
            )
            return DecisionAnalysis(
                snapshot=snapshot,
                decision=decision,
                knowledge=KnowledgeContext(),
            )

    monkeypatch.setattr("app.simulation.planner.DecisionAnalyzer", MockAnalyzer)
    monkeypatch.setattr(
        SimulationPlanner,
        "_latest_phase_guardrail",
        lambda self, symbol: {
            "match_id": 141,
            "risk_level": "phase_distribution_guardrail",
            "reason": "extremely similar to completed distribution sample",
            "best_match": {
                "core_symbol": "SZ002081",
                "score": 90.0,
                "target_latest_phase": "distribution",
            },
            "diagnosis": "hard distribution risk",
        },
    )

    snapshot = MarketSnapshot(
        symbol="SH688333",
        name="phase hard block",
        price=46.75,
        pct_change=20.0,
        high=46.75,
        amount=900_000_000,
        metadata={
            "data_quality": "realtime_quote_fallback",
            "limit_up_threshold": 19.8,
        },
    )

    plan = SimulationPlanner().create_plan(snapshot)

    assert plan.allowed is False
    assert plan.action == "observe"
    assert plan.quantity == 0
    assert plan.blocked_reason == "phase_guardrail"


def test_planner_adds_stable_candidate_review_without_position_change(monkeypatch, test_db):
    class MockAnalyzer:
        def analyze(self, snapshot):
            decision = CandidateDecision(
                symbol=snapshot.symbol,
                score=88.0,
                tier=CandidateTier.strong,
                blocked=False,
                hits=[],
            )
            return DecisionAnalysis(
                snapshot=snapshot,
                decision=decision,
                knowledge=KnowledgeContext(),
                risk_notes=["base risk note"],
            )

    class MockRegime:
        def get_latest_regime(self):
            return {"regime": "neutral", "reasons": []}

    selected_candidate = {
        "status": "passed_for_simulation_review",
        "review_only": True,
        "simulation_only": True,
        "parameters": {
            "entry_delay_days": 1,
            "horizon_days": 3,
            "confirmation_filter": "none",
            "attribution_filter": "turning_point_requires_green_or_strong",
            "buy_position_ratio": 0.08,
        },
        "source_validation_metrics": {
            "win_rate": 0.733333,
            "equal_weight_cumulative_return_pct": 199.532969,
        },
        "weighted_win_rate": 0.727273,
        "total_equal_weight_cumulative_return_pct": 1156.826633,
        "complete_window": {
            "schema_version": "signal_complete_backtest_window.v1",
            "status": "checked",
            "input_signal_count": 120,
            "eligible_signal_count": 51,
            "no_entry_bar_count": 14,
            "incomplete_exit_window_count": 55,
            "entry_delay_days": 1,
            "horizon_days": 3,
            "review_only": True,
            "simulation_only": True,
            "live_trading_enabled": False,
        },
    }
    with test_db.connect() as conn:
        conn.execute("DELETE FROM offhour_research_runs")
        conn.execute(
            """
            INSERT INTO offhour_research_runs(
                mode, status, requested_by, backtest_json, next_action,
                review_only, simulation_only, live_trading_enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "balanced_search_replay",
                "completed",
                "pytest",
                json.dumps(
                    {
                        "dataset2_signal_optimization": {
                            "status": "passed_for_simulation_review",
                            "selected_stable_candidate": selected_candidate,
                            "optimization_budget": {
                                "learning_filter_budget": {
                                    "accepted_candidate_count": 48,
                                    "filter_count": 4,
                                    "review_only": True,
                                    "simulation_only": True,
                                    "live_trading_enabled": False,
                                },
                                "complete_window": {
                                    "checks": [selected_candidate["complete_window"]],
                                    "review_only": True,
                                    "simulation_only": True,
                                    "live_trading_enabled": False,
                                },
                            },
                            "learning_filter_candidates": [
                                {
                                    "parameters": {
                                        "entry_delay_days": 1,
                                        "horizon_days": 3,
                                        "confirmation_filter": "strong_reclaim",
                                        "attribution_filter": "star_and_turning_point_quality_gate",
                                    },
                                    "validation_metrics": {
                                        "win_rate": 0.846154,
                                        "equal_weight_cumulative_return_pct": 240.302267,
                                    },
                                    "review_only": True,
                                    "simulation_only": True,
                                }
                            ],
                            "stable_candidate_tracks": {
                                "schema_version": "stable_candidate_tracks.v1",
                                "broad_momentum_candidate": {
                                    "track": "broad_momentum_candidate",
                                    "status": "blocked",
                                    "reasons": ["fixture broad track absent"],
                                    "candidate": None,
                                    "review_only": True,
                                    "simulation_only": True,
                                },
                                "dataset1_stabilized_candidate": {
                                    "track": "dataset1_stabilized_candidate",
                                    "status": "passed_for_simulation_review",
                                    "reasons": [],
                                    "candidate": selected_candidate,
                                    "review_only": True,
                                    "simulation_only": True,
                                },
                                "review_only": True,
                                "simulation_only": True,
                                "live_trading_enabled": False,
                            },
                            "track_tradeoff_attribution": {
                                "schema_version": "stable_candidate_tradeoff_attribution.v1",
                                "status": "completed",
                                "broad_only_summary": {
                                    "count": 1,
                                    "average_return_pct": -6.0,
                                },
                                "broad_only_tag_summary": {
                                    "trade_count": 1,
                                    "phase_counts": {"distribution_or_failed_markup": 1},
                                    "learning_tag_counts": {
                                        "broad_only_risk": 1,
                                        "distribution_or_stall_risk": 1,
                                    },
                                    "risk_trade_count": 1,
                                    "hard_risk_trade_count": 1,
                                    "opportunity_trade_count": 0,
                                    "mixed_opportunity_risk_count": 0,
                                    "review_only": True,
                                    "simulation_only": True,
                                },
                                "broad_only_supervision": {
                                    "schema_version": "broad_only_supervision.v1",
                                    "status": "completed",
                                    "enhanced_watch_track": {
                                        "track": "broad_only_enhanced_watch",
                                        "status": "candidate",
                                        "raw_opportunity_count": 4,
                                        "sample_count": 3,
                                        "secondary_confirmation_rejected_count": 1,
                                        "confirmation_summary": {
                                            "candidate_count": 4,
                                            "passed_count": 3,
                                            "failed_count": 1,
                                            "review_only": True,
                                            "simulation_only": True,
                                        },
                                        "suggested_review_position_ratio": 0.02,
                                        "review_only": True,
                                        "simulation_only": True,
                                    },
                                    "near_reclaim_watch_track": {
                                        "track": "broad_only_near_reclaim_watch",
                                        "status": "watch_for_reclaim",
                                        "sample_count": 1,
                                        "review_only": True,
                                        "simulation_only": True,
                                    },
                                    "failed_markup_block": {
                                        "track": "broad_only_failed_markup_block",
                                        "status": "active",
                                        "sample_count": 1,
                                        "review_only": True,
                                        "simulation_only": True,
                                    },
                                    "review_only": True,
                                    "simulation_only": True,
                                    "live_trading_enabled": False,
                                },
                                "shared_signal_return_delta_summary": {
                                    "count": 2,
                                    "average_return_pct": 0.5,
                                },
                                "verdict": {
                                    "label": "stabilization_filter_reduced_risk",
                                    "next_action": "prefer_dataset1_stabilized_candidate_for_simulated_entry_review",
                                },
                                "review_only": True,
                                "simulation_only": True,
                            },
                        }
                    }
                ),
                "review_only",
                1,
                1,
                0,
            ),
        )

    monkeypatch.setattr("app.simulation.planner.DecisionAnalyzer", MockAnalyzer)
    monkeypatch.setattr("app.market_regime.service.MarketRegimeService", MockRegime)
    monkeypatch.setattr("app.simulation.planner.settings.default_cash", 200_000)

    snapshot = MarketSnapshot(
        symbol="SZ002081",
        name="stable review",
        price=10.0,
        metadata={"data_quality": "daily_bar", "profile_risk_level": "low"},
    )

    plan = SimulationPlanner().create_plan(snapshot)

    assert plan.allowed is True
    assert plan.action == "buy"
    assert plan.position_ratio == 0.10
    assert plan.quantity == 2000
    assert any("track=dataset1_stabilized_candidate" in reason for reason in plan.reasons)
    assert any("does not change production rules" in note for note in plan.risk_notes)
    assert any("validation_return=199.53%" in note for note in plan.risk_notes)
    assert any("complete-window evidence" in note for note in plan.risk_notes)
    assert any("eligible_signals=51" in note for note in plan.risk_notes)
    assert any("incomplete_exit_window=55" in note for note in plan.risk_notes)
    assert any("Learning-filter evidence" in note for note in plan.risk_notes)
    assert any("accepted_candidates=48" in note for note in plan.risk_notes)
    assert any("top_attribution=star_and_turning_point_quality_gate" in note for note in plan.risk_notes)
    assert any("broad_momentum_candidate=blocked" in note for note in plan.risk_notes)
    assert any("attribution=turning_point_requires_green_or_strong" in note for note in plan.risk_notes)
    assert any("stabilization_filter_reduced_risk" in note for note in plan.risk_notes)
    assert any("broad_only_risk_trades=1" in note for note in plan.risk_notes)
    assert any("broad_only_hard_risk_trades=1" in note for note in plan.risk_notes)
    assert any("enhanced_watch=candidate" in note for note in plan.risk_notes)
    assert any("raw=4, confirmed=3, rejected=1" in note for note in plan.risk_notes)
    assert any("near_reclaim_watch=watch_for_reclaim" in note for note in plan.risk_notes)
    assert any("failed_markup_block=active" in note for note in plan.risk_notes)
    assert any("distribution_or_failed_markup:1" in note for note in plan.risk_notes)


def test_planner_adds_rule_family_memory_without_position_change(monkeypatch, test_db):
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
                risk_notes=["base risk note"],
            )

    class MockRegime:
        def get_latest_regime(self):
            return {"regime": "neutral", "reasons": []}

    with test_db.connect() as conn:
        conn.execute("DELETE FROM offhour_research_runs")
        conn.execute("DELETE FROM events WHERE event_type = 'dataset2_training_run'")
        conn.execute(
            """
            INSERT INTO events(event_type, payload_json)
            VALUES (?, ?)
            """,
            (
                "dataset2_training_run",
                json.dumps(
                    {
                        "rule_family_performance_memory": {
                            "schema_version": "dataset2_rule_family_performance_memory.v1",
                            "summary": {
                                "staging_group_count": 12,
                                "backtest_trade_count": 20,
                            },
                            "top_backtest_groups": [
                                {
                                    "pattern_id": "LEGACY_VP_SINGLE_001",
                                    "pattern_name": "放量大阳线",
                                    "action_label": "SIM_BUY_CANDIDATE",
                                    "trade_count": 20,
                                    "win_rate": 0.65,
                                    "average_return_pct": 3.5,
                                    "worst_return_pct": -4.0,
                                    "review_only": True,
                                    "simulation_only": True,
                                }
                            ],
                            "review_only": True,
                            "simulation_only": True,
                            "live_trading_enabled": False,
                        },
                        "review_only": True,
                        "simulation_only": True,
                        "live_trading_enabled": False,
                    },
                    ensure_ascii=False,
                ),
            ),
        )

    monkeypatch.setattr("app.simulation.planner.DecisionAnalyzer", MockAnalyzer)
    monkeypatch.setattr("app.market_regime.service.MarketRegimeService", MockRegime)
    monkeypatch.setattr("app.simulation.planner.settings.default_cash", 200_000)

    snapshot = MarketSnapshot(
        symbol="SZ002081",
        name="rule family review",
        price=10.0,
        metadata={"data_quality": "daily_bar", "profile_risk_level": "low"},
    )

    plan = SimulationPlanner().create_plan(snapshot)

    assert plan.allowed is True
    assert plan.action == "buy"
    assert plan.position_ratio == 0.10
    assert plan.quantity == 2000
    assert any("Dataset2 rule-family performance memory" in note for note in plan.risk_notes)
    assert any("top_family=LEGACY_VP_SINGLE_001/放量大阳线/SIM_BUY_CANDIDATE" in note for note in plan.risk_notes)
    assert any("does not change action, allowed, quantity" in note for note in plan.risk_notes)


def test_planner_selects_best_recent_stable_candidate_not_latest(test_db):
    def stable_candidate(
        *,
        validation_return: float,
        validation_win: float,
        walk_forward_return: float,
        walk_forward_win: float,
        trade_count: int,
        horizon: int,
    ) -> dict:
        return {
            "status": "passed_for_simulation_review",
            "review_only": True,
            "simulation_only": True,
            "parameters": {
                "entry_delay_days": 1,
                "horizon_days": horizon,
                "confirmation_filter": "strong_reclaim",
                "attribution_filter": "star_and_turning_point_quality_gate",
            },
            "source_validation_metrics": {
                "win_rate": validation_win,
                "equal_weight_cumulative_return_pct": validation_return,
            },
            "weighted_win_rate": walk_forward_win,
            "total_equal_weight_cumulative_return_pct": walk_forward_return,
            "trade_count": trade_count,
            "min_fold_win_rate": 0.58,
            "min_fold_cumulative_return_pct": 16.0,
        }

    stronger_older = stable_candidate(
        validation_return=240.0,
        validation_win=0.84,
        walk_forward_return=1156.0,
        walk_forward_win=0.72,
        trade_count=33,
        horizon=3,
    )
    weaker_latest = stable_candidate(
        validation_return=65.0,
        validation_win=0.69,
        walk_forward_return=211.0,
        walk_forward_win=0.66,
        trade_count=33,
        horizon=8,
    )

    def payload(candidate: dict) -> str:
        return json.dumps(
            {
                "dataset2_signal_optimization": {
                    "status": "passed_for_simulation_review",
                    "selected_stable_candidate": candidate,
                    "stable_candidate_tracks": {
                        "dataset1_stabilized_candidate": {
                            "status": "passed_for_simulation_review",
                            "candidate": candidate,
                            "review_only": True,
                            "simulation_only": True,
                        },
                        "review_only": True,
                        "simulation_only": True,
                    },
                    "review_only": True,
                    "simulation_only": True,
                }
            }
        )

    with test_db.connect() as conn:
        conn.execute("DELETE FROM offhour_research_runs")
        strong_cursor = conn.execute(
            """
            INSERT INTO offhour_research_runs(
                mode, status, requested_by, backtest_json,
                review_only, simulation_only, live_trading_enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("balanced_search_replay", "completed", "pytest", payload(stronger_older), 1, 1, 0),
        )
        strong_run_id = strong_cursor.lastrowid
        conn.execute(
            """
            INSERT INTO offhour_research_runs(
                mode, status, requested_by, backtest_json,
                review_only, simulation_only, live_trading_enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("balanced_search_replay", "completed", "pytest", payload(weaker_latest), 1, 1, 0),
        )

    context = SimulationPlanner()._latest_stable_candidate_context()

    assert context is not None
    assert context["run_id"] == strong_run_id
    assert context["candidate"]["parameters"]["horizon_days"] == 3
    assert context["selection"]["selected_from_candidate_count"] == 2
    assert context["selection"]["policy"] == "best_recent_passed_candidate"


def test_planner_adds_reclaim_watch_context_without_position_change(monkeypatch, test_db):
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
                risk_notes=["base risk note"],
            )

    class MockRegime:
        def get_latest_regime(self):
            return {"regime": "neutral", "reasons": []}

    with test_db.connect() as conn:
        conn.execute(
            """
            INSERT INTO offhour_research_runs(
                mode, status, requested_by, backtest_json, next_action,
                review_only, simulation_only, live_trading_enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "balanced_search_replay",
                "completed",
                "pytest",
                json.dumps(
                    {
                        "dataset2_reclaim_watchlist": {
                            "schema_version": "reclaim_watchlist.v1",
                            "items": [
                                {
                                    "symbol": "SH600011",
                                    "status": "reclaim_review",
                                    "signal_date": "2026-06-12",
                                    "latest_trade_date": "2026-06-15",
                                    "close_vs_signal_pct": 1.25,
                                    "allowed_effect": "raise_review_priority_and_dry_run_only",
                                    "risk_tags": ["top_risk"],
                                    "review_only": True,
                                    "simulation_only": True,
                                }
                            ],
                            "review_only": True,
                            "simulation_only": True,
                            "live_trading_enabled": False,
                        },
                        "dataset2_reclaim_transition_study": {
                            "schema_version": "reclaim_transition_study.v1",
                            "risk_tag_attribution": {
                                "by_status_tag": [
                                    {
                                        "key": "reclaim_review:top_risk",
                                        "sample_count": 52,
                                        "win_rate": 0.653846,
                                        "average_return_pct": 2.207487,
                                        "suggested_treatment": "downgrade_to_smallest_dry_run_or_observe",
                                        "review_only": True,
                                        "simulation_only": True,
                                    }
                                ]
                            },
                            "review_only": True,
                            "simulation_only": True,
                        }
                    }
                ),
                "review_only",
                1,
                1,
                0,
            ),
        )

    monkeypatch.setattr("app.simulation.planner.DecisionAnalyzer", MockAnalyzer)
    monkeypatch.setattr("app.market_regime.service.MarketRegimeService", MockRegime)
    monkeypatch.setattr("app.simulation.planner.settings.default_cash", 200_000)

    snapshot = MarketSnapshot(
        symbol="SH600011",
        name="reclaim review",
        price=10.0,
        metadata={"data_quality": "daily_bar", "profile_risk_level": "low"},
    )

    plan = SimulationPlanner().create_plan(snapshot)

    assert plan.allowed is True
    assert plan.action == "buy"
    assert plan.position_ratio == 0.10
    assert plan.quantity == 2000
    assert any("Dataset2 reclaim watch context" in note for note in plan.risk_notes)
    assert any("status=reclaim_review" in note for note in plan.risk_notes)
    assert any("dry-run evidence only" in note for note in plan.risk_notes)
    assert any("Risk attribution context: reclaim_review:top_risk" in note for note in plan.risk_notes)
    assert any("treatment=downgrade_to_smallest_dry_run_or_observe" in note for note in plan.risk_notes)
    assert any("not to increase size" in note for note in plan.risk_notes)
    assert any("does not change action, allowed, quantity" in note for note in plan.risk_notes)


def test_planner_adds_phase_similarity_context_without_position_change(monkeypatch, test_db):
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
                risk_notes=["base risk note"],
            )

    class MockRegime:
        def get_latest_regime(self):
            return {"regime": "neutral", "reasons": []}

    with test_db.connect() as conn:
        conn.execute(
            """
            INSERT INTO offhour_research_runs(
                mode, status, requested_by, backtest_json, next_action,
                review_only, simulation_only, live_trading_enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "balanced_search_replay",
                "completed",
                "pytest",
                json.dumps(
                    {
                        "phase_similarity_performance": {
                            "schema_version": "phase_similarity_performance.v1",
                            "status": "completed",
                            "by_group": [
                                {
                                    "key": "SZ002081:post_distribution_watch",
                                    "core_symbol": "SZ002081",
                                    "target_latest_phase": "post_distribution_watch",
                                    "sample_count": 5,
                                    "win_rate": 0.6,
                                    "average_close_return_pct": 2.99,
                                    "average_min_return_pct": -2.5,
                                    "suggested_treatment": "observe_only_distribution_risk",
                                    "confidence_tier": "observe_only_distribution_risk_confidence",
                                    "confidence_score": 45,
                                    "confidence_reasons": [
                                        "sample_count>=5",
                                        "win_rate>=60%",
                                        "distribution_path_caps_confidence",
                                    ],
                                    "downside_risk_note": "average intratrade downside is moderate; require small dry-run sizing.",
                                    "review_only": True,
                                    "simulation_only": True,
                                }
                            ],
                            "items": [
                                {
                                    "symbol": "SH600012",
                                    "signal_date": "2026-06-12",
                                    "pattern_id": "TEST_BIG_YANG_001",
                                    "group_key": "SZ002081:post_distribution_watch",
                                    "best_match": {
                                        "core_symbol": "SZ002081",
                                        "sample_role": "金螳螂拉升出货完成样本",
                                        "score": 82.0,
                                        "target_latest_phase": "post_distribution_watch",
                                    },
                                    "review_only": True,
                                    "simulation_only": True,
                                }
                            ],
                            "review_only": True,
                            "simulation_only": True,
                            "live_trading_enabled": False,
                        }
                    }
                ),
                "review_only",
                1,
                1,
                0,
            ),
        )

    monkeypatch.setattr("app.simulation.planner.DecisionAnalyzer", MockAnalyzer)
    monkeypatch.setattr("app.market_regime.service.MarketRegimeService", MockRegime)
    monkeypatch.setattr("app.simulation.planner.settings.default_cash", 200_000)

    snapshot = MarketSnapshot(
        symbol="SH600012",
        name="phase similarity",
        price=10.0,
        metadata={"data_quality": "daily_bar", "profile_risk_level": "low"},
    )

    plan = SimulationPlanner().create_plan(snapshot)

    assert plan.allowed is True
    assert plan.action == "buy"
    assert plan.position_ratio == 0.10
    assert plan.quantity == 2000
    assert any("Phase similarity context" in note for note in plan.risk_notes)
    assert any("core=SZ002081" in note for note in plan.risk_notes)
    assert any("treatment=observe_only_distribution_risk" in note for note in plan.risk_notes)
    assert any("confidence_tier=observe_only_distribution_risk_confidence" in note for note in plan.risk_notes)
    assert any("confidence_score=45" in note for note in plan.risk_notes)
    assert any("distribution-like phase evidence" in note for note in plan.risk_notes)
    assert any("does not change action, allowed, quantity" in note for note in plan.risk_notes)


def test_planner_adds_simulation_review_plan_confidence_without_position_change(monkeypatch, test_db):
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
                risk_notes=["base risk note"],
            )

    class MockRegime:
        def get_latest_regime(self):
            return {"regime": "neutral", "reasons": []}

    with test_db.connect() as conn:
        conn.execute(
            """
            INSERT INTO offhour_research_runs(
                mode, status, requested_by, backtest_json, artifact_json, next_action,
                review_only, simulation_only, live_trading_enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "balanced_search_replay",
                "completed",
                "pytest",
                "{}",
                json.dumps(
                    {
                        "simulation_review_plan": {
                            "schema_version": "simulation_review_plan.v1",
                            "status": "ready_for_dry_run_review",
                            "permission_policy": {
                                "may_submit_order": False,
                                "may_enable_screen_click": False,
                            },
                            "candidates": [
                                {
                                    "symbol": "SH603120",
                                    "recommended_mode": "dry_run_screen_candidate",
                                    "priority_score": 182.849948,
                                    "confidence_adjusted_priority_score": 151.765457,
                                    "position_plan": {"max_initial_cash": 4000.0},
                                    "best_strategy": {
                                        "experiment_id": "base_shadow_candidate",
                                        "win_rate": 0.75,
                                        "average_return_pct": 4.5,
                                    },
                                    "blockers": [],
                                    "caution_flags": [],
                                    "evidence_quality": {
                                        "schema_version": "simulation_candidate_evidence_quality.v1",
                                        "confidence_tier": "high_confidence_dry_run_review",
                                        "confidence_score": 83.0,
                                        "reasons": [
                                            "walk_forward_passed",
                                            "market_context_robust",
                                            "cumulative_return_above_20_pct_gate",
                                        ],
                                        "review_only": True,
                                        "simulation_only": True,
                                        "live_trading_enabled": False,
                                    },
                                    "review_only": True,
                                    "simulation_only": True,
                                    "live_trading_enabled": False,
                                }
                            ],
                            "review_only": True,
                            "simulation_only": True,
                            "live_trading_enabled": False,
                        }
                    }
                ),
                "review_only",
                1,
                1,
                0,
            ),
        )

    monkeypatch.setattr("app.simulation.planner.DecisionAnalyzer", MockAnalyzer)
    monkeypatch.setattr("app.market_regime.service.MarketRegimeService", MockRegime)
    monkeypatch.setattr("app.simulation.planner.settings.default_cash", 200_000)

    snapshot = MarketSnapshot(
        symbol="SH603120",
        name="simulation review confidence",
        price=10.0,
        metadata={"data_quality": "daily_bar", "profile_risk_level": "low"},
    )

    plan = SimulationPlanner().create_plan(snapshot)

    assert plan.allowed is True
    assert plan.action == "buy"
    assert plan.position_ratio == 0.10
    assert plan.quantity == 2000
    assert any("Latest offhour simulation review plan context" in note for note in plan.risk_notes)
    assert any("confidence_tier=high_confidence_dry_run_review" in note for note in plan.risk_notes)
    assert any("confidence_score=83.0" in note for note in plan.risk_notes)
    assert any("max_initial_cash=4000.0" in note for note in plan.risk_notes)
    assert any("submit=False, screen_click=False" in note for note in plan.risk_notes)
    assert any("does not change action, allowed, quantity" in note for note in plan.risk_notes)
