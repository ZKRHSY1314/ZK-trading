import sqlite3, os, json
ROOT = r"D:\codex-A股交易"
MH = sqlite3.connect(f"file:{os.path.join(ROOT,'market_history.sqlite3')}?mode=ro", uri=True)
TL = sqlite3.connect(f"file:{os.path.join(ROOT,'trading_local.sqlite3')}?mode=ro", uri=True)
MH.row_factory = sqlite3.Row; TL.row_factory = sqlite3.Row

print("--- ingest_runs schema")
print([r[1] for r in MH.execute("PRAGMA table_info(ingest_runs)").fetchall()])
print()

sql = """SELECT provider,
                COUNT(*) runs,
                SUM(symbol_count) symbols,
                SUM(row_count) rows,
                ROUND(SUM(julianday(finished_at)-julianday(started_at))*86400.0,1) secs
           FROM ingest_runs
          WHERE started_at IS NOT NULL AND finished_at IS NOT NULL
          GROUP BY provider ORDER BY symbols DESC"""
print("--- wall-clock throughput per provider from ingest_runs")
print("SQL: " + " ".join(sql.split()))
try:
    for r in MH.execute(sql).fetchall():
        d = dict(r)
        s = d.get("secs") or 0
        d["symbols_per_sec"] = round((d["symbols"] or 0) / s, 3) if s else None
        print("     ", d)
except sqlite3.Error as e:
    print("     ERR:", e)
    for r in MH.execute("SELECT * FROM ingest_runs LIMIT 2").fetchall():
        print("     sample:", dict(r))
print()

print("--- DECISIVE: BJ920058, the 2026-09-03 sweep reached back exactly how many sessions?")
sql2 = """SELECT COUNT(*) sessions_in_that_span
            FROM (SELECT DISTINCT trade_date FROM daily_bar_cache
                   WHERE symbol='BJ920058'
                     AND trade_date BETWEEN '2024-07-30' AND '2026-09-03')"""
print("SQL: " + " ".join(sql2.split()))
print("     ", dict(TL.execute(sql2).fetchone()))

sql3 = """SELECT COUNT(*) rows_created_on_2026_09_03, MIN(trade_date) reached_back_to,
                 MAX(trade_date) up_to
            FROM daily_bar_cache
           WHERE symbol='BJ920058' AND source='tonghuasun.local.quotes.candle'
             AND substr(created_at,1,10)='2026-09-03'"""
print("SQL: " + " ".join(sql3.split()))
print("     ", dict(TL.execute(sql3).fetchone()))
print()

print("--- Same test across ALL tonghuasun symbols touched on 2026-09-03:")
sql4 = """WITH sweep AS (
            SELECT symbol, MIN(trade_date) mn, MAX(trade_date) mx, COUNT(*) n
              FROM daily_bar_cache
             WHERE source='tonghuasun.local.quotes.candle'
             GROUP BY symbol)
          SELECT COUNT(*) symbols,
                 MIN(mn) earliest_any_symbol_reached,
                 MAX(n) deepest_symbol
            FROM sweep"""
print("SQL: " + " ".join(sql4.split()))
print("     ", dict(TL.execute(sql4).fetchone()))

sql5 = """SELECT COUNT(*) sessions_500_window
            FROM (SELECT DISTINCT trade_date FROM daily_bar_cache
                   WHERE length(trade_date)=10
                     AND trade_date BETWEEN '2024-08-14' AND '2026-09-04')"""
print("SQL: " + " ".join(sql5.split()))
print("     ", dict(TL.execute(sql5).fetchone()))
print()
print("--- Sessions BETWEEN the head-gap end and the deepest tonghuasun reach")
sql6 = """SELECT COUNT(*) unreachable_sessions_between_headgap_end_and_ths_floor
            FROM (SELECT DISTINCT trade_date FROM daily_bar_cache
                   WHERE length(trade_date)=10
                     AND trade_date > '2024-04-08' AND trade_date < '2024-07-30')"""
print("SQL: " + " ".join(sql6.split()))
print("     ", dict(TL.execute(sql6).fetchone()))
