import sqlite3,sys
sys.stdout.reconfigure(encoding='utf-8')
c=sqlite3.connect("file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True)
for lbl,sql in [
 ("historical_backtest_runs created_at range","SELECT MIN(created_at),MAX(created_at),COUNT(*) FROM historical_backtest_runs"),
 ("backtest start/end span","SELECT MIN(start_date),MAX(end_date),COUNT(DISTINCT data_source) FROM historical_backtest_runs"),
 ("data_source used","SELECT data_source,COUNT(*) FROM historical_backtest_runs GROUP BY data_source"),
 ("daily_bar_cache MIN created_at","SELECT MIN(created_at) FROM daily_bar_cache"),
 ("backtest runs created BEFORE the oldest bar row now in the cache",
  "SELECT COUNT(*) FROM historical_backtest_runs WHERE created_at < (SELECT MIN(created_at) FROM daily_bar_cache)"),
 ("daily equity rows","SELECT COUNT(*) FROM historical_backtest_daily_equity"),
 ("backtest trades","SELECT COUNT(*) FROM historical_backtest_trades"),
]:
    print(f"{lbl}: {c.execute(sql).fetchall()}\n   |SQL| {sql}")
c.close()
