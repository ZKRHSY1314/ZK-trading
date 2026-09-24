import sqlite3
CACHE = r"D:/codex-A股交易/trading_local.sqlite3"
HIST  = r"D:/codex-A股交易/market_history.sqlite3"
con = sqlite3.connect(f"file:{HIST}?mode=ro", uri=True)
con.execute("ATTACH DATABASE ? AS cache", (f"file:{CACHE}?mode=ro",))
con.row_factory = sqlite3.Row
def q(l, sql):
    print("\n### "+l, flush=True); print("SQL:", " ".join(sql.split()), flush=True)
    for r in con.execute(sql).fetchall()[:30]: print("   ", dict(r), flush=True)

q("L amount direction: which store drops turnover?", """
SELECT SUM(CASE WHEN b.amount IS NULL AND c.amount IS NOT NULL THEN 1 ELSE 0 END) AS hist_null_cache_has,
       SUM(CASE WHEN b.amount IS NOT NULL AND c.amount IS NULL THEN 1 ELSE 0 END) AS cache_null_hist_has,
       SUM(CASE WHEN b.amount IS NULL AND c.amount IS NULL THEN 1 ELSE 0 END)     AS both_null,
       SUM(CASE WHEN b.amount IS NOT NULL AND c.amount IS NOT NULL THEN 1 ELSE 0 END) AS both_present
FROM main.daily_bars b JOIN cache.daily_bar_cache c ON c.symbol=b.symbol AND c.trade_date=b.trade_date""")

q("M magnitude of close disagreement (is it float noise or real re-basing?)", """
SELECT COUNT(*) AS differing_rows,
       SUM(CASE WHEN ABS(b.close-c.close) <= 1e-6                       THEN 1 ELSE 0 END) AS diff_le_1e6_noise,
       SUM(CASE WHEN ABS(b.close-c.close)/NULLIF(c.close,0) > 0.001     THEN 1 ELSE 0 END) AS rel_gt_0_1pct,
       SUM(CASE WHEN ABS(b.close-c.close)/NULLIF(c.close,0) > 0.05      THEN 1 ELSE 0 END) AS rel_gt_5pct,
       MAX(ABS(b.close-c.close)/NULLIF(c.close,0))                      AS max_rel_diff
FROM main.daily_bars b JOIN cache.daily_bar_cache c ON c.symbol=b.symbol AND c.trade_date=b.trade_date
WHERE ROUND(b.close,6) IS NOT ROUND(c.close,6)""")

q("N is the missing-amount concentrated by provider label?", """
SELECT b.provider, COUNT(*) n, SUM(CASE WHEN b.amount IS NULL THEN 1 ELSE 0 END) hist_amount_null
FROM main.daily_bars b GROUP BY 1 ORDER BY n DESC""")

q("O eligible-but-absent: cache rows passing every seeder filter with NO hist twin", """
SELECT COUNT(*) AS eligible_cache_rows_missing_from_hist,
       COUNT(DISTINCT c.symbol) AS symbols_affected,
       MIN(c.trade_date) d0, MAX(c.trade_date) d1
FROM cache.daily_bar_cache c
WHERE c.trade_date!='ERROR' AND c.quality_status='ready' AND c.adjustment_mode='qfq'
  AND (lower(COALESCE(c.source,'')) NOT LIKE '%sina%'
       OR lower(COALESCE(c.source,''))='tencent.fqkline.raw+sina.qfq_factor.unit_verified')
  AND NOT EXISTS (SELECT 1 FROM main.daily_bars b WHERE b.symbol=c.symbol AND b.trade_date=c.trade_date)""")
con.close()
