import sqlite3
MH = r"D:/codex-A股交易/market_history.sqlite3"
con = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
q = lambda s, p=(): con.execute(s, p).fetchall()

def show(t, sql, p=()):
    print("="*78); print(t); print("SQL:", " ".join(sql.split())); 
    for r in q(sql, p): print("   ", dict(r))

# --- 0. denominator integrity: is 2,787,736 the true total? NULLs?
show("0a TOTAL ROWS + NULL available_at (denominator check)", """
SELECT COUNT(*) AS total_rows,
       SUM(CASE WHEN available_at IS NULL THEN 1 ELSE 0 END) AS null_avail,
       SUM(CASE WHEN available_at IS NOT NULL THEN 1 ELSE 0 END) AS nonnull_avail,
       COUNT(DISTINCT symbol) AS distinct_symbols,
       COUNT(DISTINCT adjustment_mode) AS distinct_adjmodes,
       MIN(trade_date) AS min_td, MAX(trade_date) AS max_td
FROM daily_bars""")

# --- 1. raw value shape: is available_at a date or a full timestamp? (string-compare bug check)
show("0b RAW available_at VALUE SHAPE (length + samples)", """
SELECT length(available_at) AS len, COUNT(*) AS n, MIN(available_at) AS min_v, MAX(available_at) AS max_v
FROM daily_bars GROUP BY len ORDER BY n DESC""")

show("0c DISTINCT FULL-PRECISION available_at VALUES (not truncated to day)", """
SELECT COUNT(DISTINCT available_at) AS distinct_full_timestamps,
       COUNT(DISTINCT substr(available_at,1,10)) AS distinct_days,
       COUNT(DISTINCT substr(available_at,1,13)) AS distinct_hours
FROM daily_bars""")

# --- 2. INDEPENDENT METRIC #1: available_at vs fetched_at identity
#     A point-in-time column must be semantically distinct from fetch time.
show("1 IS available_at JUST A COPY OF fetched_at? (structural test, no date math)", """
SELECT SUM(CASE WHEN available_at = fetched_at THEN 1 ELSE 0 END) AS identical_to_fetched_at,
       SUM(CASE WHEN available_at <> fetched_at THEN 1 ELSE 0 END) AS differs,
       SUM(CASE WHEN available_at = updated_at THEN 1 ELSE 0 END) AS identical_to_updated_at,
       COUNT(*) AS total,
       ROUND(100.0*SUM(CASE WHEN available_at = fetched_at THEN 1 ELSE 0 END)/COUNT(*),4) AS pct_identical
FROM daily_bars""")

# --- 3. INDEPENDENT METRIC #2: pure STRING comparison, no julianday, no 30-day threshold.
#     A correct PIT value must satisfy available_at_day >= trade_date and be CLOSE to it.
#     Test the strictest honest bar: available_at day within the same calendar month as trade_date.
show("2 STRING-ONLY test (no julianday): available_at day vs trade_date", """
SELECT SUM(CASE WHEN substr(available_at,1,10) < trade_date THEN 1 ELSE 0 END) AS avail_BEFORE_trade_date,
       SUM(CASE WHEN substr(available_at,1,10) = trade_date THEN 1 ELSE 0 END) AS same_day,
       SUM(CASE WHEN substr(available_at,1,7) = substr(trade_date,1,7) THEN 1 ELSE 0 END) AS same_calendar_month,
       SUM(CASE WHEN substr(available_at,1,4) = substr(trade_date,1,4) THEN 1 ELSE 0 END) AS same_calendar_year,
       SUM(CASE WHEN substr(available_at,1,4) > substr(trade_date,1,4) THEN 1 ELSE 0 END) AS later_year,
       COUNT(*) AS total
FROM daily_bars""")

# --- 4. INDEPENDENT METRIC #3: count DISTINCT SECURITIES, not rows; exclude indices.
show("3 DISTINCT SECURITIES affected, INDICES EXCLUDED (their metric was rows)", """
SELECT COUNT(DISTINCT b.symbol) AS stocks_total,
       COUNT(DISTINCT CASE WHEN substr(b.available_at,1,7) <> substr(b.trade_date,1,7)
             THEN b.symbol END) AS stocks_with_any_stale_month,
       COUNT(DISTINCT CASE WHEN substr(b.available_at,1,7) = substr(b.trade_date,1,7)
             THEN b.symbol END) AS stocks_with_any_same_month
FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
WHERE i.exchange IN ('SH','SZ','BJ')""")

show("3b PER-STOCK: how many NON-INDEX stocks have EVERY bar stale (>1 month)?", """
WITH s AS (
  SELECT b.symbol,
         COUNT(*) AS n,
         SUM(CASE WHEN substr(b.available_at,1,7) <> substr(b.trade_date,1,7) THEN 1 ELSE 0 END) AS stale
  FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
  WHERE i.exchange IN ('SH','SZ','BJ') GROUP BY b.symbol)
SELECT COUNT(*) AS stocks,
       SUM(CASE WHEN stale=n THEN 1 ELSE 0 END) AS all_bars_stale,
       SUM(CASE WHEN stale=0 THEN 1 ELSE 0 END) AS no_bar_stale,
       SUM(CASE WHEN stale>0 AND stale<n THEN 1 ELSE 0 END) AS mixed
FROM s""")

# --- 5. RESEARCH WINDOW restricted (their claim used the whole table)
show("4 RESTRICTED TO RESEARCH WINDOW 2023-09-04..2026-09-04, NON-INDEX ONLY", """
SELECT COUNT(*) AS rows_in_window,
       SUM(CASE WHEN substr(b.available_at,1,7) = substr(b.trade_date,1,7) THEN 1 ELSE 0 END) AS same_month,
       SUM(CASE WHEN substr(b.available_at,1,10) <= date(b.trade_date,'+3 day') THEN 1 ELSE 0 END) AS avail_within_3d,
       SUM(CASE WHEN substr(b.available_at,1,10) <= date(b.trade_date,'+30 day') THEN 1 ELSE 0 END) AS avail_within_30d
FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
WHERE i.exchange IN ('SH','SZ','BJ')
  AND b.trade_date BETWEEN '2023-09-04' AND '2026-09-04'""")
con.close()
