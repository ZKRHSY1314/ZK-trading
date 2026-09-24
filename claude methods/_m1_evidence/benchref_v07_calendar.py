import sqlite3, sys
TL = "D:/codex-A股交易/trading_local.sqlite3"
MH = "D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
tl, mh = ro(TL), ro(MH)
W0, W1 = '2023-09-04', '2026-09-04'
def P(*a): print(*a); sys.stdout.flush()

P("indexes on daily_bar_cache:", [r[0] for r in tl.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='daily_bar_cache'")])

# ---- ONE scan: per-date distinct stock count (stocks only; indices + 6-digit dupes excluded)
P("\nscanning trading_local.daily_bar_cache ...")
breadth = dict(tl.execute("""
  SELECT trade_date, COUNT(DISTINCT symbol)
  FROM daily_bar_cache
  WHERE symbol GLOB '[SB][HZJ][0-9][0-9][0-9][0-9][0-9][0-9]'
    AND symbol NOT IN ('SH000300','SH000001')
    AND close IS NOT NULL
  GROUP BY trade_date""").fetchall())
P("   distinct trade_dates with >=1 stock:", len(breadth))

P("scanning market_history.daily_bars ...")
mh_breadth = dict(mh.execute("""
  SELECT trade_date, COUNT(DISTINCT symbol) FROM daily_bars WHERE close IS NOT NULL GROUP BY trade_date""").fetchall())
P("   distinct trade_dates:", len(mh_breadth))

bench = set(r[0] for r in tl.execute("SELECT DISTINCT trade_date FROM daily_bar_cache WHERE symbol='SH000300'"))
P("   benchmark days:", len(bench))

def cal(d, thr): return sorted(k for k,v in d.items() if v>=thr)

P("\n### A. TRADING_LOCAL calendar sensitivity, restricted to window %s..%s" % (W0,W1))
P("   thr | sessions_in_window | first | last | bench_present | bench_missing | sessions_before_2024-06-19")
for thr in (1,50,100,500,1000,2000,3000,4000,5000):
    c=[d for d in cal(breadth,thr) if W0<=d<=W1]
    if not c: P(f"   {thr:5d} | 0"); continue
    pres=sum(1 for d in c if d in bench); miss=len(c)-pres
    pre=sum(1 for d in c if d < '2024-06-19')
    P(f"   {thr:5d} | {len(c):4d} | {c[0]} | {c[-1]} | {pres:4d} | {miss:4d} | {pre:4d}")

P("\n### B. MARKET_HISTORY calendar sensitivity (independent store), same window")
for thr in (1,100,1000,3000,4000,5000):
    c=[d for d in cal(mh_breadth,thr) if W0<=d<=W1]
    if not c: P(f"   {thr:5d} | 0"); continue
    pres=sum(1 for d in c if d in bench)
    P(f"   {thr:5d} | {len(c):4d} | {c[0]} | {c[-1]} | bench_present={pres} bench_missing={len(c)-pres}")

P("\n### C. UNION calendar (either store, >=100 stocks) — the most generous session estimate")
u=sorted(set(cal(breadth,100)) | set(cal(mh_breadth,100)))
uw=[d for d in u if W0<=d<=W1]
P(f"   union sessions in window: {len(uw)}  {uw[0]}..{uw[-1]}")
P(f"   benchmark present: {sum(1 for d in uw if d in bench)}   missing: {sum(1 for d in uw if d not in bench)}")
P(f"   sessions in window BEFORE first benchmark day 2024-06-19: {sum(1 for d in uw if d<'2024-06-19')}")
P(f"   sessions in window AFTER last benchmark day 2026-09-02:  {sum(1 for d in uw if d>'2026-09-02')}")

P("\n### D. The 9 'missing' days INSIDE the benchmark span (trading_local thr=100)")
c100=[d for d in cal(breadth,100) if W0<=d<=W1]
inside=[d for d in c100 if '2024-06-19'<=d<='2026-09-02' and d not in bench]
P("   count:", len(inside))
for d in inside: P(f"     {d}  stock_breadth={breadth[d]}  mh_breadth={mh_breadth.get(d,'-')}")

P("\n### E. Breadth onset — when does trading_local first exceed thresholds?")
allc=sorted(breadth)
P("   overall first/last date with any stock:", allc[0], allc[-1])
for thr in (100,1000,3000,4000,5000):
    f=[d for d in allc if breadth[d]>=thr]
    P(f"   thr={thr:5d} first={f[0] if f else None} n={len(f)}")
P("   market_history first/last:", min(mh_breadth), max(mh_breadth))
for thr in (100,1000,3000,4000,5000):
    f=sorted(d for d in mh_breadth if mh_breadth[d]>=thr)
    P(f"   MH thr={thr:5d} first={f[0] if f else None} n={len(f)}")

P("\n### F. Daily breadth 2024-05-27..2024-06-28 (both stores)")
for d in sorted(x for x in breadth if '2024-05-27'<=x<='2024-06-28'):
    P(f"   {d} TL={breadth[d]:5d} MH={mh_breadth.get(d,0):5d} bench={'Y' if d in bench else '.'}")
