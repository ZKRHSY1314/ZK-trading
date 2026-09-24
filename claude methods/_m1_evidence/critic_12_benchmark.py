import sqlite3, json
c=sqlite3.connect("file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True); c.execute("PRAGMA query_only=1")
print("SH000300 rows inside the 39 runs' actual windows:")
for a,b in (("2025-10-15","2026-06-12"),("2025-10-12","2026-06-09"),("2025-06-17","2026-06-12"),("2025-06-14","2026-06-09")):
    n=c.execute("SELECT COUNT(*),MIN(trade_date),MAX(trade_date) FROM daily_bar_cache WHERE symbol='SH000300' AND trade_date BETWEEN ? AND ?",(a,b)).fetchone()
    print(f"  {a}..{b}: {n}")
print("\nbenchmark_json status distribution:")
from collections import Counter
cnt=Counter()
for (bj,) in c.execute("SELECT benchmark_json FROM historical_backtest_runs"):
    try: cnt[json.loads(bj).get("status")]+=1
    except Exception: cnt["unparsable"]+=1
print("  ",cnt)
print("\nSH000300 quality/adjustment/amount:",
  c.execute("SELECT quality_status, adjustment_mode, COUNT(*), SUM(amount IS NULL), MIN(trade_date), MAX(trade_date) FROM daily_bar_cache WHERE symbol='SH000300' GROUP BY 1,2").fetchall())
