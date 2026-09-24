import sqlite3
TL="D:/codex-A股交易/trading_local.sqlite3"; MH="D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
tl,mh=ro(TL),ro(MH)
W0,W1='2023-09-04','2026-09-04'

print("### G. Run THEIR EXACT SQL verbatim, to see what their 4 numbers really are")
their = """
WITH cal AS (SELECT trade_date FROM daily_bar_cache WHERE length(symbol)=8 AND substr(symbol,1,2) IN ('SH','SZ','BJ') AND symbol NOT LIKE 'SH00%' GROUP BY trade_date HAVING COUNT(DISTINCT symbol)>=100), b AS (SELECT trade_date FROM daily_bar_cache WHERE symbol='SH000300')
SELECT (SELECT COUNT(*) FROM cal WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'), (SELECT COUNT(*) FROM b WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'), (SELECT COUNT(*) FROM cal WHERE trade_date BETWEEN (SELECT MIN(trade_date) FROM b) AND (SELECT MAX(trade_date) FROM b) AND trade_date NOT IN (SELECT trade_date FROM b)), (SELECT COUNT(*) FROM cal WHERE trade_date BETWEEN '2023-09-04' AND '2024-06-18');
"""
print("  their 4 outputs (cal_in_window, bench_in_window, interior_gaps, cal_in_dark_period):", tl.execute(their).fetchone())

print()
print("### H. Does the STOCK data cover the dark period at all?  (is this benchmark-specific?)")
q="""SELECT
  (SELECT COUNT(*) FROM daily_bar_cache) tot,
  (SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date < '2024-06-07') before_breadth,
  (SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2024-06-18') in_dark,
  (SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2024-06-18') sym_in_dark,
  (SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2024-06-18') days_in_dark,
  (SELECT MIN(trade_date) FROM daily_bar_cache) minall,
  (SELECT MAX(trade_date) FROM daily_bar_cache) maxall"""
print("  trading_local.daily_bar_cache:", dict(zip(
  ['total_rows','rows_before_2024-06-07','rows_in_dark_period','distinct_symbols_in_dark','distinct_days_in_dark','min_date','max_date'],
  tl.execute(q).fetchone())))
q2="""SELECT
  (SELECT COUNT(*) FROM daily_bars) tot,
  (SELECT COUNT(*) FROM daily_bars WHERE trade_date BETWEEN '2023-09-04' AND '2024-06-18') in_dark,
  (SELECT COUNT(DISTINCT symbol) FROM daily_bars WHERE trade_date BETWEEN '2023-09-04' AND '2024-06-18') sym_dark,
  (SELECT COUNT(DISTINCT trade_date) FROM daily_bars WHERE trade_date BETWEEN '2023-09-04' AND '2024-06-18') days_dark,
  (SELECT MIN(trade_date) FROM daily_bars), (SELECT MAX(trade_date) FROM daily_bars)"""
print("  market_history.daily_bars:    ", dict(zip(
  ['total_rows','rows_in_dark','distinct_symbols_in_dark','distinct_days_in_dark','min_date','max_date'],
  mh.execute(q2).fetchone())))

print()
print("### I. Per-day breadth around the two start edges (stocks only, explicit code prefixes)")
q3="""SELECT trade_date, COUNT(DISTINCT symbol) n FROM daily_bar_cache
WHERE length(symbol)=8 AND ((substr(symbol,1,2)='SH' AND substr(symbol,3,1)='6')
  OR (substr(symbol,1,2)='SZ' AND substr(symbol,3,1) IN ('0','3')) OR substr(symbol,1,2)='BJ')
  AND trade_date BETWEEN '2024-05-20' AND '2024-06-28' GROUP BY trade_date ORDER BY trade_date"""
for r in tl.execute(q3).fetchall(): print(f"    {r[0]}  stocks={r[1]:5}  bench={'Y' if tl.execute('SELECT 1 FROM daily_bar_cache WHERE symbol=? AND trade_date=?',('SH000300',r[0])).fetchone() else 'N'}")

print()
print("### J. Tail edge: last days")
q4="""SELECT trade_date, COUNT(DISTINCT symbol) n FROM daily_bar_cache
WHERE length(symbol)=8 AND ((substr(symbol,1,2)='SH' AND substr(symbol,3,1)='6')
  OR (substr(symbol,1,2)='SZ' AND substr(symbol,3,1) IN ('0','3')) OR substr(symbol,1,2)='BJ')
  AND trade_date >= '2026-08-25' GROUP BY trade_date ORDER BY trade_date"""
for r in tl.execute(q4).fetchall(): print(f"    {r[0]}  stocks={r[1]:5}  bench={'Y' if tl.execute('SELECT 1 FROM daily_bar_cache WHERE symbol=? AND trade_date=?',('SH000300',r[0])).fetchone() else 'N'}")
tl.close(); mh.close()
