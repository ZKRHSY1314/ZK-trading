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
    return rows

q("16. FINAL corrected headline: absolute vs relative threshold, same vs different provider", """
SELECT COUNT(*) AS common_rows,
  COUNT(DISTINCT d.symbol) AS symbols_in_join,
  SUM(CASE WHEN ABS(d.close-b.close)>0.005 THEN 1 ELSE 0 END) AS differ_halfcent_abs,
  ROUND(100.0*SUM(CASE WHEN ABS(d.close-b.close)>0.005 THEN 1 ELSE 0 END)/COUNT(*),2) AS pct_halfcent,
  SUM(CASE WHEN ABS(d.close-b.close)/b.close>0.01 THEN 1 ELSE 0 END) AS differ_gt1pct,
  ROUND(100.0*SUM(CASE WHEN ABS(d.close-b.close)/b.close>0.01 THEN 1 ELSE 0 END)/COUNT(*),2) AS pct_gt1pct,
  COUNT(DISTINCT CASE WHEN ABS(d.close-b.close)/b.close>0.01 THEN d.symbol END) AS syms_gt1pct,
  SUM(CASE WHEN d.source=b.provider THEN 1 ELSE 0 END) AS same_provider_rows,
  SUM(CASE WHEN d.source<>b.provider THEN 1 ELSE 0 END) AS diff_provider_rows,
  ROUND(100.0*SUM(CASE WHEN d.source=b.provider AND ABS(d.close-b.close)>0.005 THEN 1 ELSE 0 END)
        /SUM(CASE WHEN d.source=b.provider THEN 1 ELSE 0 END),2) AS pct_differ_when_SAME_provider,
  ROUND(100.0*SUM(CASE WHEN d.source<>b.provider AND ABS(d.close-b.close)>0.005 THEN 1 ELSE 0 END)
        /SUM(CASE WHEN d.source<>b.provider THEN 1 ELSE 0 END),2) AS pct_differ_when_DIFF_provider
FROM daily_bar_cache d
JOIN mh.daily_bars b ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
WHERE d.quality_status='ready' AND d.adjustment_mode='qfq' AND b.close>0
""")

q("17. Return-level impact restated as a single number", """
WITH j AS (SELECT d.symbol s, d.trade_date td, d.close dc, b.close bc
  FROM daily_bar_cache d JOIN mh.daily_bars b
    ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
  WHERE d.quality_status='ready' AND d.adjustment_mode='qfq' AND b.close>0 AND d.close>0),
r AS (SELECT s, dc/LAG(dc) OVER (PARTITION BY s ORDER BY td) dr,
              bc/LAG(bc) OVER (PARTITION BY s ORDER BY td) br FROM j)
SELECT COUNT(*) AS return_pairs,
  SUM(CASE WHEN ABS(dr-br)<0.0001 THEN 1 ELSE 0 END) AS returns_agree_1bp,
  ROUND(100.0*SUM(CASE WHEN ABS(dr-br)<0.0001 THEN 1 ELSE 0 END)/COUNT(*),2) AS pct_agree_1bp,
  SUM(CASE WHEN ABS(dr-br)>=0.01 THEN 1 ELSE 0 END) AS returns_differ_1pct,
  ROUND(100.0*SUM(CASE WHEN ABS(dr-br)>=0.01 THEN 1 ELSE 0 END)/COUNT(*),4) AS pct_differ_1pct
FROM r WHERE dr IS NOT NULL AND br IS NOT NULL
""")
c.close()
