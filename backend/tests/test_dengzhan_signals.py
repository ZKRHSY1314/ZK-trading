from app.models import MarketSnapshot
from app.strategies.dengzhan import UNKNOWN, DengZhanSignals

def test_dynamic_limit_up_threshold():
    signals = DengZhanSignals()
    params = {"max_price_to_high_ratio": 0.5, "min_market_cap_billion": 10, "max_market_cap_billion": 200}
    
    # 创业板 19.8%
    snap_chinext = MarketSnapshot(
        symbol="SZ300001",
        price=10.0,
        pct_change=19.8,
        historical_high=30.0,
        market_cap_billion=50.0,
        metadata={"rolling_high_250": 30.0, "limit_up_threshold": 19.5}
    )
    passed, reason = signals.is_low_position_limit_up(snap_chinext, params)
    assert passed
    
    # ST 4.9%
    snap_st = MarketSnapshot(
        symbol="SZ000001",
        price=10.0,
        pct_change=4.9,
        historical_high=30.0,
        market_cap_billion=50.0,
        metadata={"rolling_high_250": 30.0, "limit_up_threshold": 4.8}
    )
    passed, reason = signals.is_low_position_limit_up(snap_st, params)
    assert passed

def test_market_cap_filter():
    signals = DengZhanSignals()
    params = {"max_price_to_high_ratio": 0.5, "min_market_cap_billion": 50, "max_market_cap_billion": 200}
    
    # Missing market cap
    snap_missing = MarketSnapshot(
        symbol="SH600000", price=10.0, pct_change=10.0, historical_high=30.0,
        metadata={"limit_up_threshold": 9.8}
    )
    passed, reason = signals.is_low_position_limit_up(snap_missing, params)
    assert not passed
    assert "缺少" in reason
    
    # Below min
    snap_small = MarketSnapshot(
        symbol="SH600000", price=10.0, pct_change=10.0, historical_high=30.0,
        market_cap_billion=30.0,
        metadata={"limit_up_threshold": 9.8}
    )
    passed, reason = signals.is_low_position_limit_up(snap_small, params)
    assert not passed
    assert "低于下限" in reason


def test_missing_pb_is_unknown_when_the_rule_requires_it():
    result = DengZhanSignals().is_low_position_limit_up(
        MarketSnapshot(
            symbol="SH600000",
            price=10.0,
            pct_change=10.0,
            historical_high=30.0,
            pb=None,
            market_cap_billion=100.0,
            metadata={"limit_up_threshold": 9.8},
        ),
        {
            "max_price_to_high_ratio": 0.5,
            "max_pb": 6.0,
            "min_market_cap_billion": 50,
            "max_market_cap_billion": 200,
        },
    )

    assert result.passed is False
    assert result.status == UNKNOWN
    assert result.missing == ("pb",)

def test_rolling_high_preference():
    signals = DengZhanSignals()
    params = {"max_price_to_high_ratio": 0.5}
    
    # 历史最高30, 250日最高15, 当前价10. 如果用历史最高 10/30=0.33 < 0.5
    # 但如果用250日最高 10/15=0.66 > 0.5 (should fail)
    snap = MarketSnapshot(
        symbol="SH600000", price=10.0, historical_high=30.0,
        metadata={"rolling_high_250": 15.0}
    )
    passed, reason = signals.is_low_position(snap, params)
    assert not passed
    assert "0.67" in reason or "0.66" in reason or "触发高位" in reason


def _armed_params(**overrides):
    params = {
        "max_price_to_high_ratio": 0.5,
        "min_limit_up_pct": 9.9,
        "min_market_cap_billion": 50,
        "max_market_cap_billion": 200,
        "armed_window_days": 5,
    }
    params.update(overrides)
    return params


def _quiet_bar(armed_age):
    """Low position and inside the cap band, but no limit up on this bar."""
    return MarketSnapshot(
        symbol="SH600000",
        price=10.0,
        pct_change=1.2,
        historical_high=30.0,
        market_cap_billion=80.0,
        metadata={
            "rolling_high_250": 30.0,
            "limit_up_threshold": 9.8,
            "dengzhan_armed_age": armed_age,
        },
    )


def test_armed_window_admits_a_divergence_that_arrives_on_a_later_bar():
    """IDLE -> ARMED -> ENTRY: S0 arms, confirmation may come later.

    Same-bar-only admits 77 entries market-wide over 20 months where the
    sequenced form admits 124, so this is a different strategy rather than a
    tweak. The S0 gate itself is unchanged - only *when* it may be satisfied.
    """

    signals = DengZhanSignals()

    # Armed two bars ago: the S0 condition was met then, so a quiet bar today
    # still carries it and only needs the divergence rule to fire.
    assert signals.is_low_position_limit_up(_quiet_bar(2), _armed_params()).passed

    # The bar the S0 itself fired on is age 0 and passes on its own merits.
    assert signals.same_bar_s0(
        MarketSnapshot(
            symbol="SH600000",
            price=10.0,
            pct_change=10.0,
            historical_high=30.0,
            market_cap_billion=80.0,
            metadata={"rolling_high_250": 30.0, "limit_up_threshold": 9.8},
        ),
        _armed_params(),
    ).passed


def test_armed_window_expires_and_can_be_switched_off():
    signals = DengZhanSignals()

    # Past the window the carry-over is gone and the bar is judged on its own.
    assert not signals.is_low_position_limit_up(_quiet_bar(6), _armed_params()).passed

    # armed_window_days=0 restores the previous same-bar-only contract, so the
    # sequencing is a configured choice and not a silent behaviour change.
    assert not signals.is_low_position_limit_up(
        _quiet_bar(2), _armed_params(armed_window_days=0)
    ).passed

    # A caller that never tracks the state (the live snapshot path) is unaffected.
    assert not signals.is_low_position_limit_up(_quiet_bar(None), _armed_params()).passed
