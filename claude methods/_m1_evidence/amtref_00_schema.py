import sqlite3
H=r"D:/codex-A股交易/market_history.sqlite3"
C=r"D:/codex-A股交易/trading_local.sqlite3"
for name,p in (("HIST",H),("CACHE",C)):
    con=sqlite3.connect(f"file:{p}?mode=ro",uri=True)
    print("="*20,name)
    for t in ("daily_bars","daily_bar_cache","instruments"):
        r=con.execute("SELECT sql FROM sqlite_master WHERE name=?",(t,)).fetchone()
        if r: print("---",t,"\n",r[0][:2500])
    con.close()
