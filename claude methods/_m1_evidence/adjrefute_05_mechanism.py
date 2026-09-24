import sqlite3, collections, statistics
TL=r"D:/codex-A股交易/trading_local.sqlite3"
MH=r"D:/codex-A股交易/market_history.sqlite3"
c=sqlite3.connect(f"file:{TL}?mode=ro",uri=True)
c.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")

XV = """FROM daily_bar_cache c
 JOIN mh.daily_bars m ON m.symbol=c.symbol AND m.trade_date=c.trade_date AND m.adjustment_mode='qfq'
 JOIN mh.instruments i ON i.symbol=c.symbol
 WHERE c.adjustment_mode='qfq' AND c.source=m.provider AND c.close>0 AND m.close>0
   AND i.exchange<>'INDEX'
   AND substr(m.available_at,1,10)<'2026-08-01' AND substr(c.updated_at,1,10)>='2026-09-01'"""

print("### M1 cross-vintage cohort: symbols total vs symbols with any >1% move")
s="SELECT COUNT(DISTINCT c.symbol) syms_in_cohort, COUNT(DISTINCT CASE WHEN abs(m.close/c.close-1.0)>0.01 THEN c.symbol END) syms_moved "+XV
print("SQL:",' '.join(s.split()))
print("   ",c.execute(s).fetchone())

print("\n### M2 SIGN of the move (old_vintage/new_vintage). qfq re-adjust should push ALL old>new")
s="SELECT SUM(m.close>c.close) old_higher, SUM(m.close<c.close) old_lower, SUM(m.close=c.close) equal "+XV+" AND abs(m.close/c.close-1.0)>0.01"
print("SQL:",' '.join(s.split()))
print("   ",c.execute(s).fetchone())

print("\n### M3 per-symbol structure: is ratio a CONSTANT factor on a DATE PREFIX (real corp action) or noise?")
s="""SELECT c.symbol, c.trade_date, m.close, c.close, m.close/c.close AS ratio """+XV+""" ORDER BY c.symbol, c.trade_date"""
rows=c.execute(s).fetchall()
by=collections.defaultdict(list)
for sym,d,mc,cc,r in rows: by[sym].append((d,r))
moved=[s_ for s_,v in by.items() if any(abs(r-1)>0.01 for _,r in v)]
print("SQL:",' '.join(s.split()))
print(f"   cohort symbols={len(by)}  symbols with a >1% move={len(moved)}")
clean_prefix=0; details=[]
for sym in moved:
    v=by[sym]
    off=[r for _,r in v if abs(r-1)>0.001]
    on =[r for _,r in v if abs(r-1)<=0.001]
    # contiguity: all differing dates must come before all matching dates
    idx_diff=[i for i,(d,r) in enumerate(v) if abs(r-1)>0.001]
    idx_same=[i for i,(d,r) in enumerate(v) if abs(r-1)<=0.001]
    contiguous = (not idx_diff) or (not idx_same) or (max(idx_diff) < min(idx_same))
    spread = (max(off)-min(off)) if off else 0.0
    if contiguous and spread<0.002: clean_prefix+=1
    details.append((sym,len(v),len(off),round(statistics.median(off),6) if off else None,round(spread,6),contiguous,
                    v[max(idx_diff)][0] if idx_diff else None, v[min(idx_same)][0] if idx_same else None))
print(f"   symbols whose diff is a CONSTANT factor on a clean date PREFIX (corp-action signature) = {clean_prefix}/{len(moved)}")
print("   sym, bars, diff_bars, median_ratio, ratio_spread, prefix_contiguous, last_diff_date, first_same_date")
for d in sorted(details,key=lambda x:-x[2])[:20]: print("   ",d)
c.close()
