import sqlite3
OP = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True); c.row_factory = sqlite3.Row; return c
op = ro(OP)
def q(sql, params=()):
    print("="*100); print("SQL:", " ".join(sql.split()))
    rows = op.execute(sql, params).fetchall()
    for r in rows: print("   ", dict(r))
    print(f"   [{len(rows)} rows]"); return rows

# A. What is the PREVIOUS bar before 2024-11-06 for each of the 3 symbols? (suspension gap size)
for s in ('SH688089','SH688143','SH688173'):
    q("""SELECT symbol, trade_date, open, high, low, close, volume FROM daily_bar_cache
         WHERE symbol=? AND trade_date < '2024-11-06' AND quality_status='ready'
         ORDER BY trade_date DESC LIMIT 3""", (s,))
    q("""SELECT symbol, trade_date, open, high, low, close, volume FROM daily_bar_cache
         WHERE symbol=? AND trade_date > '2024-11-06' AND quality_status='ready'
         ORDER BY trade_date ASC LIMIT 3""", (s,))

# B. Is 2024-11-06 a real trading day at all? how many symbols have a bar that day
q("""SELECT trade_date, COUNT(*) n, COUNT(DISTINCT symbol) syms FROM daily_bar_cache
     WHERE trade_date BETWEEN '2024-11-01' AND '2024-11-11' GROUP BY trade_date ORDER BY trade_date""")

# C. Existing backtest runs: do any of them SPAN 2024-11-06, and did they complete?
q("""SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'historical_backtest%'""")
q("""SELECT id, status, start_date, end_date, created_at FROM historical_backtest_runs
     ORDER BY id DESC LIMIT 45""")

# D. Did any run's daily equity actually contain 2024-11-06?
q("""SELECT COUNT(*) rows_on_date, COUNT(DISTINCT run_id) runs_on_date
     FROM historical_backtest_daily_equity WHERE trade_date='2024-11-06'""")
q("""SELECT run_id, MIN(trade_date) mn, MAX(trade_date) mx, COUNT(*) n
     FROM historical_backtest_daily_equity GROUP BY run_id
     HAVING mn <= '2024-11-06' AND mx >= '2024-11-06' ORDER BY run_id DESC LIMIT 20""")

# E. total trades / fills ever recorded
q("""SELECT (SELECT COUNT(*) FROM historical_backtest_trades) trades,
            (SELECT COUNT(*) FROM historical_backtest_closed_trades) closed""")
