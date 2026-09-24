# -*- coding: utf-8 -*-
import sqlite3, collections, json
c=sqlite3.connect(r"file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True)
c.execute(r"ATTACH DATABASE 'file:D:/codex-A股交易/market_history.sqlite3?mode=ro' AS mh")
BASE="""
WITH b AS (SELECT symbol,trade_date,close,source FROM daily_bar_cache
   WHERE length(trade_date)=10 AND date(trade_date) IS NOT NULL
     AND trade_date BETWEEN '2023-09-04' AND '2026-09-04' AND close>0),
 l AS (SELECT symbol,trade_date,close,source,
        LAG(close) OVER (PARTITION BY symbol ORDER BY trade_date) pc
       FROM b)
SELECT %s FROM l JOIN mh.instruments i USING(symbol) WHERE pc>0 AND i.asset_type='stock' AND %s"""
def cnt(e): return c.execute(BASE%("COUNT(*), COUNT(DISTINCT symbol)",e)).fetchone()
R=("(i.board IN ('sh_main','sz_main') AND abs(close/pc-1.0)>{m}) OR "
   "(i.board IN ('chi_next','star') AND abs(close/pc-1.0)>{w}) OR "
   "(i.board='beijing' AND abs(close/pc-1.0)>{b})")
print("=== reverse-engineering their 430 events / 274 symbols ===")
for m,w,b,lbl in [(.105,.205,.305,"limit + 0.005"),(.105,.21,.315,"limit x 1.05"),
                  (.1005,.2005,.3005,"limit + 0.0005"),(.102,.202,.302,"limit + 0.002"),
                  (.103,.203,.303,"limit + 0.003"),(.104,.204,.304,"limit + 0.004"),
                  (.106,.206,.306,"limit + 0.006"),(.11,.205,.305,"0.11 floor + .005")]:
    e,s=cnt(R.format(m=m,w=w,b=b)); flag="  <== closest" if abs(e-430)<25 else ""
    print(f"   {lbl:22s} events={e:6d} symbols={s:5d}{flag}")

print("\n############### MY FINAL TIERED RESULT ###############")
K=json.load(open(r"D:/codex-A股交易/claude methods/_m1_evidence/adjv2_unexplained.json"))
print("Tier 0  statutory limit, no tolerance      : 27,302 events / 4,417 symbols  (99% = 2dp rounding on legit limit days -> UNUSABLE)")
print(f"Tier 1  beyond per-event price-rounding    : 2,523 events / 1,096 symbols")
print(f"Tier 2  Tier1 minus IPO-no-limit & halts   : {len(K)} events / {len(set(e['symbol'] for e in K))} symbols")
mat=[e for e in K if abs(e['ret'])-e['lim']>0.01]
print(f"Tier 3  Tier2 with MATERIAL excess >1pp    : {len(mat)} events / {len(set(e['symbol'] for e in mat))} symbols")
print("        Tier3 by board:", dict(collections.Counter(e['board'] for e in mat)))
print("        Tier3 by mh verdict:", dict(collections.Counter(e['mh'] for e in mat)))
print("        Tier3 by source:", dict(collections.Counter(e['src'] for e in mat)))

print("\n--- does 'confirmed' mean the SAME number in both stores? ---")
cf=[e for e in K if e['mh']=='confirmed']
close_agree=sum(1 for e in cf if abs(e['mh_ret']-e['ret'])<0.002)
print(f"   confirmed events: {len(cf)}; cache ret within 0.002 of mh ret: {close_agree} ({close_agree/len(cf)*100:.1f}%)")
print("   -> these are the SAME price path in an independent store, i.e. qfq representation, not a cache defect")

print("\n--- the genuinely actionable core ---")
disc=[e for e in K if e['mh'] in ('cache_only','differs')]
unv=[e for e in K if e['mh']=='absent']
print(f"   A) cache CONTRADICTED by market_history : {len(disc)} events / {len(set(e['symbol'] for e in disc))} symbols"
      f"  (cache_only {sum(1 for e in disc if e['mh']=='cache_only')}, differs {sum(1 for e in disc if e['mh']=='differs')})")
print(f"      by source:", dict(collections.Counter(e['src'] for e in disc)))
print(f"      sitting on a source change (splice): {sum(1 for e in disc if e['src']!=e['psrc'])}/{len(disc)}")
print(f"   B) UNVERIFIABLE (absent from mh)        : {len(unv)} events / {len(set(e['symbol'] for e in unv))} symbols")
print(f"      by board:", dict(collections.Counter(e['board'] for e in unv)))
print(f"      by source:", dict(collections.Counter(e['src'] for e in unv)))
print(f"      pct of Tier2: {len(unv)/len(K)*100:.1f}%")
print("\n--- BJ second-source availability (the hard blocker) ---")
print("   mh.daily_bars BJ rows before 2025-11-17:",
   c.execute("SELECT COUNT(*) FROM mh.daily_bars WHERE symbol LIKE 'BJ%' AND trade_date<'2025-11-17'").fetchone()[0])
print("   cache BJ rows before 2025-11-17:",
   c.execute("SELECT COUNT(*) FROM daily_bar_cache WHERE symbol LIKE 'BJ%' AND length(trade_date)=10 AND trade_date<'2025-11-17'").fetchone()[0])
