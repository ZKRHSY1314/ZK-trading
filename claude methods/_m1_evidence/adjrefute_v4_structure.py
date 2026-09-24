import sqlite3
OPS = r"D:/codex-A股交易/trading_local.sqlite3"
HIS = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{OPS}?mode=ro", uri=True)
c.execute("ATTACH DATABASE ? AS mh", (f"file:{HIS}?mode=ro",))
c.execute("PRAGMA temp_store=MEMORY"); c.execute("PRAGMA cache_size=-400000")
def q(label, sql, lim=40):
    print("="*100); print(label); print("SQL:", " ".join(sql.split()))
    rows=c.execute(sql).fetchall()
    for r in rows[:lim]: print("   ", r)
    if len(rows)>lim: print(f"    ...{len(rows)} rows")
    return rows

# 7. Is the ratio PIECEWISE constant (anchor artifact) or genuinely noisy (shape defect)?
q("7. Distinct ratio LEVELS per symbol (ratio rounded to 4dp), symbols with >20 shared bars", """
SELECT CASE WHEN nlev=1 THEN 'a 1 level (pure rescale)'
            WHEN nlev<=3 THEN 'b 2-3 levels'
            WHEN nlev<=10 THEN 'c 4-10 levels'
            WHEN nlev<=50 THEN 'd 11-50 levels'
            ELSE 'e >50 levels' END AS levels, COUNT(*) AS symbols, SUM(n) AS bars
FROM (SELECT d.symbol, COUNT(*) n, COUNT(DISTINCT ROUND(d.close/b.close,4)) nlev
      FROM daily_bar_cache d JOIN mh.daily_bars b
        ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
      WHERE d.quality_status='ready' AND d.adjustment_mode='qfq' AND b.close>0
      GROUP BY 1 HAVING n>20)
GROUP BY 1 ORDER BY 1
""")

# 8. Stored decimal precision -- rounding floor on any ratio-constancy test
q("8. Decimal precision of stored closes (sampled 200k rows each)", """
SELECT 'ops daily_bar_cache' src,
  SUM(CASE WHEN close=ROUND(close,2) THEN 1 ELSE 0 END) AS at_2dp,
  SUM(CASE WHEN close=ROUND(close,3) THEN 1 ELSE 0 END) AS at_3dp, COUNT(*) n
FROM (SELECT close FROM daily_bar_cache WHERE adjustment_mode='qfq' AND quality_status='ready' AND close>0 LIMIT 200000)
UNION ALL
SELECT 'hist mh.daily_bars',
  SUM(CASE WHEN close=ROUND(close,2) THEN 1 ELSE 0 END),
  SUM(CASE WHEN close=ROUND(close,3) THEN 1 ELSE 0 END), COUNT(*)
FROM (SELECT close FROM mh.daily_bars WHERE adjustment_mode='qfq' AND close>0 LIMIT 200000)
""")

# 9. Their year breakdown -- is it a YEAR effect or a PROVIDER-MIX effect?
q("9. Divergence by year AND provider-pair identity", """
SELECT substr(d.trade_date,1,4) yr,
  CASE WHEN d.source=b.provider THEN 'same provider' ELSE 'different provider' END AS pair,
  COUNT(*) n, ROUND(100.0*SUM(CASE WHEN ABS(d.close-b.close)>0.005 THEN 1 ELSE 0 END)/COUNT(*),2) pct_halfcent
FROM daily_bar_cache d JOIN mh.daily_bars b
  ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
WHERE d.quality_status='ready' AND d.adjustment_mode='qfq' AND b.close>0
GROUP BY 1,2 ORDER BY 1,2
""")

# 10. The "worst case" SZ301590 -- real corporate action or corruption?
q("10. SZ301590 ratio timeline around 2025-09-30", """
SELECT d.trade_date, d.close ops_close, b.close hist_close,
       ROUND(d.close/b.close,6) ratio, d.source, b.provider
FROM daily_bar_cache d JOIN mh.daily_bars b
  ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
WHERE d.symbol='SZ301590' AND d.quality_status='ready' AND d.adjustment_mode='qfq'
  AND d.trade_date BETWEEN '2025-09-20' AND '2025-10-25'
ORDER BY d.trade_date
""")
q("11. SZ301590 distinct ratio levels over full history", """
SELECT ROUND(d.close/b.close,4) ratio, COUNT(*) n, MIN(d.trade_date) first_date, MAX(d.trade_date) last_date
FROM daily_bar_cache d JOIN mh.daily_bars b
  ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
WHERE d.symbol='SZ301590' AND d.quality_status='ready' AND d.adjustment_mode='qfq' AND b.close>0
GROUP BY 1 ORDER BY 3
""")
c.close()
