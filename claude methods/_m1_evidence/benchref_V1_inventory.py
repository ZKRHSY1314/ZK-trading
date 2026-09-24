import sqlite3, re
TL = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"

def ro(p):
    return sqlite3.connect(f"file:{p.replace(chr(92),'/')}?mode=ro", uri=True)

for label, path in (("trading_local", TL), ("market_history", MH)):
    c = ro(path)
    print("="*90)
    print(label)
    print("="*90)
    rows = c.execute("SELECT type,name,sql FROM sqlite_master WHERE type IN ('table','view') ORDER BY name").fetchall()
    for t,n,s in rows:
        if n.startswith("sqlite_"): continue
        s = s or ""
        # flag any table whose name or DDL smells of benchmark/index/calendar
        hot = bool(re.search(r"index_|benchmark|bench|calendar|session|trading_day|hs300|csi|sh000|market_index|reference", n+s, re.I))
        try:
            cnt = c.execute(f"SELECT COUNT(*) FROM \"{n}\"").fetchone()[0]
        except Exception as e:
            cnt = f"ERR {e}"
        print(f"{'*' if hot else ' '} {t:5} {n:45} rows={cnt}")
    c.close()
