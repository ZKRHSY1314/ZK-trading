import sqlite3, re
TL = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"

def ro(p):
    return sqlite3.connect(f"file:{p.replace(chr(92),'/')}?mode=ro", uri=True)

for label, p in (("trading_local", TL), ("market_history", MH)):
    c = ro(p)
    print("="*70)
    print(label)
    print("="*70)
    rows = c.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view') ORDER BY name").fetchall()
    names = [r[0] for r in rows]
    print(f"{len(names)} tables/views")
    # anything that smells like index / benchmark / calendar / reference
    pat = re.compile(r"index|benchmark|bench|calendar|session|trading_day|reference|ref_|constituent|component|sector|industry|board|instrument|universe|symbol|security|meta", re.I)
    hits = [n for n in names if pat.search(n)]
    print("REF-LIKE TABLES:", hits)
    for n in hits:
        try:
            cnt = c.execute(f"SELECT COUNT(*) FROM \"{n}\"").fetchone()[0]
        except Exception as e:
            cnt = f"ERR {e}"
        print(f"   {n}: {cnt}")
    print("ALL:", names)
    c.close()
