import sqlite3
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
def show(con,t,sql,p=()):
    print("="*78); print(t); print("SQL:", " ".join(sql.split()))
    try:
        for r in con.execute(sql,p).fetchall(): print("   ", dict(r))
    except Exception as e: print("   ERR:", e)

mh = sqlite3.connect(f"file:{MH}?mode=ro", uri=True); mh.row_factory = sqlite3.Row
tl = sqlite3.connect(f"file:{TL}?mode=ro", uri=True); tl.row_factory = sqlite3.Row

# 1. Do universe_snapshots offer an independent as-of path?
show(mh,"1 universe_snapshots -- are they real historical vintages?", """
SELECT id, universe_name, snapshot_date, substr(created_at,1,19) AS created_at
FROM universe_snapshots ORDER BY snapshot_date""")

# 2. Does created_at in daily_bars differ from available_at (a second vintage signal)?
show(mh,"2 daily_bars.created_at -- independent vintage signal?", """
SELECT COUNT(DISTINCT substr(created_at,1,10)) AS distinct_created_days,
       MIN(created_at) AS min_created, MAX(created_at) AS max_created,
       SUM(CASE WHEN substr(created_at,1,10) <= date(trade_date,'+30 day') THEN 1 ELSE 0 END) AS created_within_30d,
       COUNT(*) AS total
FROM daily_bars""")

# 3. Fallback: does the UPSTREAM trading_local.daily_bar_cache carry a usable vintage?
show(tl,"3 trading_local.daily_bar_cache.created_at -- upstream vintage (the store that FEEDS the backtest)", """
SELECT COUNT(DISTINCT substr(created_at,1,10)) AS distinct_created_days,
       MIN(created_at) AS min_created, MAX(created_at) AS max_created,
       SUM(CASE WHEN substr(created_at,1,10) <= date(trade_date,'+30 day') THEN 1 ELSE 0 END) AS created_within_30d,
       COUNT(*) AS total
FROM daily_bar_cache""")

show(tl,"3b upstream created_at day histogram (top 10)", """
SELECT substr(created_at,1,10) AS d, COUNT(*) AS n FROM daily_bar_cache
GROUP BY d ORDER BY n DESC LIMIT 10""")

# 4. ingest_runs -- could run timestamps rebuild vintages?
show(mh,"4 ingest_runs date span -- earliest possible vintage anchor", """
SELECT COUNT(*) AS runs, MIN(created_at) AS first_run, MAX(created_at) AS last_run,
       COUNT(DISTINCT substr(created_at,1,10)) AS distinct_run_days
FROM ingest_runs""")
mh.close(); tl.close()
