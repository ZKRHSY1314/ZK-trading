import sqlite3
MH=r"D:/codex-A股交易/market_history.sqlite3"
TL=r"D:/codex-A股交易/trading_local.sqlite3"
for lbl,p in (("MARKET_HISTORY",MH),("TRADING_LOCAL",TL)):
    c=sqlite3.connect(f"file:{p}?mode=ro",uri=True)
    print("="*70); print(lbl)
    for (n,t,s) in c.execute("SELECT name,type,sql FROM sqlite_master WHERE type IN ('table','view') ORDER BY name"):
        print("-",t,n)
    c.close()
