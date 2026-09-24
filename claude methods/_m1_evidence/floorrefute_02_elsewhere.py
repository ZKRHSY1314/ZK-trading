# -*- coding: utf-8 -*-
import sqlite3
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
def show(c, sql, title):
    print("-"*88); print(title); print("SQL:", " ".join(sql.split()))
    try:
        cur = c.execute(sql); hdr=[d[0] for d in cur.description]; rows=cur.fetchall()
        print("  " + " | ".join(hdr))
        for r in rows[:40]: print("  " + " | ".join("NULL" if v is None else str(v) for v in r))
        if len(rows)>40: print(f"  ... {len(rows)-40} more")
    except Exception as e: print("  ERROR:", e)
tl=ro(TL); mh=ro(MH)

print("#"*88); print("# A: does ANY other price/equity table in trading_local reach before 2024-04-09?")
for tbl,col in [("global_market_bars","bar_time"),("historical_backtest_daily_equity","trade_date"),
                ("full_market_feature_state","trade_date"),("capital_flow_snapshots","trade_date"),
                ("sector_membership_snapshots","effective_date"),("trade_records","trade_date"),
                ("trade_cases","trade_date"),("dataset2_staging_records","signal_date"),
                ("disclosure_facts","period_end"),("stock_profiles","launch_date")]:
    show(tl, f"""SELECT '{tbl}' AS tbl, COUNT(*) AS n, MIN(CAST({col} AS TEXT)) AS lo,
                 MAX(CAST({col} AS TEXT)) AS hi,
                 SUM(CASE WHEN CAST(substr(CAST({col} AS TEXT),1,4) AS INTEGER) BETWEEN 2000 AND 2024 THEN 1 ELSE 0 END) AS n_le2024
                 FROM {tbl}""", f"A.{tbl}.{col}")
show(mh, """SELECT COUNT(*) AS n, MIN(snapshot_date) AS lo, MAX(snapshot_date) AS hi FROM universe_snapshots""",
     "A.market_history.universe_snapshots")

print()
print("#"*88); print("# B: does the BACKTEST claim to run over the missing period? (is the gap consequential)")
show(tl, """SELECT COUNT(*) AS runs, MIN(CAST(start_date AS TEXT)) AS earliest_start,
            MAX(CAST(end_date AS TEXT)) AS latest_end,
            SUM(CASE WHEN CAST(start_date AS TEXT) < '2024-04-09' THEN 1 ELSE 0 END) AS runs_starting_before_data_floor
            FROM historical_backtest_runs""", "B1 historical_backtest_runs vs the 2024-04-09 floor")
show(tl, """SELECT CAST(start_date AS TEXT) AS start_date, CAST(end_date AS TEXT) AS end_date, COUNT(*) AS runs
            FROM historical_backtest_runs GROUP BY 1,2 ORDER BY 1""", "B2 distinct backtest windows requested")
show(tl, """SELECT MIN(CAST(trade_date AS TEXT)) AS lo, MAX(CAST(trade_date AS TEXT)) AS hi,
            COUNT(*) AS n, COUNT(DISTINCT CAST(trade_date AS TEXT)) AS sessions
            FROM historical_backtest_daily_equity""", "B3 equity curve actual dates produced")

print()
print("#"*88); print("# C: are the 13 symbols alive on 2024-04-09 stocks or indices? (do NOT count indices as stocks)")
show(tl, """SELECT symbol, CAST(trade_date AS TEXT) AS td, source FROM daily_bar_cache
            WHERE CAST(trade_date AS TEXT) < '2024-05-01' ORDER BY td, symbol LIMIT 40""",
     "C1 the earliest rows in daily_bar_cache")
show(mh, """SELECT exchange, asset_type, COUNT(*) AS n FROM instruments GROUP BY 1,2 ORDER BY 3 DESC""",
     "C2 instruments breakdown (INDEX vs stock)")

print()
print("#"*88); print("# D: independent session-count + window arithmetic, integer-keyed, no string compare")
show(tl, """SELECT COUNT(DISTINCT CAST(trade_date AS TEXT)) AS sessions_all,
            SUM(CASE WHEN CAST(replace(CAST(trade_date AS TEXT),'-','') AS INTEGER)
                     BETWEEN 20230904 AND 20260904 THEN 1 ELSE 0 END) AS rows_in_window,
            SUM(CASE WHEN CAST(replace(CAST(trade_date AS TEXT),'-','') AS INTEGER)
                     BETWEEN 20230904 AND 20240408 THEN 1 ELSE 0 END) AS rows_first7months,
            SUM(CASE WHEN CAST(replace(CAST(trade_date AS TEXT),'-','') AS INTEGER)
                     < 20230904 AND CAST(replace(CAST(trade_date AS TEXT),'-','') AS INTEGER) > 19000000
                     THEN 1 ELSE 0 END) AS rows_warmup_pre_window
            FROM daily_bar_cache""", "D1 integer-date window arithmetic on daily_bar_cache")
show(mh, """SELECT COUNT(DISTINCT trade_date) AS sessions_all,
            SUM(CASE WHEN CAST(replace(trade_date,'-','') AS INTEGER) BETWEEN 20230904 AND 20240408 THEN 1 ELSE 0 END) AS rows_first7months,
            SUM(CASE WHEN CAST(replace(trade_date,'-','') AS INTEGER) < 20230904 THEN 1 ELSE 0 END) AS rows_warmup_pre_window
            FROM daily_bars""", "D2 integer-date window arithmetic on daily_bars")
tl.close(); mh.close()
