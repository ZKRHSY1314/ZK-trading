import sqlite3, io, time
CACHE = r"D:/codex-A股交易/trading_local.sqlite3"
HIST  = r"D:/codex-A股交易/market_history.sqlite3"
OUT   = r"D:/codex-A股交易/claude methods/_m1_evidence/lineage_reconcile4_output.txt"
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

q("M38 amount (成交额) regression: hist NULL where cache has a value", """
SELECT COUNT(*) AS overlap_rows,
  SUM(CASE WHEN b.amount IS NULL AND c.amount IS NOT NULL THEN 1 ELSE 0 END) AS hist_null_cache_has,
  SUM(CASE WHEN b.amount IS NOT NULL AND c.amount IS NULL THEN 1 ELSE 0 END) AS cache_null_hist_has,
  SUM(CASE WHEN b.amount IS NULL AND c.amount IS NULL THEN 1 ELSE 0 END) AS both_null
FROM main.daily_bars b JOIN cache.daily_bar_cache c ON c.symbol=b.symbol AND c.trade_date=b.trade_date""")

q("M39 hist amount NULL by provider", """
SELECT provider, COUNT(*) AS rows, SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) AS null_amount_rows,
       ROUND(100.0*SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END)/COUNT(*),2) AS pct_null
FROM main.daily_bars GROUP BY 1 ORDER BY rows DESC""")

q("M40 cache amount NULL by source", """
SELECT source, COUNT(*) AS rows, SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) AS null_amount_rows,
       ROUND(100.0*SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END)/COUNT(*),2) AS pct_null
FROM cache.daily_bar_cache GROUP BY 1 ORDER BY rows DESC""")

q("M41 PIT usability: hist rows visible under a strict available_at<=as_of filter at 3 sample as_of dates", """
SELECT '2025-09-04' AS as_of,
       (SELECT COUNT(*) FROM main.daily_bars WHERE trade_date<='2025-09-04' AND available_at<='2025-09-04') AS rows_visible_pit,
       (SELECT COUNT(*) FROM main.daily_bars WHERE trade_date<='2025-09-04') AS rows_by_trade_date
UNION ALL SELECT '2026-06-30',
       (SELECT COUNT(*) FROM main.daily_bars WHERE trade_date<='2026-06-30' AND available_at<='2026-06-30'),
       (SELECT COUNT(*) FROM main.daily_bars WHERE trade_date<='2026-06-30')
UNION ALL SELECT '2026-08-01',
       (SELECT COUNT(*) FROM main.daily_bars WHERE trade_date<='2026-08-01' AND available_at<='2026-08-01'),
       (SELECT COUNT(*) FROM main.daily_bars WHERE trade_date<='2026-08-01')""")

q("M42 what the backtest engine actually ran on (historical_backtest_runs)", """
SELECT data_source, status, COUNT(*) AS runs, MIN(start_date) AS earliest_start, MAX(end_date) AS latest_end,
       MIN(created_at) AS first_created, MAX(created_at) AS last_created
FROM cache.historical_backtest_runs GROUP BY 1,2 ORDER BY runs DESC""")

q("M43 backtest runs: per-run window + whether any trades were produced", """
SELECT r.id, r.start_date, r.end_date, r.status, r.benchmark_symbol,
       (SELECT COUNT(*) FROM cache.historical_backtest_trades t WHERE t.run_id=r.id) AS trades,
       (SELECT COUNT(*) FROM cache.historical_backtest_daily_equity d WHERE d.run_id=r.id) AS equity_days
FROM cache.historical_backtest_runs r ORDER BY r.id DESC LIMIT 15""", lim=15)

q("M44 duplicate instrument representation: unprefixed cache symbols vs prefixed twin", """
SELECT c.symbol AS unprefixed, COUNT(*) AS rows, MIN(c.trade_date) AS first_bar, MAX(c.trade_date) AS last_bar,
  (SELECT COUNT(*) FROM cache.daily_bar_cache x WHERE x.symbol='SZ'||c.symbol OR x.symbol='SH'||c.symbol OR x.symbol='BJ'||c.symbol) AS prefixed_twin_rows
FROM cache.daily_bar_cache c
WHERE c.symbol NOT LIKE 'SH%' AND c.symbol NOT LIKE 'SZ%' AND c.symbol NOT LIKE 'BJ%'
GROUP BY c.symbol ORDER BY rows DESC""")

q("M45 same-day close disagreement between an unprefixed symbol and its prefixed twin", """
SELECT a.symbol AS unprefixed, b.symbol AS prefixed, a.trade_date, a.close AS close_unprefixed,
       b.close AS close_prefixed, a.source AS src_unprefixed, b.source AS src_prefixed
FROM cache.daily_bar_cache a JOIN cache.daily_bar_cache b
  ON b.symbol IN ('SH'||a.symbol,'SZ'||a.symbol,'BJ'||a.symbol) AND b.trade_date=a.trade_date
WHERE a.symbol NOT LIKE 'SH%' AND a.symbol NOT LIKE 'SZ%' AND a.symbol NOT LIKE 'BJ%'
  AND a.close != b.close
ORDER BY a.trade_date DESC LIMIT 10""", lim=10)

q("M46 usable backtest depth: symbols with >=250 ready qfq bars in window (cache)", """
WITH per AS (
  SELECT symbol, COUNT(*) AS n FROM cache.daily_bar_cache
  WHERE quality_status='ready' AND adjustment_mode='qfq' AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'
    AND open IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL AND close IS NOT NULL
  GROUP BY symbol)
SELECT COUNT(*) AS symbols, SUM(CASE WHEN n>=500 THEN 1 ELSE 0 END) AS ge_500,
       SUM(CASE WHEN n>=250 THEN 1 ELSE 0 END) AS ge_250, SUM(CASE WHEN n>=60 THEN 1 ELSE 0 END) AS ge_60,
       SUM(CASE WHEN n<60 THEN 1 ELSE 0 END) AS lt_60 FROM per""")

q("M47 earliest date at which >=4000 symbols have a bar (effective full-market start)", """
SELECT trade_date, COUNT(DISTINCT symbol) AS symbols FROM cache.daily_bar_cache
WHERE trade_date!='ERROR' GROUP BY trade_date HAVING COUNT(DISTINCT symbol)>=4000
ORDER BY trade_date ASC LIMIT 3""", lim=3)

q("M48 hist same: earliest date with >=4000 symbols", """
SELECT trade_date, COUNT(DISTINCT symbol) AS symbols FROM main.daily_bars
GROUP BY trade_date HAVING COUNT(DISTINCT symbol)>=4000 ORDER BY trade_date ASC LIMIT 3""", lim=3)

conn.close()
open(OUT,"w",encoding="utf-8").write(buf.getvalue()); print("\nWROTE",OUT)
