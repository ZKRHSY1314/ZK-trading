import sqlite3
OP=r"D:/codex-A股交易/trading_local.sqlite3"
MH=r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
c=ro(OP)
print("=== daily_bar_cache DDL ===")
for (s,) in c.execute("SELECT sql FROM sqlite_master WHERE tbl_name='daily_bar_cache'"):
    print(s)
print("\n=== forecast_decisions DDL ===")
for (s,) in c.execute("SELECT sql FROM sqlite_master WHERE tbl_name='forecast_decisions'"):
    print(s)
print("\n=== tables matching forecast/decision ===")
for (n,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%forecast%' OR name LIKE '%decision%') ORDER BY name"):
    print(" ",n)
c.close()
