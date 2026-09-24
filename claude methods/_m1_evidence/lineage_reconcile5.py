import sqlite3, io, time
CACHE = r"D:/codex-A股交易/trading_local.sqlite3"
HIST  = r"D:/codex-A股交易/market_history.sqlite3"
OUT   = r"D:/codex-A股交易/claude methods/_m1_evidence/lineage_reconcile5_output.txt"
buf=io.StringIO()
def P(*a):
    s=" ".join(str(x) for x in a); buf.write(s+"\n"); print(s.encode("ascii","replace").decode("ascii"))
conn=sqlite3.connect(f"file:{HIST}?mode=ro",uri=True); conn.execute("PRAGMA query_only=ON"); conn.row_factory=sqlite3.Row
conn.execute(f"ATTACH DATABASE 'file:{CACHE}?mode=ro' AS cache")
def q(t,sql,p=(),lim=40):
    st=time.time(); rows=conn.execute(sql,p).fetchall(); P("\n### "+t); P("SQL: "+" ".join(sql.split()))
    for r in rows[:lim]: P("   ",dict(r))
    if len(rows)>lim: P("    ... (%d rows)"%len(rows))
    P("    [%.1fs]"%(time.time()-st)); return rows

q("M49 SZ001388: is the disagreement a constant ratio (qfq re-basing) or noise?", """
SELECT c.trade_date, c.close AS cache_close, b.close AS hist_close,
       ROUND(b.close/c.close,6) AS ratio_hist_over_cache
FROM main.daily_bars b JOIN cache.daily_bar_cache c ON c.symbol=b.symbol AND c.trade_date=b.trade_date
WHERE b.symbol='SZ001388' AND b.adjustment_mode='qfq' ORDER BY c.trade_date DESC LIMIT 12""", lim=12)

q("M50 ratio spread per mismatching symbol (constant ratio => pure qfq rebasing)", """
WITH j AS (
  SELECT b.symbol, b.close/c.close AS ratio
  FROM main.daily_bars b JOIN cache.daily_bar_cache c ON c.symbol=b.symbol AND c.trade_date=b.trade_date
  WHERE b.adjustment_mode='qfq' AND c.close>0 AND b.close>0),
s AS (SELECT symbol, COUNT(*) n, MIN(ratio) mn, MAX(ratio) mx FROM j GROUP BY symbol)
SELECT COUNT(*) AS symbols,
  SUM(CASE WHEN mx-mn < 0.0005 THEN 1 ELSE 0 END) AS symbols_constant_ratio,
  SUM(CASE WHEN mx-mn >= 0.0005 THEN 1 ELSE 0 END) AS symbols_varying_ratio,
  SUM(CASE WHEN mn>0.9995 AND mx<1.0005 THEN 1 ELSE 0 END) AS symbols_ratio_is_one
FROM s""")

q("M51 mismatch magnitude distribution (relative)", """
SELECT CASE
  WHEN ABS(c.close-b.close)/c.close < 0.0001 THEN 'a:<0.01%'
  WHEN ABS(c.close-b.close)/c.close < 0.001 THEN 'b:0.01-0.1%'
  WHEN ABS(c.close-b.close)/c.close < 0.01 THEN 'c:0.1-1%'
  WHEN ABS(c.close-b.close)/c.close < 0.05 THEN 'd:1-5%'
  WHEN ABS(c.close-b.close)/c.close < 0.2 THEN 'e:5-20%'
  ELSE 'f:>=20%' END AS bucket, COUNT(*) AS rows
FROM main.daily_bars b JOIN cache.daily_bar_cache c ON c.symbol=b.symbol AND c.trade_date=b.trade_date
WHERE b.adjustment_mode='qfq' AND c.close>0 AND b.close>0 AND c.close!=b.close GROUP BY 1 ORDER BY 1""")

q("M52 per-store max bars/symbol vs distinct sessions in window", """
SELECT (SELECT COUNT(DISTINCT trade_date) FROM cache.daily_bar_cache WHERE trade_date!='ERROR') AS cache_sessions,
       (SELECT MAX(n) FROM (SELECT COUNT(*) n FROM cache.daily_bar_cache WHERE trade_date!='ERROR' GROUP BY symbol)) AS cache_max_bars_per_symbol,
       (SELECT COUNT(DISTINCT trade_date) FROM main.daily_bars) AS hist_sessions,
       (SELECT MAX(n) FROM (SELECT COUNT(*) n FROM main.daily_bars GROUP BY symbol)) AS hist_max_bars_per_symbol""")

q("M53 hist staleness: latest trade_date per store and symbols missing the last session", """
SELECT (SELECT MAX(trade_date) FROM main.daily_bars) AS hist_max,
       (SELECT MAX(trade_date) FROM cache.daily_bar_cache WHERE trade_date!='ERROR') AS cache_max,
       (SELECT COUNT(DISTINCT symbol) FROM cache.daily_bar_cache WHERE trade_date='2026-09-04') AS cache_symbols_on_0904,
       (SELECT COUNT(DISTINCT symbol) FROM main.daily_bars WHERE trade_date='2026-09-03') AS hist_symbols_on_0903""")
conn.close(); open(OUT,"w",encoding="utf-8").write(buf.getvalue()); print("\nWROTE",OUT)
