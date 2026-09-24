import sqlite3
c=sqlite3.connect(r"file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True)
print("demo_seed_fixture / error rows in daily_bar_cache:")
for r in c.execute("""SELECT symbol,trade_date,open,high,low,close,volume,source,quality_status
   FROM daily_bar_cache WHERE source IN ('demo_seed_fixture','error') ORDER BY symbol,trade_date"""): print("  ",r)
print("\nSZ002081 neighbourhood 2026-05-20..2026-05-28:")
for r in c.execute("""SELECT trade_date,open,high,low,close,source FROM daily_bar_cache
   WHERE symbol='SZ002081' AND trade_date BETWEEN '2026-05-20' AND '2026-05-28' ORDER BY trade_date"""): print("  ",r)
