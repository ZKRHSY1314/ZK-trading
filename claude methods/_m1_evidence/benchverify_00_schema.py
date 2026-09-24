import sqlite3, json
OP=r"D:\codex-A股交易\trading_local.sqlite3"
MH=r"D:\codex-A股交易\market_history.sqlite3"
def ro(p):
    return sqlite3.connect(f"file:{p.replace(chr(92),'/')}?mode=ro", uri=True)
for label,p in (("trading_local",OP),("market_history",MH)):
    c=ro(p)
    print("="*70); print(label)
    rows=c.execute("SELECT name,type FROM sqlite_master WHERE type IN ('table','view') ORDER BY name").fetchall()
    for n,t in rows:
        if any(k in n.lower() for k in ("backtest","bt_","simul","equity","trade","fill","position","bench","index","replay","walk","strategy","run")):
            try:
                cnt=c.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0]
            except Exception as e:
                cnt=f"ERR {e}"
            print(f"  {t:5s} {n:55s} {cnt}")
    c.close()
