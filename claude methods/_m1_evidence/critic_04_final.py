# -*- coding: utf-8 -*-
"""FINAL adversarial confirmation. STRICT READ-ONLY."""
import sqlite3, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
OP=r"D:\codex-A股交易\trading_local.sqlite3"; MH=r"D:\codex-A股交易\market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro",uri=True)
def show(t,sql,con):
    print("="*78); print(t); print("SQL:"," ".join(sql.split()))
    cur=con.execute(sql); rows=cur.fetchall()
    print("COLS:",[d[0] for d in cur.description])
    for r in rows[:40]: print("   ",r)
    print()
op=ro(OP); mh=ro(MH)

show("J1 HEADLINE: my independent single-query restatement of the whole claim",
 """SELECT
   (SELECT MIN(trade_date) FROM daily_bar_cache
      WHERE date(trade_date) IS NOT NULL)                       AS min_valid_date_via_date_fn,
   (SELECT COUNT(*) FROM daily_bar_cache
      WHERE date(trade_date) IS NOT NULL AND date(trade_date) < date('2023-09-04')) AS rows_before_window_start,
   (SELECT COUNT(*) FROM daily_bar_cache
      WHERE date(trade_date) IS NOT NULL
        AND date(trade_date) >= date('2023-09-04')
        AND date(trade_date) <= date('2024-04-08'))             AS rows_in_first_7_months,
   (SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache
      WHERE date(trade_date) IS NOT NULL AND date(trade_date) < date('2024-04-09')) AS symbols_before_floor,
   (SELECT COUNT(*) FROM daily_bar_cache WHERE date(trade_date) IS NULL) AS rows_unparseable_as_date""", op)

show("J2 the 2024-04-09 floor is ONE row for ONE symbol; breadth thresholds",
 """WITH b AS (SELECT trade_date, COUNT(DISTINCT symbol) syms FROM daily_bar_cache
             WHERE date(trade_date) IS NOT NULL GROUP BY trade_date)
    SELECT (SELECT syms FROM b WHERE trade_date='2024-04-09') AS syms_on_claimed_floor,
           (SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date='2024-04-09') AS rows_on_claimed_floor,
           (SELECT MIN(trade_date) FROM b WHERE syms>=1000) AS first_session_ge_1000_symbols,
           (SELECT MIN(trade_date) FROM b WHERE syms>=5000) AS first_session_ge_5000_symbols,
           (SELECT COUNT(*) FROM b WHERE syms<1000) AS sessions_with_under_1000_symbols,
           (SELECT SUM(syms) FROM b WHERE trade_date<'2024-06-21') AS symbol_days_before_breadth""", op)

show("J3 hard per-symbol bar cap vs sessions available (mechanism = rolling fetch limit)",
 """SELECT (SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE date(trade_date) IS NOT NULL) AS sessions_present,
           (SELECT MAX(n) FROM (SELECT symbol,COUNT(*) n FROM daily_bar_cache
              WHERE date(trade_date) IS NOT NULL GROUP BY symbol)) AS max_bars_any_symbol,
           (SELECT COUNT(*) FROM (SELECT symbol,COUNT(*) n FROM daily_bar_cache
              WHERE date(trade_date) IS NOT NULL GROUP BY symbol) WHERE n BETWEEN 500 AND 538) AS symbols_in_500_538_band""", op)

show("J4 MISSING HISTORY vs NEW LISTING: instruments alive at window start",
 """SELECT COUNT(*) AS equities_listed_and_alive_on_2023_09_04,
           SUM(CASE WHEN list_date <= '2022-09-04' THEN 1 ELSE 0 END) AS also_alive_one_year_earlier
    FROM instruments
    WHERE asset_type='stock' AND exchange IN ('SH','SZ','BJ')
      AND list_date IS NOT NULL AND list_date <= '2023-09-04'
      AND (delist_date IS NULL OR delist_date > '2023-09-04')""", mh)

show("J5 market_history floor, independently, excluding indices and using date()",
 """SELECT MIN(trade_date) AS min_td, COUNT(*) AS rows_before_floor
    FROM daily_bars WHERE date(trade_date) < date('2024-04-09')""", mh)

show("J6 market_history: rows anywhere inside 2023-09-04..2024-04-08",
 """SELECT COUNT(*) n, COUNT(DISTINCT symbol) syms FROM daily_bars
    WHERE trade_date >= '2023-09-04' AND trade_date <= '2024-04-08'""", mh)

show("J7 earliest available_at / fetched_at — when did ingestion actually begin?",
 """SELECT MIN(available_at) min_avail, MAX(available_at) max_avail,
           MIN(fetched_at) min_fetched, MAX(fetched_at) max_fetched FROM daily_bars""", mh)

show("J8 sanity: ISO strings sort chronologically (no string-vs-date bug)",
 """SELECT '2023-09-04' < '2024-04-09' AS a, '2024-04-08' < '2024-04-09' AS b,
           '2026-09-04' > '2024-04-09' AS c, 'ERROR' > '2026-09-04' AS d_error_sorts_last""", op)
op.close(); mh.close()
