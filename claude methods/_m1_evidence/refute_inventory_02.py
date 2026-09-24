import sqlite3
OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
def show(t, rows):
    print("--", t)
    for r in rows: print("   ", r)

c = ro(OP)
print("### A. trade_date VALUE HYGIENE in daily_bar_cache (no filters at all)")
show("typeof/length histogram", c.execute("""
SELECT typeof(trade_date) AS ty, length(trade_date) AS len, COUNT(*) n,
       MIN(trade_date) mn, MAX(trade_date) mx
FROM daily_bar_cache GROUP BY ty, len ORDER BY n DESC""").fetchall())
show("NULL trade_date", c.execute("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date IS NULL").fetchall())
show("non YYYY-MM-DD pattern rows", c.execute("""
SELECT trade_date, COUNT(*) FROM daily_bar_cache
WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
GROUP BY trade_date ORDER BY 2 DESC LIMIT 20""").fetchall())

print()
print("### B. INDEPENDENT MIN via date() cast (defeats string-sort tricks)")
show("min/max by julianday", c.execute("""
SELECT MIN(julianday(trade_date)), MAX(julianday(trade_date)),
       date(MIN(julianday(trade_date))), date(MAX(julianday(trade_date)))
FROM daily_bar_cache
WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'""").fetchall())

print()
print("### C. rows/symbols in the pre-window and warm-up regions (cache)")
show("cache buckets", c.execute("""
SELECT CASE
  WHEN julianday(trade_date) <  julianday('2023-09-04') THEN '1_before_window(warmup region)'
  WHEN julianday(trade_date) <= julianday('2026-09-04') THEN '2_inside_window'
  ELSE '3_after_window' END AS bucket,
  COUNT(*) rows, COUNT(DISTINCT symbol) syms, MIN(trade_date), MAX(trade_date)
FROM daily_bar_cache
WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
GROUP BY bucket ORDER BY bucket""").fetchall())
c.close()

m = ro(MH)
print()
print("### D. same hygiene + buckets for market_history.daily_bars")
show("typeof/length", m.execute("""
SELECT typeof(trade_date), length(trade_date), COUNT(*), MIN(trade_date), MAX(trade_date)
FROM daily_bars GROUP BY 1,2 ORDER BY 3 DESC""").fetchall())
show("mh buckets", m.execute("""
SELECT CASE
  WHEN julianday(trade_date) <  julianday('2023-09-04') THEN '1_before_window'
  WHEN julianday(trade_date) <= julianday('2026-09-04') THEN '2_inside_window'
  ELSE '3_after_window' END AS bucket,
  COUNT(*) rows, COUNT(DISTINCT symbol) syms, MIN(trade_date), MAX(trade_date)
FROM daily_bars GROUP BY bucket ORDER BY bucket""").fetchall())
show("adjustment_mode mix (does COUNT(*) per symbol over-count?)", m.execute("""
SELECT adjustment_mode, COUNT(*) , COUNT(DISTINCT symbol) FROM daily_bars GROUP BY 1""").fetchall())
m.close()
