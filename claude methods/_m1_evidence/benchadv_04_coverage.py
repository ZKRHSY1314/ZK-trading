# -*- coding: utf-8 -*-
import sqlite3, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
def q(c,s,a=()): return c.execute(s,a).fetchall()
tl=ro(TL); mh=ro(MH)
W0,W1='2023-09-04','2026-09-04'

print("="*100)
print("A. BENCHMARK COVERAGE vs the trading calendar actually present in the same store")
print("="*100)
cal = q(tl,"SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date>=? AND trade_date<=?",(W0,W1))[0][0]
print(f"  distinct trade_date in TL.daily_bar_cache within {W0}..{W1}  = {cal}")
calmh = q(mh,"SELECT COUNT(DISTINCT trade_date) FROM daily_bars WHERE trade_date>=? AND trade_date<=?",(W0,W1))[0][0]
print(f"  distinct trade_date in MH.daily_bars     within window        = {calmh}")
for s in ("SH000300","SH000001"):
    n=q(tl,"SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE symbol=? AND trade_date>=? AND trade_date<=?",(s,W0,W1))[0][0]
    print(f"  {s}: {n} of {cal} window trading days = {100.0*n/cal:.1f}%  -> MISSING {cal-n} days")

print()
print("  Where is the benchmark missing? days present in cache but absent for SH000300, bucketed by year:")
rows=q(tl,"""
SELECT substr(d.trade_date,1,4) yr, COUNT(*) missing_days
FROM (SELECT DISTINCT trade_date FROM daily_bar_cache WHERE trade_date>=? AND trade_date<=?) d
LEFT JOIN (SELECT DISTINCT trade_date FROM daily_bar_cache WHERE symbol='SH000300') b
  ON b.trade_date=d.trade_date
WHERE b.trade_date IS NULL
GROUP BY yr ORDER BY yr
""",(W0,W1))
for yr,n in rows: print(f"    {yr}: {n} window trading days with NO CSI300 bar")

print()
print("B. Do the 39 backtest runs actually overlap the period where SH000300 exists?")
print("-"*100)
cols=[r[1] for r in q(tl,"PRAGMA table_info(historical_backtest_runs)")]
print("  cols:", cols)
dc=[c for c in cols if 'start' in c or 'end' in c or 'date' in c]
print("  date cols:", dc)
if dc:
    sel=",".join(dc)
    print("  run windows (sample):", q(tl,f"SELECT {sel}, COUNT(*) FROM historical_backtest_runs GROUP BY {sel} ORDER BY 1 LIMIT 15"))
eq=q(tl,"SELECT MIN(trade_date),MAX(trade_date),COUNT(*) FROM historical_backtest_daily_equity")[0]
print(f"  historical_backtest_daily_equity span: {eq[0]}..{eq[1]} rows={eq[2]}")
before=q(tl,"SELECT COUNT(*) FROM historical_backtest_daily_equity WHERE trade_date<'2024-06-19'")[0][0]
print(f"  equity rows on dates BEFORE first CSI300 bar (2024-06-19): {before} of {eq[2]}"
      f"  = {100.0*before/eq[2]:.1f}% -> benchmark cannot exist for these")

print()
print("C. forecast_outcomes.benchmark_return -- is it really an index return, or a cross-sectional proxy?")
print("-"*100)
oc=[r[1] for r in q(tl,"PRAGMA table_info(forecast_outcomes)")]
dcol=[c for c in oc if 'date' in c.lower()]
print("  date-ish cols:", dcol)
print("  distinct benchmark_return values (top 10 by freq):",
      q(tl,"SELECT ROUND(benchmark_return,6), COUNT(*) FROM forecast_outcomes GROUP BY 1 ORDER BY 2 DESC LIMIT 10"))
print("  n distinct benchmark_return:", q(tl,"SELECT COUNT(DISTINCT benchmark_return) FROM forecast_outcomes")[0][0])
print("  min/max/avg:", q(tl,"SELECT MIN(benchmark_return),MAX(benchmark_return),AVG(benchmark_return) FROM forecast_outcomes")[0])
if dcol:
    d0=dcol[0]
    print(f"  span of {d0}:", q(tl,f"SELECT MIN({d0}),MAX({d0}) FROM forecast_outcomes")[0])
    print("  rows before 2024-06-19:", q(tl,f"SELECT COUNT(*) FROM forecast_outcomes WHERE {d0}<'2024-06-19'")[0][0])
tl.close(); mh.close()
