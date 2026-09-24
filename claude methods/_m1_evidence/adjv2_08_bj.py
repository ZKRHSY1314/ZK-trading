# -*- coding: utf-8 -*-
import sqlite3, collections
c=sqlite3.connect(r"file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True)
c.execute(r"ATTACH DATABASE 'file:D:/codex-A股交易/market_history.sqlite3?mode=ro' AS mh")
BASE="""
WITH b AS (SELECT symbol,trade_date,close,source FROM daily_bar_cache
   WHERE length(trade_date)=10 AND date(trade_date) IS NOT NULL
     AND trade_date BETWEEN '2023-09-04' AND '2026-09-04' AND close>0),
 l AS (SELECT symbol,trade_date,close,source,
        LAG(close) OVER (PARTITION BY symbol ORDER BY trade_date) pc
       FROM b)
SELECT %s FROM l JOIN mh.instruments i USING(symbol) WHERE pc>0 AND i.asset_type='stock' %s"""
print("=== DECISIVE: BJ (board='beijing') symbol-days with |ret| > 0.30, whole window ===")
print(c.execute(BASE % ("COUNT(*), COUNT(DISTINCT symbol)", "AND i.board='beijing' AND abs(close/pc-1.0)>0.30")).fetchone())
print("  same but symbol LIKE 'BJ%' (prefix rule):",
  c.execute(BASE % ("COUNT(*), COUNT(DISTINCT symbol)", "AND symbol LIKE 'BJ%' AND abs(close/pc-1.0)>0.30")).fetchone())

print("\n=== threshold grid: what board-limit rule reproduces THEIR 430 / 274 symbols? ===")
print(f"{'rule':46s} {'events':>8s} {'symbols':>8s}")
def cnt(expr):
    return c.execute(BASE % ("COUNT(*), COUNT(DISTINCT symbol)", "AND "+expr)).fetchone()
r = ("(i.board IN ('sh_main','sz_main') AND abs(close/pc-1.0)>%s) OR "
     "(i.board IN ('chi_next','star') AND abs(close/pc-1.0)>%s) OR "
     "(i.board='beijing' AND abs(close/pc-1.0)>%s)")
for m,w,bj,lbl in [(0.10,0.20,0.30,"exact limits 10/20/30 (as they describe)"),
                   (0.11,0.21,0.31,"limits +1pp"),
                   (0.105,0.21,0.315,"limits x1.05"),
                   (0.11,0.22,0.33,"limits x1.10"),
                   (0.12,0.24,0.36,"limits x1.20"),
                   (0.15,0.30,0.45,"limits x1.50"),
                   (0.11,0.11,0.11,"flat 0.11 (no board rule)")]:
    e,s=cnt(r % (m,w,bj)); print(f"{lbl:46s} {e:8d} {s:8d}")

print("\n=== BJ over-limit events: are they consecutive-session and second-sourceable? ===")
q=BASE % ("symbol,trade_date,close,pc,source", "AND i.board='beijing' AND abs(close/pc-1.0)>0.30")
rows=c.execute(q).fetchall()
print("  total BJ over-30% events:", len(rows), " distinct symbols:", len(set(r[0] for r in rows)))
print("  sources:", dict(collections.Counter(r[4] for r in rows)))
absent=present=0
for sym,d,cl,pc,src in rows:
    if c.execute("SELECT 1 FROM mh.daily_bars WHERE symbol=? AND trade_date=?",(sym,d)).fetchone(): present+=1
    else: absent+=1
print(f"  of these, absent from market_history: {absent}  present: {present}")
print("\n=== BJ coverage: mh vs cache, by month ===")
cm=dict(c.execute("""SELECT substr(trade_date,1,7),COUNT(*) FROM daily_bar_cache WHERE symbol LIKE 'BJ%'
   AND length(trade_date)=10 GROUP BY 1"""))
mm=dict(c.execute("""SELECT substr(trade_date,1,7),COUNT(*) FROM mh.daily_bars WHERE symbol LIKE 'BJ%' GROUP BY 1"""))
for k in sorted(set(cm)|set(mm)):
    print(f"   {k}  cache={cm.get(k,0):6d}  mh={mm.get(k,0):6d}")
