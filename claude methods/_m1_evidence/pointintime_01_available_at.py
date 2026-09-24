import sqlite3, sys, time
sys.stdout.reconfigure(encoding='utf-8')
MH = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)

def q(sql, params=(), label=None):
    t=time.time()
    rows = c.execute(sql, params).fetchall()
    print(f"\n### {label}")
    print("SQL:", " ".join(sql.split()))
    for r in rows[:400]:
        print("   ", r)
    if len(rows)>400: print(f"    ... ({len(rows)} rows total)")
    print(f"    [{time.time()-t:.1f}s]")
    return rows

WIN0, WIN1 = "2023-09-04", "2026-09-04"

q("SELECT COUNT(*) AS total, SUM(available_at IS NOT NULL) AS non_null, SUM(available_at IS NULL) AS is_null FROM daily_bars",
  label="A1 daily_bars available_at null-ness (all rows)")

q("SELECT COUNT(*) total, SUM(available_at IS NOT NULL) non_null FROM daily_bars WHERE trade_date BETWEEN ? AND ?",
  (WIN0,WIN1), label="A2 available_at null-ness inside research window")

q("SELECT MIN(available_at), MAX(available_at), MIN(trade_date), MAX(trade_date) FROM daily_bars WHERE available_at IS NOT NULL",
  label="A3 available_at range vs trade_date range (non-null rows)")

q("SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM daily_bars",
  label="A4 daily_bars trade_date full range")

q("SELECT COUNT(*) FROM daily_bars WHERE available_at IS NOT NULL AND substr(available_at,1,10) < trade_date",
  label="A5 IMPOSSIBLE: available_at date EARLIER than trade_date")

q("SELECT COUNT(*) FROM daily_bars WHERE available_at IS NOT NULL AND substr(available_at,1,10) = trade_date",
  label="A6 available_at SAME calendar day as trade_date")

q("""SELECT CAST(julianday(substr(available_at,1,10)) - julianday(trade_date) AS INT) AS lag_days,
      COUNT(*) AS n, MIN(trade_date) AS first_td, MAX(trade_date) AS last_td
     FROM daily_bars WHERE available_at IS NOT NULL
     GROUP BY lag_days ORDER BY lag_days""",
  label="A7 available_at MINUS trade_date, in calendar days (full distribution)")

q("SELECT provider, adjustment_mode, COUNT(*) n, SUM(available_at IS NOT NULL) with_avail, MIN(trade_date), MAX(trade_date), MIN(fetched_at), MAX(fetched_at) FROM daily_bars GROUP BY provider, adjustment_mode ORDER BY n DESC",
  label="A8 daily_bars by provider x adjustment_mode, incl. fetched_at range")

q("SELECT substr(fetched_at,1,10) AS fetch_day, COUNT(*) n, MIN(trade_date) min_td, MAX(trade_date) max_td, COUNT(DISTINCT symbol) syms FROM daily_bars GROUP BY fetch_day ORDER BY fetch_day",
  label="A9 daily_bars fetched_at by day (the true collection calendar)")

q("SELECT quality_status, COUNT(*) FROM daily_bars GROUP BY quality_status",
  label="A10 daily_bars quality_status")

q("SELECT COUNT(*) FROM daily_bars WHERE available_at IS NOT NULL AND available_at > fetched_at",
  label="A11 available_at later than fetched_at (would mean stamped in the future of collection)")

q("SELECT COUNT(*) FROM daily_bars WHERE substr(fetched_at,1,10) < trade_date",
  label="A12 IMPOSSIBLE-2: fetched_at earlier than trade_date")

q("""SELECT CAST(julianday(substr(fetched_at,1,10)) - julianday(trade_date) AS INT)/30 AS lag_months, COUNT(*) n
     FROM daily_bars WHERE trade_date BETWEEN ? AND ? GROUP BY lag_months ORDER BY lag_months""",
  (WIN0,WIN1), label="A13 fetched_at minus trade_date, in ~30d buckets, window rows only")

q("SELECT ingest_run_id, COUNT(*) n, MIN(trade_date), MAX(trade_date) FROM daily_bars GROUP BY ingest_run_id ORDER BY n DESC LIMIT 30",
  label="A14 daily_bars rows per ingest_run_id")

c.close()
