import sqlite3, json, os, sys
ROOT = r"D:\codex-A股交易"
DBS = {
    "trading_local": os.path.join(ROOT, "trading_local.sqlite3"),
    "market_history": os.path.join(ROOT, "market_history.sqlite3"),
}
def ro(p):
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

for name, path in DBS.items():
    print("="*90)
    print(f"DB {name}  path={path}  size_bytes={os.path.getsize(path):,}")
    c = ro(path)
    pc = c.execute("PRAGMA page_count").fetchone()[0]
    ps = c.execute("PRAGMA page_size").fetchone()[0]
    fl = c.execute("PRAGMA freelist_count").fetchone()[0]
    print(f"page_count={pc:,} page_size={ps} freelist={fl:,} pages_bytes={pc*ps:,}")
    rows = c.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','index') ORDER BY type, name").fetchall()
    tables = [r[0] for r in rows if r[1]=='table']
    print(f"tables={len(tables)}")
    for t in tables:
        try:
            n = c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        except Exception as e:
            n = f"ERR {e}"
        print(f"  {t:50s} {n}")
    c.close()
