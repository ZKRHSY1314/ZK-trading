# -*- coding: utf-8 -*-
import sqlite3
MH = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)
def q(label, sql, params=()):
    print("\n### " + label); print("SQL: " + " ".join(sql.split()))
    cur = c.execute(sql, params); rows = cur.fetchall()
    print(" | ".join(d[0] for d in cur.description))
    for r in rows[:80]: print(" | ".join("NULL" if v is None else str(v) for v in r))
    return rows

# B1: PIT cutoff sweep across the research window - what a walk-forward split would actually see
print("\n### B1 PIT cutoff sweep: rows/symbols visible at each quarterly cutoff")
print("SQL: SELECT COUNT(*), COUNT(DISTINCT symbol), MAX(trade_date) FROM daily_bars WHERE available_at <= ?  -- swept")
print("cutoff | rows_visible | syms_visible | max_trade_date_visible | rows_pct")
tot = c.execute("SELECT COUNT(*) FROM daily_bars").fetchone()[0]
cutoffs = ["2023-09-04T23:59:59","2024-01-01T23:59:59","2024-06-30T23:59:59","2025-01-01T23:59:59",
           "2025-06-30T23:59:59","2026-01-01T23:59:59","2026-06-30T23:59:59","2026-07-15T14:15:17",
           "2026-07-15T14:15:18","2026-07-16T23:59:59","2026-07-19T23:59:59","2026-09-02T23:59:59",
           "2026-09-03T19:52:12","2026-09-04T23:59:59"]
for cut in cutoffs:
    n, s, mx = c.execute(
        "SELECT COUNT(*), COUNT(DISTINCT symbol), MAX(trade_date) FROM daily_bars WHERE available_at <= ?",
        (cut,)).fetchone()
    print(f"{cut} | {n} | {s} | {mx} | {100.0*n/tot:.4f}%")

# B2: the ONLY thing that would rescue PIT - does available_at ever discriminate WITHIN a trade_date?
q("B2 trade_dates whose rows carry >1 distinct available_at (i.e. column carries any signal at all)",
  """SELECT COUNT(*) trade_dates_total,
            SUM(CASE WHEN navail>1 THEN 1 ELSE 0 END) trade_dates_multi_avail,
            MAX(navail) max_distinct_avail_per_day
     FROM (SELECT trade_date, COUNT(DISTINCT available_at) navail FROM daily_bars GROUP BY trade_date)""")

# B3: conversely - do distinct available_at values discriminate anything other than the 4 sessions?
q("B3 distinct available_at values overall",
  """SELECT COUNT(DISTINCT available_at) distinct_available_at,
            COUNT(DISTINCT substr(available_at,1,10)) distinct_days,
            COUNT(DISTINCT trade_date) distinct_trade_dates FROM daily_bars""")

# B4: the freshest session only - is available_at plausible there (post-close same day)?
q("B4 within the 2026-09-03 session: lag distribution",
  """SELECT CAST(julianday(substr(available_at,1,10))-julianday(trade_date) AS INTEGER) lag,
            COUNT(*) n, COUNT(DISTINCT symbol) syms
     FROM daily_bars WHERE substr(available_at,1,10)='2026-09-03'
     GROUP BY lag ORDER BY lag LIMIT 12""")

# B5: how many rows are same-day-knowable (lag 0) and are they real?
q("B5 lag<=0 rows: which trade_dates",
  """SELECT trade_date, COUNT(*) n, COUNT(DISTINCT symbol) syms, MIN(available_at) av
     FROM daily_bars
     WHERE julianday(substr(available_at,1,10))-julianday(trade_date) <= 0
     GROUP BY trade_date ORDER BY trade_date""")

# B6: ingest_runs - is there an alternative PIT source that rescues the column?
q("B6 ingest_runs schema",
  "SELECT sql FROM sqlite_master WHERE name='ingest_runs'")
q("B7 ingest_run_id linkage on daily_bars",
  """SELECT COUNT(*) total, SUM(CASE WHEN ingest_run_id IS NULL THEN 1 ELSE 0 END) run_null,
            COUNT(DISTINCT ingest_run_id) distinct_runs FROM daily_bars""")
c.close()
