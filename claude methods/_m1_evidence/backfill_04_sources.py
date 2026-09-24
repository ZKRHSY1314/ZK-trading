import sqlite3, os, json
ROOT = r"D:\codex-A股交易"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
tl = ro(os.path.join(ROOT,"trading_local.sqlite3")); tl.row_factory=sqlite3.Row
mh = ro(os.path.join(ROOT,"market_history.sqlite3")); mh.row_factory=sqlite3.Row

def q(c, sql, params=()):
    print("SQL:", " ".join(sql.split()))
    for r in c.execute(sql, params).fetchall():
        print("   ", dict(r))
    print()

print("########## trading_local.daily_bar_cache ##########")
q(tl, """SELECT source, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS symbols,
                MIN(trade_date) AS min_d, MAX(trade_date) AS max_d,
                SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) AS amount_null,
                SUM(CASE WHEN volume IS NULL THEN 1 ELSE 0 END) AS volume_null
         FROM daily_bar_cache GROUP BY source ORDER BY rows DESC""")
q(tl, """SELECT adjustment_mode, volume_unit, quality_status, COUNT(*) AS rows
         FROM daily_bar_cache GROUP BY adjustment_mode, volume_unit, quality_status ORDER BY rows DESC""")
q(tl, """SELECT COUNT(*) AS rows_in_window FROM daily_bar_cache
         WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'""")
q(tl, """SELECT COUNT(*) AS rows_before_window FROM daily_bar_cache
         WHERE trade_date < '2023-09-04' AND length(trade_date)=10""")
q(tl, """SELECT COUNT(*) AS bad_date_rows FROM daily_bar_cache WHERE length(trade_date) <> 10""")
q(tl, """SELECT source, COUNT(*) AS rows_in_window FROM daily_bar_cache
         WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04' GROUP BY source ORDER BY rows_in_window DESC""")
q(tl, """SELECT COUNT(DISTINCT trade_date) AS distinct_sessions_in_window FROM daily_bar_cache
         WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04' AND length(trade_date)=10""")
q(tl, """SELECT COUNT(DISTINCT symbol) AS symbols_total FROM daily_bar_cache""")

print("########## per-symbol window depth histogram (stocks only, non-index) ##########")
q(tl, """WITH per AS (
           SELECT symbol, COUNT(*) AS n FROM daily_bar_cache
           WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04' AND length(trade_date)=10
           GROUP BY symbol)
         SELECT CASE WHEN n>=700 THEN 'a >=700'
                     WHEN n>=600 THEN 'b 600-699'
                     WHEN n>=500 THEN 'c 500-599'
                     WHEN n>=300 THEN 'd 300-499'
                     WHEN n>=100 THEN 'e 100-299'
                     ELSE 'f <100' END AS bucket,
                COUNT(*) AS symbols, SUM(n) AS rows
         FROM per GROUP BY bucket ORDER BY bucket""")

print("########## market_history.daily_bars ##########")
q(mh, """SELECT provider, adjustment_mode, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS symbols,
                MIN(trade_date) AS min_d, MAX(trade_date) AS max_d
         FROM daily_bars GROUP BY provider, adjustment_mode ORDER BY rows DESC""")
q(mh, """SELECT COUNT(*) AS rows_in_window FROM daily_bars
         WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'""")
q(mh, """SELECT COUNT(DISTINCT provider) AS distinct_providers FROM daily_bars""")
q(mh, """SELECT provider, COUNT(*) AS runs, SUM(inserted_row_count) AS inserted, SUM(updated_row_count) AS updated,
                SUM(processed_symbol_count) AS processed
         FROM ingest_runs GROUP BY provider""")
q(mh, """SELECT status, COUNT(*) AS runs FROM ingest_runs GROUP BY status""")
q(mh, """SELECT MIN(created_at) AS first_run, MAX(created_at) AS last_run FROM ingest_runs""")
