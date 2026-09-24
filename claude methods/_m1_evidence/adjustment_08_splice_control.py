import sqlite3, sys, json, statistics
sys.stdout.reconfigure(encoding='utf-8')
OUT=r"D:/codex-A股交易/claude methods/_m1_evidence"
ev=json.load(open(OUT+"/adjustment_03_events.json",encoding="utf-8"))
spl=set(b[0] for b in ev["boundaries"] if b[2]=='2024-08-13')
con=sqlite3.connect("file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True)
con.execute("PRAGMA query_only=ON")
sql=("SELECT symbol, trade_date, close, LAG(close) OVER (PARTITION BY symbol ORDER BY trade_date) AS pc "
     "FROM daily_bar_cache WHERE trade_date IN ('2024-08-12','2024-08-13') AND quality_status='ready' "
     "AND symbol NOT LIKE 'SH00%'")
print("SQL:"," ".join(sql.split()))
a=[];b=[]
for s,d,c,pc in con.execute(sql):
    if d=='2024-08-13' and c and pc and pc>0:
        (a if s in spl else b).append(c/pc-1.0)
def st(x): return dict(n=len(x),mean=round(statistics.mean(x),5),median=round(statistics.median(x),5),
                       pct_up=round(sum(1 for v in x if v>0)/len(x),4))
print("  SPLICED on 2024-08-13 (source changed):    ",st(a))
print("  NOT spliced on 2024-08-13 (control):       ",st(b))
print("  contamination = mean(spliced)-mean(control) = %+.5f"%(statistics.mean(a)-statistics.mean(b)))
con.close()
