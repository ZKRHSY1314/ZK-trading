import sqlite3, os, hashlib
CACHE = r"D:/codex-A股交易/trading_local.sqlite3"
HIST  = r"D:/codex-A股交易/market_history.sqlite3"
for p in (CACHE, HIST):
    st = os.stat(p)
    h = hashlib.sha256()
    with open(p,'rb') as f:
        h.update(f.read(1_000_000))
    print(f"{p}\n  size={st.st_size:,}  first1MB_sha256={h.hexdigest()[:24]}")
print("SAME FILE?" , os.path.samefile(CACHE, HIST))

c = sqlite3.connect(f"file:{HIST}?mode=ro", uri=True)
c.execute("PRAGMA query_only=ON")
c.execute(f"ATTACH DATABASE 'file:{CACHE}?mode=ro' AS cache")
print("\n-- identity of attached schemas --")
for row in c.execute("PRAGMA database_list"):
    print("  ", row)
print("\nmain.daily_bars rows      =", c.execute("SELECT COUNT(*) FROM main.daily_bars").fetchone()[0])
print("cache.daily_bar_cache rows=", c.execute("SELECT COUNT(*) FROM cache.daily_bar_cache").fetchone()[0])
print("\n-- sample symbols each side --")
print(" hist :", [r[0] for r in c.execute("SELECT DISTINCT symbol FROM main.daily_bars LIMIT 6")])
print(" cache:", [r[0] for r in c.execute("SELECT DISTINCT symbol FROM cache.daily_bar_cache LIMIT 6")])
print("\n-- main.daily_bars DDL --")
print(c.execute("SELECT sql FROM main.sqlite_master WHERE name='daily_bars'").fetchone()[0])
print("\n-- cache.daily_bar_cache DDL --")
print(c.execute("SELECT sql FROM cache.sqlite_master WHERE name='daily_bar_cache'").fetchone()[0])
