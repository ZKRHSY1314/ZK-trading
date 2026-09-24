import sqlite3, json, statistics
from collections import defaultdict
OP=r"D:/codex-A股交易/trading_local.sqlite3"
c=sqlite3.connect(f"file:{OP}?mode=ro",uri=True)
B=json.load(open(r"D:/codex-A股交易/claude methods/_m1_evidence/adjrefute_boundaries.json"))["boundaries"]
bset={(b[0],b[2]) for b in B}
def pctl(v,p):
    s=sorted(v); return s[min(len(s)-1,int(round(p/100*(len(s)-1))))]
# For the top boundary dates, compare boundary vs non-boundary symbols ON THAT SAME DATE
targets=['2024-08-13','2026-07-27','2026-07-24','2026-09-04','2024-07-30','2024-08-12']
print("### per-date: |ret| of symbols WITH a source change vs symbols WITHOUT, same day", flush=True)
print(f"{'date':12s} {'nBnd':>6s} {'nOther':>7s} | {'bnd p50':>8s} {'oth p50':>8s} | {'bnd>2%':>7s} {'oth>2%':>7s} | {'bnd>5%':>7s} {'oth>5%':>7s}", flush=True)
for d in targets:
    rows=c.execute("""
      SELECT a.symbol, a.close, b.close FROM daily_bar_cache a
      JOIN daily_bar_cache b ON b.symbol=a.symbol AND b.trade_date=(
         SELECT MAX(trade_date) FROM daily_bar_cache x WHERE x.symbol=a.symbol AND x.trade_date<a.trade_date)
      WHERE a.trade_date=?""",(d,)).fetchall()
    bn=[];ot=[]
    for sym,cl,pc in rows:
        if not cl or not pc or pc<=0: continue
        r=abs(cl/pc-1.0)
        (bn if (sym,d) in bset else ot).append(r)
    if not bn or not ot: 
        print(f"{d:12s} insufficient", flush=True); continue
    print(f"{d:12s} {len(bn):6d} {len(ot):7d} | {pctl(bn,50)*100:7.2f}% {pctl(ot,50)*100:7.2f}% |"
          f" {sum(1 for x in bn if x>.02)/len(bn)*100:6.1f}% {sum(1 for x in ot if x>.02)/len(ot)*100:6.1f}% |"
          f" {sum(1 for x in bn if x>.05)/len(bn)*100:6.1f}% {sum(1 for x in ot if x>.05)/len(ot)*100:6.1f}%", flush=True)
print("\n### is 2024-08-13 a one-off cutover? rows written per source per trade_date around it", flush=True)
for r in c.execute("""SELECT trade_date, source, COUNT(*) FROM daily_bar_cache
 WHERE trade_date BETWEEN '2024-08-08' AND '2024-08-16' GROUP BY 1,2 ORDER BY 1,3 DESC"""):
    print("  ",r, flush=True)
