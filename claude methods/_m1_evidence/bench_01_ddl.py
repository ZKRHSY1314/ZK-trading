import sqlite3
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

c = ro(MH)
for n in ("instruments","daily_bars","universe_snapshots","universe_members","schema_metadata"):
    print("-"*70); print(c.execute("SELECT sql FROM sqlite_master WHERE name=?", (n,)).fetchone()[0])
print("\nschema_metadata contents:")
for r in c.execute("SELECT * FROM schema_metadata").fetchall(): print("   ", r)
c.close()

t = ro(TL)
for n in ("global_market_bars","daily_bar_cache"):
    print("-"*70); print(t.execute("SELECT sql FROM sqlite_master WHERE name=?", (n,)).fetchone()[0])
t.close()
