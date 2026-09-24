# -*- coding: utf-8 -*-
import sqlite3, json, collections
TL=r"D:/codex-A股交易/trading_local.sqlite3"; MH=r"D:/codex-A股交易/market_history.sqlite3"
E=json.load(open(r"D:/codex-A股交易/claude methods/_m1_evidence/adjv2_events.json"))
c=sqlite3.connect(f"file:{TL}?mode=ro",uri=True); c.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")

cal=[x[0] for x in c.execute("""SELECT trade_date FROM daily_bar_cache
  WHERE date(trade_date) IS NOT NULL AND length(trade_date)=10
  GROUP BY trade_date HAVING COUNT(DISTINCT symbol)>=1000 ORDER BY trade_date""")]
cal_idx={d:i for i,d in enumerate(cal)}

for e in E:
    i,j=cal_idx.get(e['date']),cal_idx.get(e['prev_date'])
    e['sessions_gap']=(i-j) if (i is not None and j is not None) else None

def tick(src): return 0.0005 if (src or '').startswith('tonghuasun') else 0.005
V=[]
for e in E:
    P,C=e['prev_close'],e['close']
    tol=(tick(e['src'])+tick(e['psrc']))/2.0*(2+abs(e['ret']))/P   # 2dp/3dp rounding error on ret
    tol=max(tol,1e-6)
    if abs(e['ret'])-e['lim'] > tol:
        e['tol']=tol; V.append(e)
print(f"=== VIOLATIONS after per-event price-rounding tolerance: {len(V)} events / {len(set(x['symbol'] for x in V))} symbols")
for b,n in sorted(collections.Counter(x['board'] for x in V).items(),key=lambda k:-k[1]):
    print(f"   {b:10s} {n:5d} symbols={len(set(x['symbol'] for x in V if x['board']==b))}")

# ---- exclusion 1: IPO no-limit window (registration system: first 5 sessions unlimited, all boards) ----
def sess_since_list(sym,ld,date):
    if not ld: return None
    fut=[i for i,d in enumerate(cal) if d>=ld]
    if not fut: return None
    if date not in cal_idx: return None
    return cal_idx[date]-fut[0]        # 0 = listing day
# ---- exclusion 2: delisting consolidation period (退市整理期, last ~15 sessions) ----
buckets=collections.Counter(); kept=[]
for e in V:
    n=sess_since_list(e['symbol'],e['list_date'],e['date'])
    e['sess_since_list']=n
    delist_near=False
    if e['delist_date'] and e['date']<=e['delist_date']:
        i,j=cal_idx.get(e['date']),None
        fut=[k for k,d in enumerate(cal) if d>=e['delist_date']]
        if i is not None and fut: delist_near=(fut[0]-i)<=20
    e['delist_near']=delist_near
    if n is not None and n<=5: buckets['IPO_first6_sessions_no_limit']+=1
    elif e['sessions_gap'] not in (1,None): buckets['halt_resumption_gap']+=1
    elif delist_near: buckets['delisting_consolidation']+=1
    else: buckets['UNEXPLAINED']+=1; kept.append(e)
print("\n=== legitimate-cause exclusions ===")
for k,v in buckets.most_common(): print(f"   {k:34s} {v}")
print(f"\n=== UNEXPLAINED violations: {len(kept)} events / {len(set(x['symbol'] for x in kept))} symbols")
for b,n in sorted(collections.Counter(x['board'] for x in kept).items(),key=lambda k:-k[1]):
    print(f"   {b:10s} {n:5d} symbols={len(set(x['symbol'] for x in kept if x['board']==b))}")
print("   by source:", dict(collections.Counter(x['src'] for x in kept)))

# ---- cross-check vs market_history (independent snapshot) ----
res=collections.Counter(); det=[]
for e in kept:
    a=c.execute("SELECT close FROM mh.daily_bars WHERE symbol=? AND trade_date=? AND adjustment_mode='qfq'",(e['symbol'],e['date'])).fetchone()
    b=c.execute("SELECT close FROM mh.daily_bars WHERE symbol=? AND trade_date=? AND adjustment_mode='qfq'",(e['symbol'],e['prev_date'])).fetchone()
    if not a or not b or not a[0] or not b[0]:
        res['UNVERIFIABLE_absent_from_market_history']+=1; e['mh']='absent'; det.append(e); continue
    r2=a[0]/b[0]-1
    if abs(r2)-e['lim']>e['tol']*10: res['CONFIRMED_by_second_source']+=1; e['mh']='confirmed'
    elif abs(abs(r2)-abs(e['ret']))<0.005: res['CONFIRMED_by_second_source']+=1; e['mh']='confirmed'
    elif abs(r2)<=e['lim']: res['CACHE_ONLY_no_jump_in_mh']+=1; e['mh']='cache_only'; det.append(e)
    else: res['DIFFERS']+=1; e['mh']='differs'; det.append(e)
    e['mh_ret']=r2
print("\n=== cross-check of UNEXPLAINED violations vs market_history qfq ===")
for k,v in res.most_common(): print(f"   {k:40s} {v}   ({v/len(kept)*100:.1f}%)")
print("\n   unverifiable by board:", dict(collections.Counter(e['board'] for e in kept if e.get('mh')=='absent')))
print("   cache-only by board:  ", dict(collections.Counter(e['board'] for e in kept if e.get('mh')=='cache_only')))
print("   BJ unexplained all from tonghuasun?:",
      dict(collections.Counter(e['src'] for e in kept if e['board']=='beijing')))
json.dump(kept,open(r"D:/codex-A股交易/claude methods/_m1_evidence/adjv2_unexplained.json","w"),ensure_ascii=False)
print("\n=== worst 15 unexplained ===")
for e in sorted(kept,key=lambda x:-abs(x['ret']))[:15]:
    print(f"  {e['symbol']} {e['prev_date']}->{e['date']} {e['prev_close']:>9.3f}->{e['close']:>9.3f} ret={e['ret']:+.4f} lim={e['lim']} {e['board']:9s} mh={e.get('mh')} src={e['src'][:28]}")
