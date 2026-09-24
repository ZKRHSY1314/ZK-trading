# -*- coding: utf-8 -*-
import sqlite3
MH = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)
def q(label, sql, params=()):
    print("\n### " + label)
    print("SQL: " + " ".join(sql.split()))
    cur = c.execute(sql, params)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    print(" | ".join(cols))
    for r in rows[:60]:
        print(" | ".join("NULL" if v is None else str(v) for v in r))
    if len(rows) > 60: print(f"... ({len(rows)} rows total)")
    return rows

# ---- A. NULL-SAFE equality. Their `<>` yields NULL (excluded) whenever either side is NULL.
q("A1 null-safe divergence + null census",
  """SELECT COUNT(*) total,
            SUM(CASE WHEN available_at IS NULL THEN 1 ELSE 0 END) avail_null,
            SUM(CASE WHEN fetched_at IS NULL THEN 1 ELSE 0 END) fetch_null,
            SUM(CASE WHEN available_at IS NOT fetched_at THEN 1 ELSE 0 END) nullsafe_differ,
            SUM(CASE WHEN available_at <> fetched_at THEN 1 ELSE 0 END) their_operator,
            SUM(CASE WHEN available_at IS fetched_at THEN 1 ELSE 0 END) nullsafe_identical
     FROM daily_bars""")

# ---- B. string format hygiene of available_at (would break any string cutoff comparison)
q("A2 available_at string shapes",
  """SELECT length(available_at) len,
            CASE WHEN available_at LIKE '%T%' THEN 'T-sep'
                 WHEN available_at LIKE '% %' THEN 'space-sep' ELSE 'other' END sep,
            CASE WHEN available_at LIKE '%+%' OR available_at LIKE '%Z' THEN 'tz' ELSE 'naive' END tz,
            COUNT(*) n, MIN(available_at) lo, MAX(available_at) hi
     FROM daily_bars GROUP BY len, sep, tz ORDER BY n DESC""")

# ---- C. real trade_date span, per adjustment_mode (they reported 2024-04-09..2026-09-03)
q("A3 span by adjustment_mode",
  """SELECT adjustment_mode, COUNT(*) n, COUNT(DISTINCT symbol) syms,
            MIN(trade_date) min_td, MAX(trade_date) max_td,
            MIN(available_at) min_av, MAX(available_at) max_av
     FROM daily_bars GROUP BY adjustment_mode""")

# ---- D. distinct-symbol view of the ingest sessions, split stocks vs indices via instruments
q("A4 ingest sessions by available_at day, STOCKS ONLY (exchange in SH/SZ/BJ)",
  """SELECT substr(b.available_at,1,10) av_day, COUNT(*) n,
            COUNT(DISTINCT b.symbol) syms, MIN(b.trade_date) min_td, MAX(b.trade_date) max_td
     FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
     WHERE i.exchange IN ('SH','SZ','BJ')
     GROUP BY av_day ORDER BY av_day""")

q("A5 ingest sessions by available_at day, NON-STOCK (index/other)",
  """SELECT substr(b.available_at,1,10) av_day, i.exchange, COUNT(*) n, COUNT(DISTINCT b.symbol) syms
     FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
     WHERE i.exchange NOT IN ('SH','SZ','BJ')
     GROUP BY av_day, i.exchange ORDER BY av_day, i.exchange""")

# ---- E. is available_at EVER distinct from fetched_at at second granularity? compare as julian
q("A6 max abs(julianday(available_at)-julianday(fetched_at)) seconds",
  """SELECT COUNT(*) comparable,
            MAX(ABS(julianday(available_at)-julianday(fetched_at))*86400.0) max_abs_sec,
            SUM(CASE WHEN ABS(julianday(available_at)-julianday(fetched_at))*86400.0 > 0.5 THEN 1 ELSE 0 END) gt_half_sec
     FROM daily_bars WHERE available_at IS NOT NULL AND fetched_at IS NOT NULL""")

# ---- F. lag distribution, STOCKS ONLY, restricted to the research window
q("A7 lag(available_at - trade_date) in days, STOCKS ONLY, window 2023-09-04..2026-09-04",
  """WITH s AS (
       SELECT CAST(julianday(substr(b.available_at,1,10)) - julianday(b.trade_date) AS INTEGER) lag
       FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
       WHERE i.exchange IN ('SH','SZ','BJ')
         AND b.trade_date BETWEEN '2023-09-04' AND '2026-09-04'
         AND b.available_at IS NOT NULL)
     SELECT COUNT(*) n, MIN(lag) min_lag, MAX(lag) max_lag,
            AVG(lag) mean_lag,
            SUM(CASE WHEN lag<=0 THEN 1 ELSE 0 END) lag_le0,
            SUM(CASE WHEN lag<=1 THEN 1 ELSE 0 END) lag_le1,
            SUM(CASE WHEN lag<=5 THEN 1 ELSE 0 END) lag_le5,
            SUM(CASE WHEN lag>365 THEN 1 ELSE 0 END) lag_gt365
     FROM s""")

q("A8 lag percentiles STOCKS ONLY (median/p95 by ordered offset)",
  """WITH s AS (
       SELECT CAST(julianday(substr(b.available_at,1,10)) - julianday(b.trade_date) AS INTEGER) lag
       FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
       WHERE i.exchange IN ('SH','SZ','BJ') AND b.available_at IS NOT NULL
       ORDER BY lag),
     n AS (SELECT COUNT(*) c FROM s)
     SELECT (SELECT c FROM n) total,
            (SELECT lag FROM s LIMIT 1 OFFSET (SELECT c/2 FROM n)) p50,
            (SELECT lag FROM s LIMIT 1 OFFSET (SELECT c*95/100 FROM n)) p95,
            (SELECT lag FROM s LIMIT 1 OFFSET (SELECT c*5/100 FROM n)) p05""")
c.close()
