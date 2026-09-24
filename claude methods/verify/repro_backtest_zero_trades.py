import os
os.environ.setdefault("ENABLE_LIVE_TRADING","false")
from app.rules.engine import RuleEngine
from app.rules.loader import load_rule_config
from app.models import MarketSnapshot

cfg = load_rule_config()
eng = RuleEngine(cfg)
# ideal dengzhan bar: low position, limit up, high volume ratio, no big rise
snap = MarketSnapshot(
    symbol="SH600000", trade_date="2026-01-05", price=10.0, pct_change=10.0,
    high=10.0, low=9.2, open=9.3, close=10.0, volume=1e7, amount=1e8,
    historical_high=30.0,
    metadata={"data_quality":"daily_bar","board_type":"main","limit_up_threshold":9.8,
              "high_250":30.0,"volume_ratio":2.0,"five_day_pct":3.0,"previous_close":9.09},
)
d = eng.evaluate(snap)
print("PERFECT BAR (as backtest builds it): score=",d.score,"raw=",d.raw_score,"max=",d.max_score,"tier=",d.tier)
for h in d.hits: print("   ",h.rule_id,h.passed,h.score_delta,"|",h.reason)
snap.pb=3.0; snap.market_cap_billion=80.0
d2 = eng.evaluate(snap)
print("SAME BAR + pb/market_cap: score=",d2.score,"tier=",d2.tier)
