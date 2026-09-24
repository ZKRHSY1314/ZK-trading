import sqlite3
OPS = r"D:/codex-A股交易/trading_local.sqlite3"
HIS = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{OPS}?mode=ro", uri=True)
c.execute("ATTACH DATABASE ? AS mh", (f"file:{HIS}?mode=ro",))
def q(label, sql, params=(), lim=80):
    print("="*100); print(label); print("SQL:", " ".join(sql.split()))
    rows = c.execute(sql, params).fetchall()
    for r in rows[:lim]: print("   ", r)
    if len(rows) > lim: print(f"    ... {len(rows)} rows")
    return rows

# 1. The exact join population + distinct symbols on BOTH sides (their 5,566 denominator check)
q("1. TRUE join population and its symbol denominator", """
SELECT COUNT(*) AS common_rows,
       COUNT(DISTINCT d.symbol) AS symbols_in_join,
       MIN(d.trade_date), MAX(d.trade_date)
FROM daily_bar_cache d
JOIN mh.daily_bars b ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
WHERE d.quality_status='ready' AND d.adjustment_mode='qfq'
""")

q("1b. candidate 5566 denominators", """
SELECT (SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache) AS all_dbc_symbols,
       (SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE adjustment_mode='qfq' AND quality_status='ready') AS dbc_qfq_ready,
       (SELECT COUNT(DISTINCT symbol) FROM mh.daily_bars) AS mh_symbols,
       (SELECT COUNT(*) FROM mh.instruments) AS instruments
""")

# 2. RELATIVE difference distribution -- their 0.005 absolute threshold is rounding-level
q("2. Relative-difference buckets over the SAME join (mine, independent)", """
SELECT CASE
  WHEN ABS(d.close-b.close)/b.close < 0.0000001 THEN 'a exact (<1e-7)'
  WHEN ABS(d.close-b.close)/b.close < 0.0001    THEN 'b <0.01%  (rounding)'
  WHEN ABS(d.close-b.close)/b.close < 0.001     THEN 'c <0.1%'
  WHEN ABS(d.close-b.close)/b.close < 0.01      THEN 'd <1%'
  WHEN ABS(d.close-b.close)/b.close < 0.05      THEN 'e <5%'
  WHEN ABS(d.close-b.close)/b.close < 0.20      THEN 'f <20%'
  ELSE 'g >=20%' END AS bucket,
  COUNT(*), ROUND(100.0*COUNT(*)/(SELECT COUNT(*) FROM daily_bar_cache d2 JOIN mh.daily_bars b2 ON b2.symbol=d2.symbol AND b2.trade_date=d2.trade_date AND b2.adjustment_mode='qfq' WHERE d2.quality_status='ready' AND d2.adjustment_mode='qfq' AND b2.close>0),4) AS pct,
  COUNT(DISTINCT d.symbol) AS syms
FROM daily_bar_cache d
JOIN mh.daily_bars b ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
WHERE d.quality_status='ready' AND d.adjustment_mode='qfq' AND b.close>0
GROUP BY 1 ORDER BY 1
""")

# 3. Does the divergence track the PROVIDER pair? (the mechanism)
q("3. Divergence decomposed by (ops source, hist provider) pair", """
SELECT d.source AS ops_source, b.provider AS hist_provider, COUNT(*) AS n,
  SUM(CASE WHEN ABS(d.close-b.close)>0.005 THEN 1 ELSE 0 END) AS diff_halfcent,
  ROUND(100.0*SUM(CASE WHEN ABS(d.close-b.close)>0.005 THEN 1 ELSE 0 END)/COUNT(*),2) AS pct_halfcent,
  ROUND(100.0*SUM(CASE WHEN ABS(d.close-b.close)/b.close>0.01 THEN 1 ELSE 0 END)/COUNT(*),2) AS pct_gt1pct
FROM daily_bar_cache d
JOIN mh.daily_bars b ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
WHERE d.quality_status='ready' AND d.adjustment_mode='qfq' AND b.close>0
GROUP BY 1,2 HAVING n>50 ORDER BY n DESC
""")
c.close()
