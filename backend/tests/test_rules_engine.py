import pytest
from app.models import MarketSnapshot, CandidateTier
from app.rules.engine import RuleEngine

def test_constitution_rules_score_zero():
    config = {
        "candidate_tiers": {"strong_min_score": 80, "watch_min_score": 60},
        "rules": [
            {
                "id": "constitution_no_high_position",
                "name": "不做高位股",
                "group": "constitution",
                "enabled": True,
                "weight": 100,  # Should be ignored by engine
                "hard_block": True,
                "params": {"max_price_to_high_ratio": 0.8}
            }
        ]
    }
    engine = RuleEngine(config)
    snapshot = MarketSnapshot(
        symbol="SH600000",
        price=10.0,
        historical_high=30.0,
        metadata={"high_250": 30.0}
    )
    decision = engine.evaluate(snapshot)
    
    assert not decision.blocked
    assert decision.score == 0.0  # Even though passed and weight=100
    assert decision.tier == CandidateTier.rejected

def test_hard_block_rejects_candidate():
    config = {
        "candidate_tiers": {"strong_min_score": 80, "watch_min_score": 60},
        "rules": [
            {
                "id": "constitution_no_high_position",
                "name": "不做高位股",
                "group": "constitution",
                "enabled": True,
                "weight": 0,
                "hard_block": True,
                "params": {"max_price_to_high_ratio": 0.5}
            },
            {
                "id": "dengzhan_low_position_limit_up",
                "name": "灯盏策略",
                "group": "strategy",
                "enabled": True,
                "weight": 100,
                "hard_block": False,
                "params": {"min_limit_up_pct": 9.9, "max_price_to_high_ratio": 0.9}
            }
        ]
    }
    engine = RuleEngine(config)
    snapshot = MarketSnapshot(
        symbol="SH600000",
        price=20.0,
        pct_change=10.0,
        historical_high=30.0,
        metadata={"high_250": 30.0}
    )
    # Ratio = 20/30 = 0.66 > 0.5, triggers constitution block
    decision = engine.evaluate(snapshot)
    
    assert decision.blocked
    assert decision.tier == CandidateTier.rejected


def test_risk_rule_does_not_create_strong_candidate():
    config = {
        "candidate_tiers": {"strong_min_score": 80, "watch_min_score": 60},
        "rules": [
            {
                "id": "risk_no_chasing_after_big_rise",
                "name": "risk",
                "group": "risk",
                "enabled": True,
                "weight": 100,
                "hard_block": False,
                "params": {"big_rise_pct": 20},
            }
        ],
    }
    decision = RuleEngine(config).evaluate(
        MarketSnapshot(
            symbol="SH600000",
            price=10.0,
            metadata={"five_day_pct": 5.0},
        )
    )

    assert decision.score == 0.0
    assert decision.tier == CandidateTier.rejected


def test_low_quality_data_caps_strong_candidate_at_watch():
    config = {
        "candidate_tiers": {"strong_min_score": 80, "watch_min_score": 60},
        "rules": [
            {
                "id": "dengzhan_forced_divergence",
                "name": "strategy",
                "group": "strategy",
                "enabled": True,
                "weight": 100,
                "hard_block": False,
                "params": {"min_volume_ratio": 1.5},
            }
        ],
    }
    decision = RuleEngine(config).evaluate(
        MarketSnapshot(
            symbol="SH600000",
            price=10.0,
            metadata={"volume_ratio": 2.0, "data_quality": "fallback_profile"},
        )
    )

    assert decision.score == 100.0
    assert decision.tier == CandidateTier.watch
