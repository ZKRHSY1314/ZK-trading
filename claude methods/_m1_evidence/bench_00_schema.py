import sqlite3, re
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"

def ro(p):
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

for label, path in (("market_history", MH), ("trading_local", TL)):
    c = ro(path)
    print("="*70)
    print(label)
    print("="*70)
    rows = c.execute("SELECT type,name,sql FROM sqlite_master WHERE type IN ('table','view') ORDER BY name").fetchall()
    for t,n,s in rows:
        if n.startswith("sqlite_"): continue
        # flag anything that smells like index/benchmark/reference
        hit = bool(re.search(r"index|bench|idx|reference|market_ref|sector|industry|univ", n, re.I))
        try:
            cnt = c.execute(f"SELECT COUNT(*) FROM \"{n}\"").fetchone()[0]
        except Exception as e:
            cnt = f"ERR {e}"
        print(f"{'>>' if hit else '  '} {t:5s} {n:45s} rows={cnt}")
    c.close()
