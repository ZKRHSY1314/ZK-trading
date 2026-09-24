import sqlite3

OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"


def ro(p):
    c = sqlite3.connect("file:" + p + "?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


op = ro(OP)
mh = ro(MH)


def show(title, sql, conn=None, cap=40):
    conn = conn or op
    print("\n### " + title)
    print("SQL: " + " ".join(sql.split()))
    try:
        rows = conn.execute(sql).fetchall()
    except Exception as e:
        print("  ERROR:", e)
        return []
    for r in rows[:cap]:
        print("   ", dict(r))
    if len(rows) > cap:
        print("    ... %d rows total" % len(rows))
    return rows


show("K0 daily_equity schema", "SELECT sql FROM sqlite_master WHERE name='historical_backtest_daily_equity'")

show("K1 equity variation across all 6915 rows (is P&L flat?)",
     """SELECT COUNT(*) AS rows_, COUNT(DISTINCT total_equity) AS distinct_equity,
               MIN(total_equity) AS mn, MAX(total_equity) AS mx,
               COUNT(DISTINCT cash) AS distinct_cash
        FROM historical_backtest_daily_equity""")

show("K2 admitted symbols with NO exchange prefix (bare 6-digit codes)",
     """SELECT symbol, COUNT(*) AS rows_, MIN(trade_date) AS mn, MAX(trade_date) AS mx, source
        FROM daily_bar_cache
        WHERE quality_status='ready'
          AND upper(symbol) NOT LIKE 'SH%' AND upper(symbol) NOT LIKE 'SZ%'
          AND upper(symbol) NOT LIKE 'BJ%'
        GROUP BY symbol""")

show("K3 ingest_runs schema in market_history (find the provenance column)",
     "SELECT sql FROM sqlite_master WHERE name='ingest_runs'", conn=mh)

show("K4 market_history universe provenance",
     "SELECT * FROM ingest_runs ORDER BY id DESC LIMIT 3", conn=mh)

show("K5 does trading_local contain a daily_bars table at all?",
     "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%daily_bar%'")

show("K6 does market_history contain a daily_bar_cache table at all?",
     "SELECT name FROM sqlite_master WHERE type='table'", conn=mh)
