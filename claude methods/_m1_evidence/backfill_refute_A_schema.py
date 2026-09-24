import sqlite3, json
MH = r"D:\codex-A股交易\market_history.sqlite3"
TL = r"D:\codex-A股交易\trading_local.sqlite3"

def ro(p):
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

c = ro(MH)
print("=== market_history.daily_bars schema ===")
for r in c.execute("SELECT sql FROM sqlite_master WHERE name='daily_bars'"):
    print(r[0])
print()
print("=== indexes on daily_bars ===")
for r in c.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='daily_bars'"):
    print(r)
print()
print("=== instruments schema ===")
for r in c.execute("SELECT sql FROM sqlite_master WHERE name='instruments'"):
    print(r[0])
c.close()

c = ro(TL)
print()
print("=== trading_local.daily_bar_cache schema ===")
for r in c.execute("SELECT sql FROM sqlite_master WHERE name='daily_bar_cache'"):
    print(r[0])
print()
print("=== indexes on daily_bar_cache ===")
for r in c.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='daily_bar_cache'"):
    print(r)
c.close()
