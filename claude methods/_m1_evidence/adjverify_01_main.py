import sqlite3, statistics as st
OP=r"D:/codex-A股交易/trading_local.sqlite3"
MH=r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
c=ro(OP); m=ro(MH)

print("=== [A] trading dates around 2024-08-13 in cache (distinct symbols) ===")
Q_A="""SELECT trade_date, COUNT(DISTINCT symbol) FROM daily_bar_cache
 WHERE trade_date BETWEEN '2024-08-06' AND '2024-08-20' GROUP BY 1 ORDER BY 1"""
for r in c.execute(Q_A): print(r)

print("\n=== [B] per-symbol source at 08-12 and 08-13, DISTINCT symbols, stocks only ===")
# stocks only := adjustment_mode='qfq' (excludes the 1076 index rows which are 'none')
Q_B="""
WITH d AS (SELECT symbol, trade_date, source, close, adjustment_mode
           FROM daily_bar_cache
           WHERE trade_date IN ('2024-08-12','2024-08-13') AND adjustment_mode='qfq'),
 p AS (SELECT symbol,
        MAX(CASE WHEN trade_date='2024-08-12' THEN source END) s12,
        MAX(CASE WHEN trade_date='2024-08-13' THEN source END) s13,
        MAX(CASE WHEN trade_date='2024-08-12' THEN close END)  c12,
        MAX(CASE WHEN trade_date='2024-08-13' THEN close END)  c13
       FROM d GROUP BY symbol)
SELECT s12, s13, COUNT(*) FROM p GROUP BY 1,2 ORDER BY 3 DESC"""
for r in c.execute(Q_B): print(r)
