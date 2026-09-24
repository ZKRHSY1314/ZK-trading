import sqlite3, json, statistics
cal=json.load(open(r"D:/codex-A股交易/backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json",encoding="utf-8"))
cal=sorted({f"{d[0:4]}-{d[4:6]}-{d[6:8]}" for d in cal})
W0,W1="2023-09-04","2026-09-04"
win=[d for d in cal if W0<=d<=W1]
print("true window sessions:",len(win))
def ro(p):
    c=sqlite3.connect(f"file:{p}?mode=ro",uri=True); c.execute("PRAGMA query_only=1"); return c
tl=ro(r"D:/codex-A股交易/trading_local.sqlite3"); mh=ro(r"D:/codex-A股交易/market_history.sqlite3")
inst={s:(ld or "") for s,ld in mh.execute("SELECT symbol,list_date FROM instruments WHERE exchange IN ('SH','SZ','BJ')")}
obs={}
for s,n in tl.execute("""SELECT symbol, COUNT(DISTINCT trade_date) FROM daily_bar_cache
     WHERE length(trade_date)=10 AND quality_status='ready' AND adjustment_mode='qfq'
       AND trade_date BETWEEN ? AND ? GROUP BY 1""",(W0,W1)):
    obs[s]=n
import bisect
rows=[]
for s,ld in inst.items():
    if not ld: continue
    start=max(ld,W0)
    elig=len(win)-bisect.bisect_left(win,start)
    if elig<=0: continue
    rows.append((s,elig,obs.get(s,0),obs.get(s,0)/elig))
ratios=sorted(r[3] for r in rows)
print("securities with a computable calendar denominator:",len(rows))
print("coverage vs TRUE eligible sessions -> median %.4f  mean %.4f  max %.4f"%(
    statistics.median(ratios), sum(ratios)/len(ratios), max(ratios)))
for thr in (0.99,0.95,0.90,0.80,0.75):
    print(f"   >= {thr}: {sum(1 for r in ratios if r>=thr)}")
pre=[r for r in rows if inst[r[0]]<=W0]
print("listed on/before window start:",len(pre),
      " max coverage %.4f"%max(r[3] for r in pre), " >=0.95:",sum(1 for r in pre if r[3]>=0.95))
print("\nreport's head-gap backfill estimate uses 146 sessions; true = %d -> G-A rows = 5167*%d = %d (report: 754,382)"%(
   sum(1 for d in win if d<='2024-04-08'), sum(1 for d in win if d<='2024-04-08'), 5167*sum(1 for d in win if d<='2024-04-08')))
print("full-market gap 2023-09-04..2024-06-21 = %d sessions (report estimated ~196)"%sum(1 for d in win if d<='2024-06-21'))
