import sqlite3, os
OP = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"

def ro(p):
    return sqlite3.connect("file:" + p.replace("\\","/") + "?mode=ro", uri=True)

for name, p in (("trading_local", OP), ("market_history", MH)):
    c = ro(p)
    print("="*70)
    print(name, os.path.getsize(p))
    rows = c.execute("SELECT type,name FROM sqlite_master WHERE type IN ('table','view') ORDER BY type,name").fetchall()
    print("N objects:", len(rows))
    for t,n in rows:
        print("  ",t,n)
    c.close()

print("="*70)
print("DDL market_history.daily_bars")
c = ro(MH)
print(c.execute("SELECT sql FROM sqlite_master WHERE name='daily_bars'").fetchone()[0])
print("-- indexes --")
for (s,) in c.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='daily_bars' AND sql IS NOT NULL"):
    print(s)
c.close()

print("="*70)
print("DDL trading_local.daily_bar_cache")
c = ro(OP)
print(c.execute("SELECT sql FROM sqlite_master WHERE name='daily_bar_cache'").fetchone()[0])
c.close()
