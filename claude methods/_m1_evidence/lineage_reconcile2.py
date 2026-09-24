import sqlite3, io, time
CACHE = r"D:/codex-A股交易/trading_local.sqlite3"
HIST  = r"D:/codex-A股交易/market_history.sqlite3"
OUT   = r"D:/codex-A股交易/claude methods/_m1_evidence/lineage_reconcile2_output.txt"
buf = io.StringIO()
def P(*a):
    s=" ".join(str(x) for x in a); buf.write(s+"\n")
    print(s.encode("ascii","replace").decode("ascii"))
conn = sqlite3.connect(f"file:{HIST}?mode=ro", uri=True)
conn.execute("PRAGMA query_only=ON"); conn.row_factory = sqlite3.Row
conn.execute(f"ATTACH DATABASE 'file:{CACHE}?mode=ro' AS cache")
def q(t, sql, params=(), lim=40):
    st=time.time(); rows=conn.execute(sql,params).fetchall()
    P("\n### "+t); P("SQL: "+" ".join(sql.split()))
    for r in rows[:lim]: P("   ", dict(r))
    if len(rows)>lim: P("    ... (%d rows total)"%len(rows))
    P("    [%.1fs]"%(time.time()-st)); return rows

# ---- symbol set reconciliation ----
q("M18 symbols in cache but NOT in market_history.daily_bars (count)", """
SELECT COUNT(*) AS n FROM (
  SELECT DISTINCT symbol FROM cache.daily_bar_cache WHERE trade_date!='ERROR'
  EXCEPT SELECT DISTINCT symbol FROM main.daily_bars)""")
q("M18b examples + their bar counts / date span / instrument row presence", """
SELECT c.symbol, COUNT(*) AS cache_bars, MIN(c.trade_date) AS first_bar, MAX(c.trade_date) AS last_bar,
       (SELECT i.asset_type FROM main.instruments i WHERE i.symbol=c.symbol) AS instrument_asset_type,
       (SELECT i.exchange FROM main.instruments i WHERE i.symbol=c.symbol) AS instrument_exchange
FROM cache.daily_bar_cache c
WHERE c.trade_date!='ERROR'
  AND c.symbol NOT IN (SELECT symbol FROM main.daily_bars)
GROUP BY c.symbol ORDER BY cache_bars DESC""")
q("M19 symbols in market_history.daily_bars but NOT in cache (count + examples)", """
SELECT b.symbol, COUNT(*) AS hist_bars, MIN(b.trade_date) AS first_bar, MAX(b.trade_date) AS last_bar
FROM main.daily_bars b WHERE b.symbol NOT IN (SELECT DISTINCT symbol FROM cache.daily_bar_cache)
GROUP BY b.symbol ORDER BY hist_bars DESC""")

# ---- (symbol,trade_date) pair reconciliation ----
q("M20 pair overlap: rows present in cache only / hist only / both", """
SELECT
 (SELECT COUNT(*) FROM cache.daily_bar_cache c WHERE c.trade_date!='ERROR'
    AND NOT EXISTS (SELECT 1 FROM main.daily_bars b WHERE b.symbol=c.symbol AND b.trade_date=c.trade_date)) AS cache_only_rows,
 (SELECT COUNT(*) FROM main.daily_bars b
    WHERE NOT EXISTS (SELECT 1 FROM cache.daily_bar_cache c WHERE c.symbol=b.symbol AND c.trade_date=b.trade_date)) AS hist_only_rows,
 (SELECT COUNT(*) FROM main.daily_bars b
    WHERE EXISTS (SELECT 1 FROM cache.daily_bar_cache c WHERE c.symbol=b.symbol AND c.trade_date=b.trade_date)) AS overlap_rows""")

# ---- close mismatch ----
q("M21 overlapping rows with DIFFERENT close (tolerance 0.0)", """
SELECT COUNT(*) AS mismatched_rows,
       SUM(CASE WHEN ABS(c.close-b.close) > 0.005 THEN 1 ELSE 0 END) AS mismatch_gt_half_cent,
       SUM(CASE WHEN c.close!=0 AND ABS(c.close-b.close)/ABS(c.close) > 0.01 THEN 1 ELSE 0 END) AS mismatch_rel_gt_1pct
FROM main.daily_bars b JOIN cache.daily_bar_cache c
  ON c.symbol=b.symbol AND c.trade_date=b.trade_date
WHERE b.adjustment_mode='qfq' AND c.close IS NOT NULL AND b.close IS NOT NULL
  AND c.close != b.close""")

q("M22 mismatch broken down by cache adjustment_mode and cache source", """
SELECT c.adjustment_mode AS cache_adj_mode, c.source AS cache_source, b.provider AS hist_provider,
       COUNT(*) AS mismatched_rows, MAX(ABS(c.close-b.close)) AS max_abs_diff
FROM main.daily_bars b JOIN cache.daily_bar_cache c
  ON c.symbol=b.symbol AND c.trade_date=b.trade_date
WHERE b.adjustment_mode='qfq' AND c.close IS NOT NULL AND b.close IS NOT NULL AND c.close != b.close
GROUP BY 1,2,3 ORDER BY mismatched_rows DESC""")

q("M23 worst 15 close mismatches by relative difference", """
SELECT c.symbol, c.trade_date, c.close AS cache_close, b.close AS hist_close,
       ROUND(ABS(c.close-b.close),6) AS abs_diff,
       ROUND(ABS(c.close-b.close)/NULLIF(ABS(c.close),0)*100,4) AS rel_pct,
       c.adjustment_mode AS cache_adj, c.source AS cache_source, b.provider AS hist_provider,
       c.updated_at AS cache_updated_at, b.updated_at AS hist_updated_at, b.available_at
FROM main.daily_bars b JOIN cache.daily_bar_cache c
  ON c.symbol=b.symbol AND c.trade_date=b.trade_date
WHERE b.adjustment_mode='qfq' AND c.close IS NOT NULL AND b.close IS NOT NULL AND c.close != b.close
ORDER BY ABS(c.close-b.close)/NULLIF(ABS(c.close),0) DESC LIMIT 15""", lim=15)

q("M24 mismatch counted per symbol (top 15)", """
SELECT c.symbol, COUNT(*) AS mismatched_rows, MIN(c.trade_date) AS first_bad, MAX(c.trade_date) AS last_bad
FROM main.daily_bars b JOIN cache.daily_bar_cache c
  ON c.symbol=b.symbol AND c.trade_date=b.trade_date
WHERE b.adjustment_mode='qfq' AND c.close IS NOT NULL AND b.close IS NOT NULL AND c.close != b.close
GROUP BY c.symbol ORDER BY mismatched_rows DESC LIMIT 15""", lim=15)

conn.close()
open(OUT,"w",encoding="utf-8").write(buf.getvalue()); print("\nWROTE",OUT)
