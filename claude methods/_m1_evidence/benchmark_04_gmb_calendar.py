import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
OP = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
op=ro(OP)

print("### Q10 global_market_bars compact")
q="SELECT symbol, asset_class, COUNT(*) rows, COUNT(DISTINCT date(bar_time)) distinct_days, COUNT(DISTINCT source) distinct_sources, MIN(date(bar_time)) d0, MAX(date(bar_time)) d1 FROM global_market_bars GROUP BY symbol, asset_class ORDER BY symbol"
print("SQL:", q)
for r in op.execute(q): print("   ", r)
q2="SELECT COUNT(*) rows, COUNT(DISTINCT symbol) syms, COUNT(DISTINCT source) srcs, SUM(CASE WHEN source LIKE '%#revision-%' THEN 1 ELSE 0 END) revision_rows, SUM(CASE WHEN volume=0 OR volume IS NULL THEN 1 ELSE 0 END) zero_volume FROM global_market_bars"
print("SQL:", q2); print("   ", op.execute(q2).fetchone())
q3="SELECT quality_status, COUNT(*) FROM global_market_bars GROUP BY quality_status"
print("SQL:", q3)
for r in op.execute(q3): print("   ", r)
q4="""SELECT symbol, COUNT(*) FROM (SELECT symbol, bar_time, COUNT(*) c FROM global_market_bars GROUP BY symbol, bar_time HAVING c>1) GROUP BY symbol"""
print("SQL(bar_time with >1 source row):", q4)
for r in op.execute(q4): print("   ", r)
print("   columns present:", [d[1] for d in op.execute("PRAGMA table_info(global_market_bars)")])

print("\n### Q11 session calendar derived from A-share stock bars in daily_bar_cache, window 2023-09-04..2026-09-04")
q="""SELECT COUNT(*) FROM (
  SELECT trade_date FROM daily_bar_cache
  WHERE length(symbol)=8 AND substr(symbol,1,2) IN ('SH','SZ','BJ') AND symbol NOT LIKE 'SH00%'
    AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'
  GROUP BY trade_date HAVING COUNT(DISTINCT symbol) >= 100)"""
print("SQL:", q); print("   session_days_in_window =", op.execute(q).fetchone()[0])
q="""SELECT MIN(trade_date), MAX(trade_date) FROM daily_bar_cache WHERE length(symbol)=8 AND substr(symbol,1,2) IN ('SH','SZ','BJ') AND symbol NOT LIKE 'SH00%'"""
print("SQL:", q); print("   stock bar span =", op.execute(q).fetchone())

print("\n### Q12 benchmark coverage of SH000300/SH000001 vs session calendar (their own overlap span)")
for b in ('SH000300','SH000001'):
    q=f"""WITH cal AS (
      SELECT trade_date FROM daily_bar_cache
      WHERE length(symbol)=8 AND substr(symbol,1,2) IN ('SH','SZ','BJ') AND symbol NOT LIKE 'SH00%'
      GROUP BY trade_date HAVING COUNT(DISTINCT symbol)>=100),
    b AS (SELECT trade_date FROM daily_bar_cache WHERE symbol='{b}')
    SELECT
      (SELECT COUNT(*) FROM cal WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04') AS cal_window,
      (SELECT COUNT(*) FROM b   WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04') AS bench_window,
      (SELECT COUNT(*) FROM cal WHERE trade_date BETWEEN (SELECT MIN(trade_date) FROM b) AND (SELECT MAX(trade_date) FROM b)) AS cal_in_bench_span,
      (SELECT COUNT(*) FROM cal WHERE trade_date BETWEEN (SELECT MIN(trade_date) FROM b) AND (SELECT MAX(trade_date) FROM b)
         AND trade_date NOT IN (SELECT trade_date FROM b)) AS missing_in_bench_span,
      (SELECT MIN(trade_date) FROM b), (SELECT MAX(trade_date) FROM b)"""
    print(f"  --- {b}"); print("SQL:", q.replace('\n',' ')[:400]+"...")
    print("   ", op.execute(q).fetchone())
    # list missing days inside span
    q2=f"""WITH cal AS (SELECT trade_date FROM daily_bar_cache WHERE length(symbol)=8 AND substr(symbol,1,2) IN ('SH','SZ','BJ') AND symbol NOT LIKE 'SH00%' GROUP BY trade_date HAVING COUNT(DISTINCT symbol)>=100)
    SELECT trade_date FROM cal WHERE trade_date BETWEEN (SELECT MIN(trade_date) FROM daily_bar_cache WHERE symbol='{b}') AND (SELECT MAX(trade_date) FROM daily_bar_cache WHERE symbol='{b}') AND trade_date NOT IN (SELECT trade_date FROM daily_bar_cache WHERE symbol='{b}') ORDER BY trade_date"""
    miss=[r[0] for r in op.execute(q2)]
    print("    missing session days inside benchmark span:", len(miss), miss[:30])
op.close()
