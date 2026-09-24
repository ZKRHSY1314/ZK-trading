import sqlite3
MH = r"D:\codex-A股交易\market_history.sqlite3"
c = sqlite3.connect("file:"+MH.replace("\\","/")+"?mode=ro", uri=True)
def q(label, sql, args=()):
    r = c.execute(sql, args).fetchall()
    print(f"\n--- {label}\nSQL: {' '.join(sql.split())}")
    for row in r[:40]: print("   ", row)
    if len(r)>40: print("    ... (%d rows)" % len(r))
    return r

q("A1 total rows / null available_at / null-or-empty",
  "SELECT COUNT(*) AS total, SUM(available_at IS NULL) AS null_avail, SUM(available_at='') AS empty_avail, SUM(fetched_at IS NULL) AS null_fetched FROM daily_bars")

q("A2 exact byte equality available_at == fetched_at",
  "SELECT SUM(available_at = fetched_at) AS identical, SUM(available_at <> fetched_at) AS differ, COUNT(*) AS total FROM daily_bars")

q("A3 distinct available_at FULL timestamp values (count + list if small)",
  "SELECT available_at, COUNT(*) FROM daily_bars GROUP BY 1 ORDER BY 1")

q("A4 distinct available_at DATE prefixes",
  "SELECT substr(available_at,1,10) AS d, COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date), MAX(trade_date) FROM daily_bars GROUP BY 1 ORDER BY 1")

q("A5 distinct fetched_at DATE prefixes",
  "SELECT substr(fetched_at,1,10) AS d, COUNT(*) FROM daily_bars GROUP BY 1 ORDER BY 1")

q("A6 lag available_at-date minus trade_date, bucketed (CORRECT julianday math)",
  """SELECT CASE
        WHEN available_at IS NULL THEN 'NULL avail'
        WHEN julianday(substr(available_at,1,10))-julianday(trade_date) < 0 THEN 'lag<0 (impossible)'
        WHEN julianday(substr(available_at,1,10))-julianday(trade_date) <= 1 THEN 'lag 0-1d'
        WHEN julianday(substr(available_at,1,10))-julianday(trade_date) <= 7 THEN 'lag 2-7d'
        WHEN julianday(substr(available_at,1,10))-julianday(trade_date) <= 30 THEN 'lag 8-30d'
        ELSE 'lag>30d' END AS bucket, COUNT(*)
     FROM daily_bars GROUP BY 1 ORDER BY 2 DESC""")

# PIT retrieval - my own version, THREE variants to expose any string-vs-date bug
for asof in ('2023-09-04','2024-06-30','2025-06-30','2026-06-30','2026-07-15','2026-07-16','2026-07-19','2026-09-03','2026-09-04'):
    r = c.execute("""
      SELECT
        (SELECT COUNT(*) FROM daily_bars WHERE trade_date<=? AND available_at<=?),
        (SELECT COUNT(*) FROM daily_bars WHERE trade_date<=? AND substr(available_at,1,10)<=?),
        (SELECT COUNT(*) FROM daily_bars WHERE trade_date<=? AND date(available_at)<=date(?)),
        (SELECT COUNT(*) FROM daily_bars WHERE trade_date<=?)
    """, (asof,asof,asof,asof,asof,asof,asof)).fetchone()
    print(f"PIT as_of={asof}  rawstr_cmp={r[0]:>9}  substr10_cmp={r[1]:>9}  date()_cmp={r[2]:>9}  no_pit_filter={r[3]:>9}")

q("A7 adjustment_mode distribution market_history",
  "SELECT adjustment_mode, COUNT(*), COUNT(DISTINCT symbol) FROM daily_bars GROUP BY 1")

q("A8 do 'none' and 'qfq' coexist for same symbol+trade_date? (factor derivable?)",
  """SELECT COUNT(*) FROM (SELECT symbol,trade_date FROM daily_bars GROUP BY symbol,trade_date
     HAVING SUM(adjustment_mode='none')>0 AND SUM(adjustment_mode='qfq')>0)""")

q("A9 ingest_runs shape",
  "SELECT id, adjustment_mode, provider, started_at, finished_at, status, rows_written FROM ingest_runs ORDER BY id LIMIT 12")
c.close()
