import sqlite3, json
OP = r"D:/codex-A股交易/trading_local.sqlite3"
con = sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
c = con.cursor()
for t in ("historical_backtest_runs","symbol_fundamental_snapshot","historical_backtest_daily_equity","historical_backtest_trades"):
    r = c.execute("SELECT sql FROM sqlite_master WHERE name=?", (t,)).fetchone()
    print("=== ", t, " ===")
    print(r["sql"] if r else "MISSING")
print("=== tables like fundamental/backtest ===")
for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%fundamental%' OR name LIKE '%backtest%')"):
    print(" ", r["name"], c.execute(f"SELECT COUNT(*) FROM {r['name']}").fetchone()[0])
con.close()
