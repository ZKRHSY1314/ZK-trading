import sqlite3, re
OP = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"
def ro(p): return sqlite3.connect("file:"+p.replace("\\","/")+"?mode=ro", uri=True)

PAT = re.compile(r"div|split|factor|corp|adjust|bonus|rights|allot|除权|除息|送|转增|派|复权", re.I)

for name,p in (("trading_local",OP),("market_history",MH)):
    c = ro(p)
    tbls = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    hits=[]
    for t in tbls:
        cols=[r[1] for r in c.execute(f'PRAGMA table_info("{t}")')]
        for col in cols:
            if PAT.search(col): hits.append((t,col))
        if PAT.search(t): hits.append((t,"<TABLE NAME>"))
    print("="*70); print(name, "column/table name matches for corporate-action vocabulary:", len(hits))
    for t,col in hits: print("   ", t, "::", col)
    c.close()

# Deeper: does any trading_local table hold per-symbol per-date numeric factors?
c = ro(OP)
for t in ("disclosure_facts","stock_profiles","symbol_fundamental_snapshot","events","technical_indicators"):
    try:
        cols=[r[1] for r in c.execute(f'PRAGMA table_info("{t}")')]
        n=c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        print(f"\n{t}  rows={n}\n   cols={cols}")
    except Exception as e:
        print(t, "ERR", e)
c.close()
