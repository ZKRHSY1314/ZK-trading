import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
for label, path in (("trading_local", OP), ("market_history", MH)):
    c = ro(path)
    print("="*90); print(label)
    for (t,n) in c.execute("SELECT type,name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        try: cnt = c.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0]
        except Exception as e: cnt = f"ERR"
        print(f"  {t:5s} {n:45s} {cnt}")
    c.close()
