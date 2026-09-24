import sqlite3, datetime
TL = "D:/codex-A股交易/trading_local.sqlite3"
MH = "D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
tl, mh = ro(TL), ro(MH)
W0, W1 = '2023-09-04', '2026-09-04'

print("### A. Benchmark series, exact, independent of their SQL")
for s in ('SH000300','SH000001'):
    r = tl.execute("""SELECT COUNT(*), COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date),
                             SUM(close IS NULL), SUM(volume IS NULL), SUM(amount IS NULL),
                             MIN(close), MAX(close)
                      FROM daily_bar_cache WHERE symbol=?""", (s,)).fetchone()
    print(f"  {s}: rows={r[0]} distinct_dates={r[1]} {r[2]}..{r[3]} nullclose={r[4]} nullvol={r[5]} nullamt={r[6]} close_range=({r[7]:.2f},{r[8]:.2f})")
    print("     source/adj/vol_unit:", tl.execute(
        "SELECT source, adjustment_mode, volume_unit, quality_status, COUNT(*) FROM daily_bar_cache WHERE symbol=? GROUP BY 1,2,3,4",(s,)).fetchall())
# do the two share identical date sets?
d300 = {r[0] for r in tl.execute("SELECT trade_date FROM daily_bar_cache WHERE symbol='SH000300'")}
d001 = {r[0] for r in tl.execute("SELECT trade_date FROM daily_bar_cache WHERE symbol='SH000001'")}
print(f"  identical date sets? {d300==d001}  |300|={len(d300)} |001|={len(d001)} sym_diff={len(d300^d001)}")
# any benchmark row strictly inside window but before 2024-06-19?
print("  benchmark rows in", W0, "..2024-06-18 :",
      tl.execute("SELECT COUNT(*) FROM daily_bar_cache WHERE symbol IN ('SH000300','SH000001') AND trade_date>=? AND trade_date<='2024-06-18'",(W0,)).fetchone()[0])
# benchmark rows outside window entirely (any date)
print("  benchmark rows outside", W0,"..",W1,":",
      tl.execute("SELECT COUNT(*) FROM daily_bar_cache WHERE symbol IN ('SH000300','SH000001') AND (trade_date<? OR trade_date>?)",(W0,W1)).fetchone()[0])

print()
print("### B. My OWN session calendar, three independent constructions")
# ctor 1: my own breadth calendar from trading_local, EXPLICIT stock-code filter (not 'NOT LIKE SH00%')
cal_tl = [r[0] for r in tl.execute(f"""
 SELECT trade_date FROM daily_bar_cache
 WHERE ( (substr(symbol,1,2)='SH' AND substr(symbol,3,1)='6')
      OR (substr(symbol,1,2)='SZ' AND substr(symbol,3,1) IN ('0','3'))
      OR (substr(symbol,1,2)='BJ') )
   AND length(symbol)=8 AND trade_date BETWEEN '{W0}' AND '{W1}'
 GROUP BY trade_date HAVING COUNT(DISTINCT symbol)>=100 ORDER BY trade_date""")]
# ctor 2: research store market_history.daily_bars (the OTHER database) — independent evidence
cal_mh = [r[0] for r in mh.execute(f"""
 SELECT trade_date FROM daily_bars
 WHERE trade_date BETWEEN '{W0}' AND '{W1}'
 GROUP BY trade_date HAVING COUNT(DISTINCT symbol)>=100 ORDER BY trade_date""")]
# ctor 3: union of both stores = most generous session calendar available on disk
cal_union = sorted(set(cal_tl) | set(cal_mh))
for nm, cal in (("trading_local breadth>=100", cal_tl), ("market_history breadth>=100", cal_mh), ("UNION of both stores", cal_union)):
    print(f"  {nm:32} n={len(cal):4} {cal[0]}..{cal[-1]}")

print()
print("### C. THE CRUX — decompose the 547 vs 538 gap")
cal = cal_tl
calset = set(cal)
bmin, bmax = min(d300), max(d300)
inside  = sorted(d for d in calset if bmin <= d <= bmax)
before  = sorted(d for d in calset if d < bmin)
after   = sorted(d for d in calset if d > bmax)
interior_gaps = sorted(d for d in inside if d not in d300)
print(f"  cal days in window            = {len(calset)}")
print(f"  benchmark days in window      = {len([d for d in d300 if W0<=d<=W1])}")
print(f"  cal days BEFORE bench start   = {len(before)}  -> {before}")
print(f"  cal days AFTER  bench end     = {len(after)}   -> {after}")
print(f"  cal days INSIDE bench range   = {len(inside)}")
print(f"  INTERIOR gaps (real misses)   = {len(interior_gaps)} -> {interior_gaps}")
print(f"  bench dates NOT in cal        = {len([d for d in d300 if d not in calset])} -> {sorted(d for d in d300 if d not in calset)}")
print(f"  CHECK 547-538 = {len(calset)-len([d for d in d300 if W0<=d<=W1])} ; before+after = {len(before)+len(after)} ; interior = {len(interior_gaps)}")

print()
print("### D. Their 4th number: derived sessions in the dark period")
print("  cal days 2023-09-04..2024-06-18 (their claim: check) =",
      len([d for d in calset if W0<=d<='2024-06-18']))
print("  earliest breadth date in trading_local =", cal_tl[0])
print("  earliest breadth date in market_history =", cal_mh[0])

print()
print("### E. Is there ANY trading-calendar table?")
for lbl, c in (("trading_local", tl), ("market_history", mh)):
    hits = c.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view') AND (lower(name) LIKE '%calendar%' OR lower(name) LIKE '%trading_day%' OR lower(name) LIKE '%session%')").fetchall()
    print(f"  {lbl}: {hits}")
print("  market_history.schema_metadata:", mh.execute("SELECT * FROM schema_metadata").fetchall())

print()
print("### F. Weekday arithmetic upper bound (their 785)")
d = datetime.date(2023,9,4); e = datetime.date(2026,9,4); n=0
while d<=e:
    if d.weekday()<5: n+=1
    d += datetime.timedelta(days=1)
print("  weekdays 2023-09-04..2026-09-04 =", n)
tl.close(); mh.close()
