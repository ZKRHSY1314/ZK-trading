import sqlite3, json
OP=r"D:/codex-A股交易/trading_local.sqlite3"
c=sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
c.row_factory=sqlite3.Row
def sql(q,p=()):
    return c.execute(q,p).fetchall()
def show(t):
    print("-- schema", t)
    print(c.execute("SELECT sql FROM sqlite_master WHERE name=?",(t,)).fetchone()[0])
for t in ("historical_backtest_runs","historical_backtest_daily_equity","historical_backtest_trades","historical_backtest_closed_trades","learning_backtests"):
    show(t); print()
