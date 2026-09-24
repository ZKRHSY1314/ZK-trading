# -*- coding: utf-8 -*-
"""READ-ONLY structural integrity audit of daily_bar_cache vs market_history.daily_bars."""
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
print("PART 0 - SCHEMA / DDL")
print("=" * 100)
q(ops, "ops.schema.daily_bar_cache",
  "SELECT sql FROM sqlite_master WHERE name='daily_bar_cache'")
q(ops, "ops.indexes.daily_bar_cache",
  "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='daily_bar_cache'")
q(hist, "hist.schema.daily_bars",
  "SELECT sql FROM sqlite_master WHERE name='daily_bars'")
q(hist, "hist.indexes.daily_bars",
  "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='daily_bars'")

print("\n" + "=" * 100)
print("PART 1 - daily_bar_cache: OHLC RELATIONAL VIOLATIONS")
print("=" * 100)

q(ops, "ops.total_rows", "SELECT COUNT(*) AS n FROM daily_bar_cache")

q(ops, "ops.ohlc_violations", """
SELECT
  SUM(CASE WHEN high < low   THEN 1 ELSE 0 END) AS high_lt_low,
  SUM(CASE WHEN high < open  THEN 1 ELSE 0 END) AS high_lt_open,
  SUM(CASE WHEN high < close THEN 1 ELSE 0 END) AS high_lt_close,
  SUM(CASE WHEN low  > open  THEN 1 ELSE 0 END) AS low_gt_open,
  SUM(CASE WHEN low  > close THEN 1 ELSE 0 END) AS low_gt_close,
  SUM(CASE WHEN high < low OR high < open OR high < close OR low > open OR low > close THEN 1 ELSE 0 END) AS any_ohlc_violation
FROM daily_bar_cache
""")

q(ops, "ops.ohlc_violations_in_window", """
SELECT
  SUM(CASE WHEN high < low   THEN 1 ELSE 0 END) AS high_lt_low,
  SUM(CASE WHEN high < open  THEN 1 ELSE 0 END) AS high_lt_open,
  SUM(CASE WHEN high < close THEN 1 ELSE 0 END) AS high_lt_close,
  SUM(CASE WHEN low  > open  THEN 1 ELSE 0 END) AS low_gt_open,
  SUM(CASE WHEN low  > close THEN 1 ELSE 0 END) AS low_gt_close,
  COUNT(*) AS rows_in_window
FROM daily_bar_cache
WHERE trade_date >= '2023-09-04' AND trade_date <= '2026-09-04'
""")

q(ops, "ops.nulls_and_signs", """
SELECT
  SUM(CASE WHEN open  IS NULL THEN 1 ELSE 0 END) AS open_null,
  SUM(CASE WHEN high  IS NULL THEN 1 ELSE 0 END) AS high_null,
  SUM(CASE WHEN low   IS NULL THEN 1 ELSE 0 END) AS low_null,
  SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) AS close_null,
  SUM(CASE WHEN open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL THEN 1 ELSE 0 END) AS any_price_null,
  SUM(CASE WHEN volume IS NULL THEN 1 ELSE 0 END) AS volume_null,
  SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) AS amount_null,
  SUM(CASE WHEN close <= 0 THEN 1 ELSE 0 END) AS close_le_zero,
  SUM(CASE WHEN open < 0 OR high < 0 OR low < 0 OR close < 0 THEN 1 ELSE 0 END) AS any_price_negative,
  SUM(CASE WHEN open = 0 OR high = 0 OR low = 0 THEN 1 ELSE 0 END) AS any_ohl_zero,
  SUM(CASE WHEN volume < 0 THEN 1 ELSE 0 END) AS volume_negative,
  SUM(CASE WHEN amount < 0 THEN 1 ELSE 0 END) AS amount_negative,
  SUM(CASE WHEN volume = 0 THEN 1 ELSE 0 END) AS volume_zero,
  SUM(CASE WHEN amount = 0 THEN 1 ELSE 0 END) AS amount_zero
FROM daily_bar_cache
""")

q(ops, "ops.any_price_null_breakdown", """
SELECT quality_status, trade_date, source, COUNT(*) AS n
FROM daily_bar_cache
WHERE open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL
GROUP BY quality_status, trade_date, source
ORDER BY n DESC LIMIT 40
""")

q(ops, "ops.amount_null_by_quality", """
SELECT quality_status, COUNT(*) AS n
FROM daily_bar_cache WHERE amount IS NULL GROUP BY quality_status ORDER BY n DESC
""")

q(ops, "ops.amount_null_ready_in_window", """
SELECT COUNT(*) AS n FROM daily_bar_cache
WHERE amount IS NULL AND quality_status='ready'
  AND trade_date >= '2023-09-04' AND trade_date <= '2026-09-04'
""")

print("\n" + "=" * 100)
print("PART 2 - daily_bar_cache: trade_date FORMAT / PSEUDO-DATES")
print("=" * 100)

q(ops, "ops.trade_date_length_dist", """
SELECT LENGTH(trade_date) AS len, COUNT(*) AS n, COUNT(DISTINCT symbol) AS symbols
FROM daily_bar_cache GROUP BY LENGTH(trade_date) ORDER BY n DESC
""")

q(ops, "ops.trade_date_bad_glob", """
SELECT trade_date, COUNT(*) AS n, COUNT(DISTINCT symbol) AS symbols
FROM daily_bar_cache
WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
GROUP BY trade_date ORDER BY n DESC
""")

q(ops, "ops.trade_date_typeof", """
SELECT typeof(trade_date) AS t, COUNT(*) AS n FROM daily_bar_cache GROUP BY typeof(trade_date)
""")

q(ops, "ops.trade_date_impossible", """
SELECT trade_date, COUNT(*) AS n FROM daily_bar_cache
WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
  AND (CAST(substr(trade_date,6,2) AS INTEGER) NOT BETWEEN 1 AND 12
       OR CAST(substr(trade_date,9,2) AS INTEGER) NOT BETWEEN 1 AND 31
       OR CAST(substr(trade_date,1,4) AS INTEGER) NOT BETWEEN 1990 AND 2027)
GROUP BY trade_date ORDER BY n DESC LIMIT 40
""")

q(ops, "ops.trade_date_future", """
SELECT trade_date, COUNT(*) AS n FROM daily_bar_cache
WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND trade_date > '2026-09-04'
GROUP BY trade_date ORDER BY trade_date LIMIT 40
""")

q(ops, "ops.ERROR_rows_profile", """
SELECT trade_date, quality_status, source, adjustment_mode, volume_unit,
       COUNT(*) AS n, COUNT(DISTINCT symbol) AS symbols,
       MIN(created_at) AS min_created, MAX(created_at) AS max_created,
       MIN(updated_at) AS min_updated, MAX(updated_at) AS max_updated,
       SUM(CASE WHEN open IS NULL AND high IS NULL AND low IS NULL AND close IS NULL THEN 1 ELSE 0 END) AS all_prices_null,
       SUM(CASE WHEN close IS NOT NULL THEN 1 ELSE 0 END) AS close_not_null
FROM daily_bar_cache
WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
GROUP BY trade_date, quality_status, source, adjustment_mode, volume_unit
ORDER BY n DESC LIMIT 40
""")

q(ops, "ops.ERROR_rows_all", """
SELECT rowid AS rid, symbol, trade_date, open, high, low, close, volume, amount, source,
       quality_status, adjustment_mode, volume_unit, created_at, updated_at
FROM daily_bar_cache
WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
ORDER BY symbol
""")

q(ops, "ops.ERROR_rows_ready_engine_reachable", """
SELECT COUNT(*) AS n_ready_error_rows, COUNT(DISTINCT symbol) AS symbols
FROM daily_bar_cache
WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
  AND quality_status = 'ready'
""")

q(ops, "ops.ERROR_rows_pass_string_range", """
SELECT trade_date, COUNT(*) AS n,
       SUM(CASE WHEN trade_date >= '2023-09-04' AND trade_date <= '2026-09-04' THEN 1 ELSE 0 END) AS inside_ge_le,
       SUM(CASE WHEN trade_date BETWEEN '2023-09-04' AND '2026-09-04' THEN 1 ELSE 0 END) AS inside_between
FROM daily_bar_cache
WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
GROUP BY trade_date
""")

q(ops, "ops.ERROR_rows_survive_dropna", """
SELECT COUNT(*) AS n_error_rows_with_all_prices_nonnull
FROM daily_bar_cache
WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
  AND open IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL AND close IS NOT NULL
""")

print("\n" + "=" * 100)
print("PART 3 - daily_bar_cache: DUPLICATES & SYMBOL SPELLING VARIANTS")
print("=" * 100)

q(ops, "ops.exact_dup_symbol_date", """
SELECT COUNT(*) AS dup_groups FROM (
  SELECT symbol, trade_date FROM daily_bar_cache GROUP BY symbol, trade_date HAVING COUNT(*) > 1
)
""")

q(ops, "ops.symbol_typeof", "SELECT typeof(symbol) AS t, COUNT(*) AS n FROM daily_bar_cache GROUP BY typeof(symbol)")

q(ops, "ops.distinct_symbols", "SELECT COUNT(DISTINCT symbol) AS n FROM daily_bar_cache")

q(ops, "ops.symbol_whitespace", """
SELECT COUNT(*) AS rows_with_ws, COUNT(DISTINCT symbol) AS symbols_with_ws
FROM daily_bar_cache WHERE symbol <> TRIM(symbol)
""")

q(ops, "ops.symbol_case_collisions", """
SELECT UPPER(TRIM(symbol)) AS canon, COUNT(DISTINCT symbol) AS spellings,
       GROUP_CONCAT(DISTINCT symbol) AS variants
FROM daily_bar_cache
GROUP BY UPPER(TRIM(symbol))
HAVING COUNT(DISTINCT symbol) > 1
ORDER BY spellings DESC LIMIT 60
""")

q(ops, "ops.symbol_case_collision_count", """
SELECT COUNT(*) AS canon_keys_with_multiple_spellings,
       SUM(spellings) AS total_spellings_involved
FROM (
  SELECT UPPER(TRIM(symbol)) AS canon, COUNT(DISTINCT symbol) AS spellings
  FROM daily_bar_cache GROUP BY UPPER(TRIM(symbol)) HAVING COUNT(DISTINCT symbol) > 1
)
""")

q(ops, "ops.logical_dup_after_normalize", """
SELECT COUNT(*) AS dup_groups, SUM(n) AS rows_involved, SUM(n-1) AS excess_rows
FROM (
  SELECT UPPER(TRIM(symbol)) AS canon, trade_date, COUNT(*) AS n
  FROM daily_bar_cache GROUP BY UPPER(TRIM(symbol)), trade_date HAVING COUNT(*) > 1
)
""")

q(ops, "ops.symbol_charset", """
SELECT
  SUM(CASE WHEN symbol GLOB '[A-Z][A-Z][0-9][0-9][0-9][0-9][0-9][0-9]' THEN 1 ELSE 0 END) AS upper_prefix_6digit,
  SUM(CASE WHEN symbol GLOB '[a-z][a-z][0-9][0-9][0-9][0-9][0-9][0-9]' THEN 1 ELSE 0 END) AS lower_prefix_6digit,
  SUM(CASE WHEN symbol GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]' THEN 1 ELSE 0 END) AS bare_6digit,
  COUNT(*) AS total
FROM daily_bar_cache
""")

q(ops, "ops.symbol_shape_dist", """
SELECT LENGTH(symbol) AS len, COUNT(DISTINCT symbol) AS distinct_symbols, COUNT(*) AS rows
FROM daily_bar_cache GROUP BY LENGTH(symbol) ORDER BY rows DESC
""")

q(ops, "ops.symbol_odd_examples", """
SELECT symbol, COUNT(*) AS n FROM daily_bar_cache
WHERE symbol NOT GLOB '[A-Z][A-Z][0-9][0-9][0-9][0-9][0-9][0-9]'
GROUP BY symbol ORDER BY n DESC LIMIT 60
""")

print("\n" + "=" * 100)
print("PART 4 - daily_bar_cache: quality_status / source / mode DISTRIBUTIONS")
print("=" * 100)

q(ops, "ops.quality_status_dist", """
SELECT quality_status, COUNT(*) AS n, COUNT(DISTINCT symbol) AS symbols,
       MIN(trade_date) AS min_td, MAX(trade_date) AS max_td
FROM daily_bar_cache GROUP BY quality_status ORDER BY n DESC
""")

q(ops, "ops.not_ready_rows", """
SELECT COUNT(*) AS n FROM daily_bar_cache WHERE quality_status IS NULL OR quality_status <> 'ready'
""")

q(ops, "ops.quality_status_in_window", """
SELECT quality_status, COUNT(*) AS n, COUNT(DISTINCT symbol) AS symbols
FROM daily_bar_cache
WHERE trade_date >= '2023-09-04' AND trade_date <= '2026-09-04'
GROUP BY quality_status ORDER BY n DESC
""")

q(ops, "ops.source_dist", """
SELECT source, COUNT(*) AS n, COUNT(DISTINCT symbol) AS symbols,
       MIN(trade_date) AS min_td, MAX(trade_date) AS max_td
FROM daily_bar_cache GROUP BY source ORDER BY n DESC LIMIT 30
""")

q(ops, "ops.adjustment_mode_dist", """
SELECT adjustment_mode, quality_status, COUNT(*) AS n, COUNT(DISTINCT symbol) AS symbols
FROM daily_bar_cache GROUP BY adjustment_mode, quality_status ORDER BY n DESC LIMIT 30
""")

q(ops, "ops.volume_unit_dist", """
SELECT volume_unit, COUNT(*) AS n, COUNT(DISTINCT symbol) AS symbols
FROM daily_bar_cache GROUP BY volume_unit ORDER BY n DESC
""")

q(ops, "ops.created_updated_nulls", """
SELECT SUM(CASE WHEN created_at IS NULL THEN 1 ELSE 0 END) AS created_null,
       SUM(CASE WHEN updated_at IS NULL THEN 1 ELSE 0 END) AS updated_null,
       MIN(created_at) AS min_created, MAX(created_at) AS max_created,
       MIN(updated_at) AS min_updated, MAX(updated_at) AS max_updated
FROM daily_bar_cache
""")

print("\n" + "=" * 100)
print("PART 5 - daily_bar_cache: STALE UPDATES")
print("=" * 100)

q(ops, "ops.stale_buckets_all_symbols", """
WITH per AS (
  SELECT symbol, MAX(CASE WHEN trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
                          THEN trade_date END) AS last_td
  FROM daily_bar_cache GROUP BY symbol
)
SELECT CASE
    WHEN last_td IS NULL THEN 'A_no_valid_date_at_all'
    WHEN last_td >= '2026-09-01' THEN 'B_lag_0_3d'
    WHEN last_td >= '2026-08-21' THEN 'C_lag_up_to_2w'
    WHEN last_td >= '2026-08-04' THEN 'D_lag_up_to_1m'
    WHEN last_td >= '2026-06-04' THEN 'E_lag_1_3m'
    WHEN last_td >= '2025-09-04' THEN 'F_lag_3_12m'
    WHEN last_td >= '2023-09-04' THEN 'G_lag_1_3y_inside_window'
    ELSE 'H_last_bar_before_window_start'
  END AS bucket,
  COUNT(*) AS symbols, MIN(last_td) AS min_last, MAX(last_td) AS max_last
FROM per GROUP BY bucket ORDER BY bucket
""")

q(ops, "ops.stale_buckets_ready_only", """
WITH per AS (
  SELECT symbol, MAX(CASE WHEN trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
                          THEN trade_date END) AS last_td
  FROM daily_bar_cache WHERE quality_status='ready' GROUP BY symbol
)
SELECT CASE
    WHEN last_td IS NULL THEN 'A_no_valid_date_at_all'
    WHEN last_td >= '2026-09-01' THEN 'B_lag_0_3d'
    WHEN last_td >= '2026-08-21' THEN 'C_lag_up_to_2w'
    WHEN last_td >= '2026-08-04' THEN 'D_lag_up_to_1m'
    WHEN last_td >= '2026-06-04' THEN 'E_lag_1_3m'
    WHEN last_td >= '2025-09-04' THEN 'F_lag_3_12m'
    WHEN last_td >= '2023-09-04' THEN 'G_lag_1_3y_inside_window'
    ELSE 'H_last_bar_before_window_start'
  END AS bucket,
  COUNT(*) AS symbols, MIN(last_td) AS min_last, MAX(last_td) AS max_last
FROM per GROUP BY bucket ORDER BY bucket
""")

q(ops, "ops.global_max_trade_date", """
SELECT MAX(trade_date) AS max_valid_td FROM daily_bar_cache
WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
""")

q(ops, "ops.top_recent_dates", """
SELECT trade_date, COUNT(DISTINCT symbol) AS symbols FROM daily_bar_cache
WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
GROUP BY trade_date ORDER BY trade_date DESC LIMIT 12
""")

q(ops, "ops.updated_at_staleness", """
SELECT substr(updated_at,1,7) AS updated_month, COUNT(DISTINCT symbol) AS symbols, COUNT(*) AS rows
FROM daily_bar_cache GROUP BY substr(updated_at,1,7) ORDER BY updated_month DESC LIMIT 30
""")

print("\n" + "=" * 100)
print("PART 6 - market_history.daily_bars: VERIFY THE CHECKS ACTUALLY HELD")
print("=" * 100)

q(hist, "hist.total_rows", "SELECT COUNT(*) AS n FROM daily_bars")

q(hist, "hist.ohlc_violations", """
SELECT
  SUM(CASE WHEN high < low   THEN 1 ELSE 0 END) AS high_lt_low,
  SUM(CASE WHEN high < open  THEN 1 ELSE 0 END) AS high_lt_open,
  SUM(CASE WHEN high < close THEN 1 ELSE 0 END) AS high_lt_close,
  SUM(CASE WHEN low  > open  THEN 1 ELSE 0 END) AS low_gt_open,
  SUM(CASE WHEN low  > close THEN 1 ELSE 0 END) AS low_gt_close,
  SUM(CASE WHEN open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL THEN 1 ELSE 0 END) AS any_price_null,
  SUM(CASE WHEN close <= 0 THEN 1 ELSE 0 END) AS close_le_zero,
  SUM(CASE WHEN open < 0 OR high < 0 OR low < 0 OR close < 0 THEN 1 ELSE 0 END) AS any_price_negative,
  SUM(CASE WHEN volume < 0 THEN 1 ELSE 0 END) AS volume_negative,
  SUM(CASE WHEN amount < 0 THEN 1 ELSE 0 END) AS amount_negative,
  SUM(CASE WHEN LENGTH(trade_date) <> 10 THEN 1 ELSE 0 END) AS bad_date_len,
  SUM(CASE WHEN trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN 1 ELSE 0 END) AS bad_date_glob,
  SUM(CASE WHEN adjustment_mode NOT IN ('none','qfq','hfq') THEN 1 ELSE 0 END) AS bad_adj_mode,
  SUM(CASE WHEN volume_unit NOT IN ('hand','share','unknown') THEN 1 ELSE 0 END) AS bad_volume_unit,
  SUM(CASE WHEN volume IS NULL THEN 1 ELSE 0 END) AS volume_null,
  SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) AS amount_null
FROM daily_bars
""")

q(hist, "hist.dup_pk", """
SELECT COUNT(*) AS dup_groups FROM (
  SELECT symbol, trade_date, adjustment_mode FROM daily_bars
  GROUP BY symbol, trade_date, adjustment_mode HAVING COUNT(*)>1
)
""")

q(hist, "hist.symbol_case_collisions", """
SELECT COUNT(*) AS canon_keys_with_multiple_spellings FROM (
  SELECT UPPER(TRIM(symbol)) AS c FROM daily_bars GROUP BY UPPER(TRIM(symbol)) HAVING COUNT(DISTINCT symbol)>1
)
""")

q(hist, "hist.symbol_whitespace", """
SELECT COUNT(*) AS rows_with_ws FROM daily_bars WHERE symbol <> TRIM(symbol)
""")

q(hist, "hist.quality_status_dist", """
SELECT quality_status, COUNT(*) AS n, COUNT(DISTINCT symbol) AS symbols FROM daily_bars
GROUP BY quality_status ORDER BY n DESC
""")

q(hist, "hist.adjustment_mode_dist", """
SELECT adjustment_mode, COUNT(*) AS n, COUNT(DISTINCT symbol) AS symbols,
       MIN(trade_date) AS min_td, MAX(trade_date) AS max_td
FROM daily_bars GROUP BY adjustment_mode ORDER BY n DESC
""")

q(hist, "hist.volume_unit_dist", """
SELECT volume_unit, COUNT(*) AS n FROM daily_bars GROUP BY volume_unit ORDER BY n DESC
""")

q(hist, "hist.stale_buckets", """
WITH per AS (SELECT symbol, MAX(trade_date) AS last_td FROM daily_bars GROUP BY symbol)
SELECT CASE
    WHEN last_td >= '2026-09-01' THEN 'B_lag_0_3d'
    WHEN last_td >= '2026-08-21' THEN 'C_lag_up_to_2w'
    WHEN last_td >= '2026-08-04' THEN 'D_lag_up_to_1m'
    WHEN last_td >= '2026-06-04' THEN 'E_lag_1_3m'
    WHEN last_td >= '2025-09-04' THEN 'F_lag_3_12m'
    WHEN last_td >= '2023-09-04' THEN 'G_lag_1_3y_inside_window'
    ELSE 'H_last_bar_before_window_start'
  END AS bucket, COUNT(*) AS symbols, MIN(last_td) AS min_last, MAX(last_td) AS max_last
FROM per GROUP BY bucket ORDER BY bucket
""")

print("\n" + "=" * 100)
print("PART 7 - VIOLATION EXAMPLES / PROVENANCE")
print("=" * 100)

q(ops, "ops.ohlc_violation_examples", """
SELECT symbol, trade_date, open, high, low, close, volume, amount, source, quality_status,
       adjustment_mode, created_at, updated_at
FROM daily_bar_cache
WHERE high < low OR high < open OR high < close OR low > open OR low > close
ORDER BY trade_date DESC LIMIT 40
""")

q(ops, "ops.ohlc_violation_by_source", """
SELECT source, quality_status, adjustment_mode, COUNT(*) AS n, COUNT(DISTINCT symbol) AS symbols,
       MIN(trade_date) AS min_td, MAX(trade_date) AS max_td
FROM daily_bar_cache
WHERE high < low OR high < open OR high < close OR low > open OR low > close
GROUP BY source, quality_status, adjustment_mode ORDER BY n DESC LIMIT 30
""")

q(ops, "ops.close_le_zero_examples", """
SELECT symbol, trade_date, open, high, low, close, volume, amount, source, quality_status
FROM daily_bar_cache WHERE close <= 0 ORDER BY trade_date DESC LIMIT 30
""")

q(ops, "ops.zero_ohl_examples", """
SELECT symbol, trade_date, open, high, low, close, volume, amount, source, quality_status
FROM daily_bar_cache WHERE (open = 0 OR high = 0 OR low = 0) ORDER BY trade_date DESC LIMIT 30
""")

with open(r"D:\codex-A股交易\claude methods\_m1_evidence\integrity_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=1, default=str)
print("\n\nSAVED integrity_results.json")
