import pytest
from app.models import MarketSnapshot
from app.strategies.dengzhan import DengZhanSignals

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
