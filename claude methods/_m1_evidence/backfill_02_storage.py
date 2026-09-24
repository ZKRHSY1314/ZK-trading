import sqlite3, os
ROOT = r"D:\codex-A股交易"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

for name, path, tables in [
    ("trading_local", os.path.join(ROOT,"trading_local.sqlite3"), ["daily_bar_cache"]),
    ("market_history", os.path.join(ROOT,"market_history.sqlite3"), ["daily_bars","instruments","universe_members"]),
]:
    c = ro(path)
    print("="*80); print(name, f"file={os.path.getsize(path):,}")
    try:
        rows = c.execute("SELECT name, SUM(pgsize) AS bytes, COUNT(*) AS pages FROM dbstat GROUP BY name ORDER BY bytes DESC").fetchall()
        print("dbstat available. per-object bytes:")
        for r in rows:
            print(f"  {r[0]:55s} {r[1]:>14,} bytes  {r[2]:>9,} pages")
    except Exception as e:
        print("dbstat unavailable:", e)
    for t in tables:
        n = c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        print(f"  rowcount {t} = {n:,}")
    c.close()
