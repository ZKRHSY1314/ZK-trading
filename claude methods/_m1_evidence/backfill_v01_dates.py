import sqlite3
OP = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"

def q(c, sql, args=()):
    return c.execute(sql, args).fetchall()

op = sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
mh = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)

print("### A. UNFILTERED date extremes (NO length filter) — does their length=10 filter hide anything?")
print("A1 daily_bar_cache raw MIN/MAX/COUNT:",
      q(op, "SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM daily_bar_cache"))
print("A2 daily_bar_cache length histogram:",
      q(op, "SELECT length(trade_date) L, COUNT(*) n, MIN(trade_date), MAX(trade_date) FROM daily_bar_cache GROUP BY L ORDER BY L"))
print("A3 daily_bars raw MIN/MAX/COUNT:",
      q(mh, "SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM daily_bars"))
print("A4 daily_bars length histogram:",
      q(mh, "SELECT length(trade_date) L, COUNT(*) n, MIN(trade_date), MAX(trade_date) FROM daily_bars GROUP BY L ORDER BY L"))
print("A5 daily_bar_cache NULL trade_date:",
      q(op, "SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date IS NULL"))
print("A6 daily_bar_cache typeof(trade_date):",
      q(op, "SELECT typeof(trade_date) t, COUNT(*) FROM daily_bar_cache GROUP BY t"))
print("A7 daily_bars typeof(trade_date):",
      q(mh, "SELECT typeof(trade_date) t, COUNT(*) FROM daily_bars GROUP BY t"))

print()
print("### B. 10 earliest distinct dates in each store (sorted as TEXT)")
print("B1 cache:", q(op, "SELECT DISTINCT trade_date FROM daily_bar_cache ORDER BY trade_date ASC LIMIT 10"))
print("B2 hist :", q(mh, "SELECT DISTINCT trade_date FROM daily_bars ORDER BY trade_date ASC LIMIT 10"))
print("B3 cache last:", q(op, "SELECT DISTINCT trade_date FROM daily_bar_cache ORDER BY trade_date DESC LIMIT 5"))
print("B4 hist  last:", q(mh, "SELECT DISTINCT trade_date FROM daily_bars ORDER BY trade_date DESC LIMIT 5"))

print()
print("### C. ANY row anywhere in window before 2024-04-09? (date() normalization, catches odd formats)")
print("C1 cache rows with date(trade_date) < '2024-04-09':",
      q(op, "SELECT COUNT(*), MIN(date(trade_date)) FROM daily_bar_cache WHERE date(trade_date) < '2024-04-09'"))
print("C2 hist rows with date(trade_date) < '2024-04-09':",
      q(mh, "SELECT COUNT(*), MIN(date(trade_date)) FROM daily_bars WHERE date(trade_date) < '2024-04-09'"))
print("C3 cache rows in 2023-09-04..2024-04-08 (text cmp):",
      q(op, "SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date >= '2023-09-04' AND trade_date <= '2024-04-08'"))
print("C4 hist rows in 2023-09-04..2024-04-08 (text cmp):",
      q(mh, "SELECT COUNT(*) FROM daily_bars WHERE trade_date >= '2023-09-04' AND trade_date <= '2024-04-08'"))

print()
print("### D. distinct sessions inside window, both stores, no length filter")
print("D1 cache distinct dates 2023-09-04..2026-09-04:",
      q(op, "SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'"))
print("D2 hist  distinct dates 2023-09-04..2026-09-04:",
      q(mh, "SELECT COUNT(DISTINCT trade_date) FROM daily_bars WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'"))
print("D3 UNION of both stores distinct dates in window: computed in python below")

cd = set(x[0] for x in q(op, "SELECT DISTINCT trade_date FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'"))
hd = set(x[0] for x in q(mh, "SELECT DISTINCT trade_date FROM daily_bars WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'"))
print("   |cache|=%d |hist|=%d |union|=%d |hist-only|=%d |cache-only|=%d" % (len(cd), len(hd), len(cd|hd), len(hd-cd), len(cd-hd)))
print("   earliest union date:", min(cd|hd), " latest:", max(cd|hd))

print()
print("### E. adjustment_mode breakdown in market_history (is a non-'none' mode holding older data?)")
print("E1:", q(mh, "SELECT adjustment_mode, COUNT(*), MIN(trade_date), MAX(trade_date), COUNT(DISTINCT symbol) FROM daily_bars GROUP BY adjustment_mode"))
print("E2 cache adjustment_mode:", q(op, "SELECT adjustment_mode, COUNT(*), MIN(trade_date), MAX(trade_date) FROM daily_bar_cache GROUP BY adjustment_mode"))
print("E3 cache source:", q(op, "SELECT source, COUNT(*), MIN(trade_date), MAX(trade_date), COUNT(DISTINCT symbol) FROM daily_bar_cache GROUP BY source ORDER BY 2 DESC"))
print("E4 hist provider:", q(mh, "SELECT provider, COUNT(*), MIN(trade_date), MAX(trade_date), COUNT(DISTINCT symbol) FROM daily_bars GROUP BY provider ORDER BY 2 DESC"))

op.close(); mh.close()
