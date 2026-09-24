# -*- coding: utf-8 -*-
import sqlite3
HIST = r"D:/codex-A股交易/market_history.sqlite3"
OPS  = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

h = ro(HIST); qh = lambda s,a=(): h.execute(s,a).fetchall()
o = ro(OPS);  qo = lambda s,a=(): o.execute(s,a).fetchall()
W0,W1 = '2023-09-04','2026-09-04'

print("### Q7 HIST daily_bars: is there a DATED universe implicit in the bars?")
print("distinct symbols & dates in window:",
  qh("SELECT COUNT(DISTINCT symbol), COUNT(DISTINCT trade_date) FROM daily_bars WHERE trade_date BETWEEN ? AND ?", (W0,W1)))

print("\n### Q8 per-symbol LAST bar date in window -> delisting/suspension evidence?")
print(qh(f"""WITH last_seen AS (
  SELECT symbol, MAX(trade_date) mx, MIN(trade_date) mn FROM daily_bars
  WHERE trade_date BETWEEN '{W0}' AND '{W1}' GROUP BY symbol)
SELECT
  COUNT(*) symbols_with_bars,
  SUM(mx >= '2026-08-25') still_trading_late,
  SUM(mx <  '2026-08-25') stops_before_late,
  SUM(mx <  '2026-01-01') stops_before_2026,
  SUM(mx <  '2025-01-01') stops_before_2025,
  MIN(mx), MAX(mx) FROM last_seen"""))

print("\n### Q9 OPS daily_bar_cache (THE store the backtest actually reads) same test")
print(qo(f"""WITH last_seen AS (
  SELECT symbol, MAX(trade_date) mx FROM daily_bar_cache
  WHERE trade_date BETWEEN '{W0}' AND '{W1}' GROUP BY symbol)
SELECT COUNT(*) symbols, SUM(mx>='2026-08-25') late, SUM(mx<'2026-08-25') early_stop,
       SUM(mx<'2026-01-01') stop_pre2026, MIN(mx), MAX(mx) FROM last_seen"""))

print("\n### Q10 distinct-symbol count per trade_date -- does the cross-section GROW over time?")
for r in qh(f"""SELECT trade_date, COUNT(DISTINCT symbol) n FROM daily_bars
   WHERE trade_date IN ('2023-09-04','2023-09-05','2024-03-01','2024-09-04','2025-03-03','2025-09-04','2026-03-02','2026-07-14','2026-09-03','2026-09-04')
   GROUP BY trade_date ORDER BY trade_date"""):
    print(r)

print("\n### Q11 same for OPS daily_bar_cache")
for r in qo(f"""SELECT trade_date, COUNT(DISTINCT symbol) n FROM daily_bar_cache
   WHERE trade_date IN ('2023-09-04','2024-03-01','2024-09-04','2025-03-03','2025-09-04','2026-03-02','2026-07-14','2026-09-03','2026-09-04')
   GROUP BY trade_date ORDER BY trade_date"""):
    print(r)

print("\n### Q12 symbols present in bars but ABSENT from instruments (=delisted names surviving in bar data?)")
hist_syms = set(x[0] for x in qh(f"SELECT DISTINCT symbol FROM daily_bars WHERE trade_date BETWEEN '{W0}' AND '{W1}'"))
inst = set(x[0] for x in qh("SELECT symbol FROM instruments"))
ops_syms = set(x[0] for x in qo(f"SELECT DISTINCT symbol FROM daily_bar_cache WHERE trade_date BETWEEN '{W0}' AND '{W1}'"))
print("HIST bar symbols:", len(hist_syms), "| instruments:", len(inst), "| OPS cache symbols:", len(ops_syms))
print("in HIST bars NOT in instruments:", len(hist_syms - inst), sorted(hist_syms - inst)[:20])
print("in instruments NOT in HIST bars:", len(inst - hist_syms), sorted(inst - hist_syms)[:20])
print("in OPS cache NOT in instruments:", len(ops_syms - inst), sorted(ops_syms - inst)[:25])
print("in OPS cache NOT in HIST bars:", len(ops_syms - hist_syms), sorted(ops_syms - hist_syms)[:25])
h.close(); o.close()
