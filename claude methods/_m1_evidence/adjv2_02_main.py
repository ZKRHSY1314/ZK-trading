# -*- coding: utf-8 -*-
import sqlite3, json, collections
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
W0, W1 = '2023-09-04', '2026-09-04'

c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
c.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")

# ---------- independent method: SQL window function LAG, not a python loop ----------
# strict date validity: 10 chars, parseable by sqlite date()
BASE = """
  SELECT symbol, trade_date, open, high, low, close, volume, amount, source
  FROM daily_bar_cache
  WHERE date(trade_date) IS NOT NULL AND length(trade_date)=10
    AND trade_date >= :w0 AND trade_date <= :w1
    AND close IS NOT NULL AND close > 0
"""
print("=== A. window row/symbol counts under MY filter ===")
r = c.execute(f"SELECT COUNT(*), COUNT(DISTINCT symbol) FROM ({BASE})", {"w0":W0,"w1":W1}).fetchone()
print("rows,symbols with valid date & positive close:", r)
print("rows failing date validity in raw window-ish scan:",
      c.execute("SELECT COUNT(*) FROM daily_bar_cache WHERE date(trade_date) IS NULL OR length(trade_date)<>10").fetchone())
print("distinct bad trade_date values:",
      c.execute("SELECT DISTINCT trade_date FROM daily_bar_cache WHERE date(trade_date) IS NULL OR length(trade_date)<>10 LIMIT 10").fetchall())
print("null/nonpositive close in window:",
      c.execute("SELECT COUNT(*) FROM daily_bar_cache WHERE length(trade_date)=10 AND date(trade_date) IS NOT NULL AND trade_date BETWEEN ? AND ? AND (close IS NULL OR close<=0)",(W0,W1)).fetchone())

# ---------- market calendar from cache (sessions where >=100 symbols trade) ----------
cal = [x[0] for x in c.execute("""
  SELECT trade_date FROM daily_bar_cache
  WHERE date(trade_date) IS NOT NULL AND length(trade_date)=10
  GROUP BY trade_date HAVING COUNT(DISTINCT symbol) >= 100 ORDER BY trade_date""")]
cal_idx = {d:i for i,d in enumerate(cal)}
print(f"\n=== B. calendar sessions built from cache (>=100 symbols/day): {len(cal)}, {cal[0]}..{cal[-1]}")

# ---------- board map: INDEPENDENT SOURCE = mh.instruments, not code prefix ----------
inst = {}
for sym,board,ld,dd,status,exch,atype in c.execute(
    "SELECT symbol,board,list_date,delist_date,status,exchange,asset_type FROM mh.instruments"):
    inst[sym] = dict(board=board, list_date=ld, delist_date=dd, status=status, exch=exch, atype=atype)
LIMIT = {'sh_main':0.10,'sz_main':0.10,'chi_next':0.20,'star':0.20,'beijing':0.30}
print("instruments loaded:", len(inst))

# ---------- pull returns via LAG ----------
Q = f"""
SELECT symbol, trade_date, prev_date, close, prev_close, open, high, low, source, prev_source
FROM (
  SELECT symbol, trade_date, close, open, high, low, source,
         LAG(trade_date) OVER (PARTITION BY symbol ORDER BY trade_date) prev_date,
         LAG(close)      OVER (PARTITION BY symbol ORDER BY trade_date) prev_close,
         LAG(source)     OVER (PARTITION BY symbol ORDER BY trade_date) prev_source
  FROM ({BASE})
) WHERE prev_close IS NOT NULL AND prev_close>0
"""
events=[]; total_pairs=0; nonstock=collections.Counter(); noinst=collections.Counter()
for sym,d,pd_,cl,pcl,op,hi,lo,src,psrc in c.execute(Q, {"w0":W0,"w1":W1}):
    total_pairs+=1
    ret = cl/pcl - 1.0
    meta = inst.get(sym)
    if meta is None:
        noinst[sym]+=1; continue
    if meta['atype']!='stock':
        nonstock[sym]+=1; continue
    lim = LIMIT.get(meta['board'])
    if lim is None: nonstock[sym]+=1; continue
    if abs(ret) > lim + 1e-9:
        events.append(dict(symbol=sym,date=d,prev_date=pd_,close=cl,prev_close=pcl,
                           open=op,high=hi,low=lo,src=src,psrc=psrc,ret=ret,
                           board=meta['board'],lim=lim,list_date=meta['list_date'],
                           delist_date=meta['delist_date'],status=meta['status']))
print(f"\n=== C. consecutive-row pairs evaluated: {total_pairs}")
print("symbols with NO instruments row (excluded):", len(noinst), dict(list(noinst.items())[:10]))
print("symbols non-stock / unknown board (excluded):", len(nonstock), dict(list(nonstock.items())[:10]))
print(f"RAW over-own-limit events (no exclusions): {len(events)} over {len(set(e['symbol'] for e in events))} symbols")
for b,n in sorted(collections.Counter(e['board'] for e in events).items(), key=lambda x:-x[1]):
    print(f"   {b:10s} {n:5d}  symbols={len(set(e['symbol'] for e in events if e['board']==b))}")

json.dump(events, open(r"D:/codex-A股交易/claude methods/_m1_evidence/adjv2_events.json","w"), ensure_ascii=False)

# ---------- gap classification against the real calendar ----------
gapc = collections.Counter()
for e in events:
    i,j = cal_idx.get(e['date']), cal_idx.get(e['prev_date'])
    e['sessions_gap'] = (i-j) if (i is not None and j is not None) else None
    gapc['consecutive' if e['sessions_gap']==1 else ('gap' if e['sessions_gap'] else 'unknown')]+=1
print("\n=== D. session gap (real calendar):", dict(gapc))
