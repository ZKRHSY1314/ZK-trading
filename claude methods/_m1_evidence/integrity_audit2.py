# -*- coding: utf-8 -*-
"""READ-ONLY round 2: symbol aliasing, zero-volume, cross-DB reconciliation, warm-up boundary."""
import sqlite3, sys, json, io, urllib.parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

OPS = r"D:\codex-A股交易\trading_local.sqlite3"
HIST = r"D:\codex-A股交易\market_history.sqlite3"

def ro(p):
    uri = "file:" + urllib.parse.quote(p.replace("\\", "/")) + "?mode=ro"
    c = sqlite3.connect(uri, uri=True)
    c.row_factory = sqlite3.Row
    return c

results = {}

def q(conn, name, sql, params=()):
    cur = conn.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    results[name] = {"sql": " ".join(sql.split()), "rows": rows}
    print("\n### %s" % name)
    print("SQL: %s" % " ".join(sql.split()))
    for r in rows[:60]:
        print("   ", r)
    if len(rows) > 60:
        print("    ... (%d rows total)" % len(rows))
    return rows

ops = ro(OPS)
hist = ro(HIST)

print("=" * 100)
print("PART A - WINDOW BOUNDARY / WARM-UP")
print("=" * 100)

q(ops, "ops.minmax_trade_date", """
SELECT MIN(trade_date) AS min_td, MAX(trade_date) AS max_td, COUNT(*) AS n
FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
""")

q(ops, "ops.rows_before_window_start", """
SELECT COUNT(*) AS n_rows_before_2023_09_04, COUNT(DISTINCT symbol) AS symbols
FROM daily_bar_cache
WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND trade_date < '2023-09-04'
""")

q(ops, "ops.distinct_sessions_in_window", """
SELECT COUNT(DISTINCT trade_date) AS distinct_sessions, MIN(trade_date) AS first, MAX(trade_date) AS last
FROM daily_bar_cache
WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
  AND trade_date >= '2023-09-04' AND trade_date <= '2026-09-04'
""")

print("\n" + "=" * 100)
print("PART B - SYMBOL ALIASING: bare 6-digit vs EXCHANGE-PREFIXED spellings")
print("=" * 100)

q(ops, "ops.bare6_symbols_detail", """
SELECT symbol, COUNT(*) AS rows, MIN(trade_date) AS min_td, MAX(trade_date) AS max_td,
       GROUP_CONCAT(DISTINCT source) AS sources, GROUP_CONCAT(DISTINCT quality_status) AS statuses,
       GROUP_CONCAT(DISTINCT adjustment_mode) AS adj
FROM daily_bar_cache WHERE LENGTH(symbol)=6 GROUP BY symbol ORDER BY symbol
""")

q(ops, "ops.bare6_alias_partners", """
SELECT symbol, COUNT(*) AS rows, MIN(trade_date) AS min_td, MAX(trade_date) AS max_td,
       GROUP_CONCAT(DISTINCT source) AS sources
FROM daily_bar_cache
WHERE substr(symbol,3) IN ('000001','600519','300750','920099') AND LENGTH(symbol)=8
GROUP BY symbol ORDER BY symbol
""")

q(ops, "ops.alias_date_overlap", """
SELECT b.symbol AS bare, p.symbol AS prefixed, COUNT(*) AS overlapping_dates,
       MIN(b.trade_date) AS first_overlap, MAX(b.trade_date) AS last_overlap
FROM daily_bar_cache b
JOIN daily_bar_cache p
  ON p.trade_date = b.trade_date AND substr(p.symbol,3) = b.symbol AND LENGTH(p.symbol)=8
WHERE LENGTH(b.symbol)=6
GROUP BY b.symbol, p.symbol ORDER BY overlapping_dates DESC
""")

q(ops, "ops.alias_price_divergence", """
SELECT b.symbol AS bare, p.symbol AS prefixed,
       COUNT(*) AS overlap_rows,
       SUM(CASE WHEN ABS(COALESCE(b.close,-1) - COALESCE(p.close,-2)) > 0.005 THEN 1 ELSE 0 END) AS close_differs,
       MAX(ABS(COALESCE(b.close,0) - COALESCE(p.close,0))) AS max_abs_close_diff,
       SUM(CASE WHEN b.amount IS NULL AND p.amount IS NOT NULL THEN 1 ELSE 0 END) AS bare_amount_null_prefixed_not
FROM daily_bar_cache b
JOIN daily_bar_cache p
  ON p.trade_date = b.trade_date AND substr(p.symbol,3) = b.symbol AND LENGTH(p.symbol)=8
WHERE LENGTH(b.symbol)=6
GROUP BY b.symbol, p.symbol
""")

q(ops, "ops.alias_example_rows", """
SELECT symbol, trade_date, open, high, low, close, volume, amount, source, quality_status, adjustment_mode
FROM daily_bar_cache
WHERE (symbol='000001' OR symbol='SZ000001') AND trade_date >= '2026-08-28'
ORDER BY trade_date DESC, symbol LIMIT 20
""")

q(ops, "ops.securities_after_alias_normalize", """
SELECT COUNT(DISTINCT CASE WHEN LENGTH(symbol)=8 THEN substr(symbol,3) ELSE symbol END) AS distinct_codes,
       COUNT(DISTINCT symbol) AS distinct_spellings
FROM daily_bar_cache
""")

print("\n" + "=" * 100)
print("PART C - ZERO-VOLUME / ZERO-AMOUNT / DEGENERATE BARS")
print("=" * 100)

q(ops, "ops.zero_volume_rows", """
SELECT symbol, trade_date, open, high, low, close, volume, amount, source, quality_status
FROM daily_bar_cache WHERE volume = 0 ORDER BY trade_date DESC
""")

q(ops, "ops.zero_amount_ready_nonzero_volume", """
SELECT COUNT(*) AS n FROM daily_bar_cache
WHERE amount = 0 AND volume > 0 AND quality_status='ready'
""")

q(ops, "ops.flat_bars", """
SELECT COUNT(*) AS n_flat_ohlc, COUNT(DISTINCT symbol) AS symbols
FROM daily_bar_cache
WHERE open = high AND high = low AND low = close AND quality_status='ready'
""")

q(ops, "ops.demo_fixture_rows", """
SELECT symbol, trade_date, open, high, low, close, volume, amount, source, quality_status,
       adjustment_mode, volume_unit, created_at, updated_at
FROM daily_bar_cache WHERE quality_status='demo_fixture' ORDER BY symbol, trade_date
""")

q(ops, "ops.review_only_unadjusted_symbols", """
SELECT symbol, COUNT(*) AS n, MIN(trade_date) AS min_td, MAX(trade_date) AS max_td,
       GROUP_CONCAT(DISTINCT source) AS sources
FROM daily_bar_cache WHERE quality_status='review_only_unadjusted'
GROUP BY symbol ORDER BY n DESC LIMIT 60
""")

q(ops, "ops.index_symbols", """
SELECT symbol, COUNT(*) AS n, MIN(trade_date) AS min_td, MAX(trade_date) AS max_td, source, adjustment_mode
FROM daily_bar_cache WHERE adjustment_mode='none' AND quality_status='ready'
GROUP BY symbol, source, adjustment_mode ORDER BY n DESC
""")

print("\n" + "=" * 100)
print("PART D - CROSS-DB RECONCILIATION OF THE BAD ROWS")
print("=" * 100)

q(hist, "hist.bad_ohlc_symbols_on_2024_11_06", """
SELECT symbol, trade_date, open, high, low, close, volume, amount, provider, quality_status
FROM daily_bars
WHERE symbol IN ('SH688173','SH688143','SH688089') AND trade_date = '2024-11-06'
ORDER BY symbol
""")

q(hist, "hist.zero_open_rows", """
SELECT COUNT(*) AS n_rows_with_zero_open_high_or_low
FROM daily_bars WHERE open = 0 OR high = 0 OR low = 0
""")

q(hist, "hist.bj920289_present", """
SELECT symbol, COUNT(*) AS n, MIN(trade_date) AS min_td, MAX(trade_date) AS max_td
FROM daily_bars WHERE symbol = 'BJ920289' GROUP BY symbol
""")

q(hist, "hist.symbol_shape_dist", """
SELECT LENGTH(symbol) AS len, COUNT(DISTINCT symbol) AS distinct_symbols, COUNT(*) AS rows
FROM daily_bars GROUP BY LENGTH(symbol) ORDER BY rows DESC
""")

q(hist, "hist.amount_null_by_year", """
SELECT substr(trade_date,1,4) AS yr, COUNT(*) AS rows,
       SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) AS amount_null,
       ROUND(100.0*SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END)/COUNT(*),2) AS pct_null
FROM daily_bars GROUP BY substr(trade_date,1,4) ORDER BY yr
""")

q(ops, "ops.amount_null_by_year", """
SELECT substr(trade_date,1,4) AS yr, COUNT(*) AS rows,
       SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) AS amount_null,
       ROUND(100.0*SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END)/COUNT(*),2) AS pct_null
FROM daily_bar_cache
WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
GROUP BY substr(trade_date,1,4) ORDER BY yr
""")

q(ops, "ops.amount_null_by_source", """
SELECT source, COUNT(*) AS rows, SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) AS amount_null,
       ROUND(100.0*SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END)/COUNT(*),2) AS pct_null
FROM daily_bar_cache GROUP BY source ORDER BY amount_null DESC LIMIT 20
""")

print("\n" + "=" * 100)
print("PART E - market_history CHECK PROVENANCE (were constraints present at load time?)")
print("=" * 100)

q(hist, "hist.master_tables", "SELECT name, type FROM sqlite_master WHERE type='table' ORDER BY name")
q(hist, "hist.schema_version_like", """
SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%migration%' OR name LIKE '%schema%' OR name LIKE '%version%')
""")
q(hist, "hist.ingest_runs_span", """
SELECT MIN(id) AS min_id, MAX(id) AS max_id, COUNT(*) AS n,
       MIN(started_at) AS min_started, MAX(started_at) AS max_started
FROM ingest_runs
""")
q(hist, "hist.daily_bars_created_span", """
SELECT MIN(created_at) AS min_created, MAX(created_at) AS max_created,
       MIN(fetched_at) AS min_fetched, MAX(fetched_at) AS max_fetched
FROM daily_bars
""")
q(hist, "hist.available_at_nulls", """
SELECT SUM(CASE WHEN available_at IS NULL THEN 1 ELSE 0 END) AS available_at_null,
       COUNT(*) AS total FROM daily_bars
""")

print("\n" + "=" * 100)
print("PART F - ENGINE REACHABILITY OF DEFECTIVE ROWS")
print("=" * 100)

# engine._load_symbol_frames has NO date filter; only quality_status='ready'.
q(ops, "ops.engine_reachable_defects", """
SELECT
  SUM(CASE WHEN high < low OR high < open OR high < close OR low > open OR low > close THEN 1 ELSE 0 END) AS ohlc_violations,
  SUM(CASE WHEN open = 0 OR high = 0 OR low = 0 OR close = 0 THEN 1 ELSE 0 END) AS zero_price_rows,
  SUM(CASE WHEN open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL THEN 1 ELSE 0 END) AS null_price_rows,
  SUM(CASE WHEN trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN 1 ELSE 0 END) AS bad_date_rows,
  SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) AS amount_null_rows,
  COUNT(*) AS total_ready_rows
FROM daily_bar_cache WHERE quality_status = 'ready'
""")

# benchmark query predicate: quality_status='ready' AND trade_date >= ? AND <= ?
q(ops, "ops.benchmark_predicate_error_rows", """
SELECT COUNT(*) AS n FROM daily_bar_cache
WHERE quality_status='ready' AND trade_date >= '2023-09-04' AND trade_date <= '2026-09-04'
  AND trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
""")

# one-sided '> ?' predicate (offhour.py:6979) has NO ERROR guard - would 'ERROR' be returned?
q(ops, "ops.one_sided_gt_would_include_error", """
SELECT COUNT(*) AS n_error_rows_matching_gt_predicate
FROM daily_bar_cache
WHERE quality_status='ready' AND trade_date > '2026-09-04'
""")
q(ops, "ops.string_cmp_proof", """
SELECT 'ERROR' > '2026-09-04' AS error_gt_window_end,
       'ERROR' >= '2023-09-04' AS error_ge_window_start,
       'ERROR' <= '2026-09-04' AS error_le_window_end,
       'ERROR' BETWEEN '2023-09-04' AND '2026-09-04' AS error_between
""")

with open(r"D:\codex-A股交易\claude methods\_m1_evidence\integrity_results2.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=1, default=str)
print("\n\nSAVED integrity_results2.json")
