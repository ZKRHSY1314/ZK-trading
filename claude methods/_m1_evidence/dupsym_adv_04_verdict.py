import sqlite3
op = sqlite3.connect("file:D:/codex-A股交易/trading_local.sqlite3?mode=ro", uri=True)
op.row_factory = sqlite3.Row
SQL = """
WITH bare AS (SELECT DISTINCT symbol FROM daily_bar_cache WHERE LENGTH(symbol)<>8),
     pref AS (SELECT DISTINCT symbol FROM daily_bar_cache WHERE LENGTH(symbol)=8)
SELECT
 (SELECT COUNT(*) FROM bare)                                            AS bare_spellings,
 (SELECT COUNT(*) FROM daily_bar_cache WHERE LENGTH(symbol)<>8)         AS shadow_rows,
 (SELECT COUNT(*) FROM pref)                                            AS real_securities,
 (SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache)                   AS distinct_spellings,
 (SELECT COUNT(*) FROM pref p WHERE EXISTS
     (SELECT 1 FROM bare b WHERE b.symbol = substr(p.symbol,3)))        AS prefixed_with_a_bare_twin,
 (SELECT COUNT(*) FROM pref p WHERE EXISTS (SELECT 1 FROM bare b WHERE b.symbol=substr(p.symbol,3))
    AND EXISTS (SELECT 1 FROM daily_bar_cache x JOIN daily_bar_cache y
                ON y.symbol=substr(p.symbol,3) AND y.trade_date=x.trade_date
                WHERE x.symbol=p.symbol AND ABS(x.close-y.close) < 0.05))
                                                                        AS securities_actually_shadowed,
 (SELECT COUNT(*) FROM historical_backtest_runs
    WHERE created_at >= (SELECT MIN(created_at) FROM daily_bar_cache WHERE LENGTH(symbol)<>8))
                                                                        AS persisted_runs_contaminated,
 (SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache
    WHERE LENGTH(symbol)=8 AND substr(symbol,3,1) IN ('6','9') AND substr(symbol,1,2)<>'SH')
                                                                        AS bj_securities_misrouted_by_normalizer,
 (SELECT COUNT(*) FROM daily_bar_cache
    WHERE LENGTH(symbol)=8 AND substr(symbol,3,1) IN ('6','9') AND substr(symbol,1,2)<>'SH')
                                                                        AS bj_rows_misrouted
"""
r = dict(op.execute(SQL).fetchone())
print("### CORRECTED HEADLINE NUMBERS")
for k, v in r.items(): print(f"   {k:42s} = {v}")

print("\n### Identity test: which security is bare '000001'?")
for row in op.execute("""
SELECT p.symbol AS candidate, COUNT(*) AS shared_dates,
       ROUND(MAX(ABS(b.close-p.close)/p.close)*100,3) AS max_pct_gap,
       ROUND(AVG(b.close),3) AS bare_avg, ROUND(AVG(p.close),3) AS cand_avg
FROM daily_bar_cache b JOIN daily_bar_cache p ON p.trade_date=b.trade_date
WHERE b.symbol='000001' AND p.symbol IN ('SZ000001','SH000001') GROUP BY p.symbol"""):
    d = dict(row); print("   ", d)

print("\n### Does SH000001 have ANY shadow row of its own?")
for row in op.execute("""
SELECT 'SH000001' AS sym,
  (SELECT COUNT(*) FROM daily_bar_cache WHERE LENGTH(symbol)<>8 AND close BETWEEN 3000 AND 5000) AS bare_rows_at_index_scale,
  (SELECT COUNT(*) FROM daily_bar_cache WHERE LENGTH(symbol)<>8) AS bare_rows_total"""):
    print("   ", dict(row))
