# -*- coding: utf-8 -*-
import sqlite3, collections, json
TL=r"D:/codex-A股交易/trading_local.sqlite3"; MH=r"D:/codex-A股交易/market_history.sqlite3"
c=sqlite3.connect(f"file:{TL}?mode=ro",uri=True); c.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")
Q="""
WITH b AS (SELECT symbol,trade_date,close,source FROM daily_bar_cache
   WHERE length(trade_date)=10 AND date(trade_date) IS NOT NULL
     AND trade_date BETWEEN '2023-09-04' AND '2026-09-04' AND close>0),
 l AS (SELECT symbol,trade_date,close,source,
        LAG(close) OVER (PARTITION BY symbol ORDER BY trade_date) pc,
        LAG(trade_date) OVER (PARTITION BY symbol ORDER BY trade_date) pd
       FROM b)
SELECT i.board, COUNT(*) FROM l JOIN mh.instruments i USING(symbol)
WHERE pc>0 AND abs(close/pc-1.0)>0.11 AND i.asset_type='stock' GROUP BY 1 ORDER BY 2 DESC"""
print("=== POOL: |ret|>0.11 by board (my count) ===")
tot=0
for b,n in c.execute(Q): print(f"   {str(b):10s} {n}"); tot+=n
print("   TOTAL", tot, "  (they claimed 27,454 / chi_next 15,698 / star 6,855 / beijing 4,753)")

print("\n=== validate my IPO exclusion: sample of events removed as 'first 6 sessions' ===")
E=json.load(open(r"D:/codex-A股交易/claude methods/_m1_evidence/adjv2_events.json"))
cal=[x[0] for x in c.execute("""SELECT trade_date FROM daily_bar_cache WHERE length(trade_date)=10
   AND date(trade_date) IS NOT NULL GROUP BY trade_date HAVING COUNT(DISTINCT symbol)>=1000 ORDER BY trade_date""")]
ci={d:i for i,d in enumerate(cal)}
inst={s:(ld,bd) for s,ld,bd in c.execute("SELECT symbol,list_date,board FROM mh.instruments")}
ipo=[]
for e in E:
    if abs(e['ret'])<=0.11: continue
    ld,bd=inst.get(e['symbol'],(None,None))
    if not ld or e['date'] not in ci: continue
    fut=[i for i,d in enumerate(cal) if d>=ld]
    if not fut: continue
    n=ci[e['date']]-fut[0]
    if n<=5: e['n']=n; ipo.append(e)
print(f"  events removed as IPO-window: {len(ipo)} / {len(set(x['symbol'] for x in ipo))} symbols")
print("  by board:", dict(collections.Counter(x['board'] for x in ipo)))
print("  session-since-listing histogram:", dict(sorted(collections.Counter(x['n'] for x in ipo).items())))
print("  sample (symbol, list_date, date, n_sessions_after_listing, ret):")
for e in sorted(ipo,key=lambda x:-abs(x['ret']))[:10]:
    print(f"    {e['symbol']} list={e['list_date']} {e['prev_date']}->{e['date']} n={e['n']} ret={e['ret']:+.3f} {e['board']}")
# independent confirmation: does market_history agree these IPO moves are real?
ok=absent=0
for e in ipo[:400]:
    a=c.execute("SELECT close FROM mh.daily_bars WHERE symbol=? AND trade_date=?",(e['symbol'],e['date'])).fetchone()
    b=c.execute("SELECT close FROM mh.daily_bars WHERE symbol=? AND trade_date=?",(e['symbol'],e['prev_date'])).fetchone()
    if not a or not b: absent+=1; continue
    if abs((a[0]/b[0]-1)-e['ret'])<0.01: ok+=1
print(f"  cross-check first 400 IPO-window events vs market_history: same move in mh = {ok}, absent = {absent}")
