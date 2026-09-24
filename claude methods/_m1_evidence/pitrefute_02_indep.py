import sqlite3
from datetime import date
OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
c = ro(OP)

print("=== A. Is the 2026-06-30 created_at floor a whole-DB artifact? other tables' oldest rows ===")
for t in ["forecast_decisions","forecast_outcomes","forecast_evaluations",
          "historical_backtest_runs","historical_backtest_daily_equity"]:
    try:
        cols=[r[1] for r in c.execute(f"PRAGMA table_info({t})")]
        tc=[x for x in cols if x in ("created_at","started_at","recorded_at","generated_at","decision_date","run_date")]
        if not tc: print(f"  {t}: no time col in {cols[:8]}"); continue
        col=tc[0]
        q=f"SELECT COUNT(*), MIN({col}), MAX({col}) FROM {t}"
        print(f"  SQL: {q}\n   ->", list(c.execute(q))[0])
    except Exception as e: print("  ",t,"ERR",e)

print("\n=== B. INDEPENDENT lag computation via Python date math (no julianday) ===")
q = """SELECT substr(created_at,1,10) AS cdate, trade_date, COUNT(*) AS n
FROM daily_bar_cache
WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
  AND trade_date >= '2023-09-04' AND trade_date <= '2026-09-04'
GROUP BY 1,2"""
print("SQL:", q)
buckets={}
tot=0; neg=0
mind=10**9; maxd=-10**9
for cd, td, n in c.execute(q):
    d=(date.fromisoformat(cd)-date.fromisoformat(td)).days
    tot+=n
    if d<0: neg+=n
    mind=min(mind,d); maxd=max(maxd,d)
    if d==0: k="A_same_day"
    elif d<=3: k="B_1to3d"
    elif d<=30: k="C_4to30d"
    elif d<=90: k="D_31to90d"
    elif d<=365: k="E_91to365d"
    elif d<=730: k="F_1to2y"
    else: k="G_over2y"
    buckets[k]=buckets.get(k,0)+n
print(f"  total window rows = {tot}; negative-lag rows = {neg}; lag range = {mind}..{maxd} days")
for k in sorted(buckets):
    print(f"  {k:12s} {buckets[k]:>9,}  {100*buckets[k]/tot:6.2f}%")
live=buckets.get("A_same_day",0)+buckets.get("B_1to3d",0)
print(f"  <=3d 'live/near-live' = {live:,} = {100*live/tot:.2f}%   backfilled = {tot-live:,} = {100*(tot-live)/tot:.2f}%")

print("\n=== C. Do the 'same-day' rows come from the SAME bulk-load batches? ===")
q2 = """SELECT substr(created_at,1,10) cdate, COUNT(*) n, COUNT(DISTINCT symbol) syms,
        MIN(trade_date) mn, MAX(trade_date) mx
FROM daily_bar_cache
WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
  AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'
  AND substr(created_at,1,10) = trade_date
GROUP BY 1 ORDER BY 1"""
print("SQL:", q2)
for r in c.execute(q2): print("  ", r)

print("\n=== D. For each created_at DAY (load batch): rowcount + trade_date span it wrote ===")
q3 = """SELECT substr(created_at,1,10) cdate, COUNT(*) n, COUNT(DISTINCT trade_date) tdays,
        MIN(trade_date) mn, MAX(trade_date) mx
FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
GROUP BY 1 ORDER BY 1"""
print("SQL:", q3)
for r in c.execute(q3): print("  ", r)
c.close()
