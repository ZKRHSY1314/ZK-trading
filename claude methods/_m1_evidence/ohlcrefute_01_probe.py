# -*- coding: utf-8 -*-
"""ADVERSARIAL VERIFY: symbol-spelling aliasing in trading_local.daily_bar_cache.
READ-ONLY. No writes. No migrations. No network."""
import sqlite3, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OPS = r"D:/codex-A股交易/trading_local.sqlite3"
HIS = r"D:/codex-A股交易/market_history.sqlite3"


def ro(p):
    c = sqlite3.connect("file:{}?mode=ro".format(p), uri=True)
    c.row_factory = sqlite3.Row
    return c


def show(title, sql, conn, params=()):
    print("\n" + "=" * 100)
    print("## " + title)
    print("SQL: " + " ".join(sql.split()))
    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception as exc:
        print("  ERROR: %r" % (exc,))
        return []
    if not rows:
        print("  (no rows)")
        return rows
    print("  cols: " + " | ".join(rows[0].keys()))
    for r in rows[:60]:
        print("  " + " | ".join("NULL" if v is None else str(v) for v in tuple(r)))
    if len(rows) > 60:
        print("  ... {} more rows".format(len(rows) - 60))
    return rows


ops = ro(OPS)
his = ro(HIS)

print("#" * 100)
print("# A. SPELLING LANDSCAPE  (is the '4 bare / 5563 prefixed' partition real and exhaustive?)")
print("#" * 100)

show("A1 length x charclass census of DISTINCT symbols", """
WITH s AS (SELECT DISTINCT symbol FROM daily_bar_cache)
SELECT LENGTH(symbol) AS len,
       CASE WHEN symbol GLOB '[0-9]*' THEN 'starts_digit' ELSE 'starts_alpha' END AS shape,
       CASE WHEN symbol = UPPER(symbol) THEN 'upper_or_num' ELSE 'has_lower' END AS casing,
       COUNT(*) AS distinct_symbols,
       MIN(symbol) AS ex_min, MAX(symbol) AS ex_max
FROM s GROUP BY 1,2,3 ORDER BY 1,2,3
""", ops)

show("A2 row census by the same partition (rows, not symbols)", """
SELECT LENGTH(symbol) AS len,
       CASE WHEN symbol GLOB '[0-9]*' THEN 'starts_digit' ELSE 'starts_alpha' END AS shape,
       COUNT(*) AS rows_, COUNT(DISTINCT symbol) AS syms,
       MIN(trade_date) AS min_d, MAX(trade_date) AS max_d
FROM daily_bar_cache GROUP BY 1,2 ORDER BY 1,2
""", ops)

show("A3 headline totals: distinct spellings / distinct collapsed codes / delta", """
SELECT (SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache) AS distinct_spellings,
       (SELECT COUNT(DISTINCT CASE WHEN LENGTH(symbol)=8 THEN substr(symbol,3) ELSE symbol END)
          FROM daily_bar_cache) AS distinct_collapsed_codes,
       (SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache)
     - (SELECT COUNT(DISTINCT CASE WHEN LENGTH(symbol)=8 THEN substr(symbol,3) ELSE symbol END)
          FROM daily_bar_cache) AS delta
""", ops)

show("A4 EVERY collapsed code mapping to >1 spelling -- full alias set, no assumptions", """
SELECT CASE WHEN LENGTH(symbol)=8 THEN substr(symbol,3) ELSE symbol END AS code,
       COUNT(DISTINCT symbol) AS n_spellings,
       GROUP_CONCAT(DISTINCT symbol) AS spellings
FROM daily_bar_cache
GROUP BY 1 HAVING COUNT(DISTINCT symbol) > 1
ORDER BY 1
""", ops)

show("A5 per-spelling detail for every symbol in an alias group", """
WITH multi AS (
  SELECT CASE WHEN LENGTH(symbol)=8 THEN substr(symbol,3) ELSE symbol END AS code
  FROM daily_bar_cache GROUP BY 1 HAVING COUNT(DISTINCT symbol) > 1)
SELECT symbol, COUNT(*) AS rows_, MIN(trade_date) AS min_d, MAX(trade_date) AS max_d,
       GROUP_CONCAT(DISTINCT source) AS sources,
       GROUP_CONCAT(DISTINCT quality_status) AS qs,
       GROUP_CONCAT(DISTINCT adjustment_mode) AS adjm,
       GROUP_CONCAT(DISTINCT volume_unit) AS vunit,
       MIN(created_at) AS min_created, MAX(created_at) AS max_created
FROM daily_bar_cache
WHERE (CASE WHEN LENGTH(symbol)=8 THEN substr(symbol,3) ELSE symbol END) IN (SELECT code FROM multi)
GROUP BY symbol ORDER BY symbol
""", ops)

print("\n" + "#" * 100)
print("# B. SEPARATE THE TWO PHENOMENA THE CLAIM MERGES")
print("#" * 100)

show("B1 bare 6-digit inventory", """
SELECT COUNT(DISTINCT symbol) AS n_bare_codes, COUNT(*) AS bare_rows
FROM daily_bar_cache WHERE LENGTH(symbol)=6
""", ops)

show("B2 prefix-only collisions (TWO DIFFERENT securities sharing one 6-digit code)", """
SELECT substr(symbol,3) AS code, COUNT(DISTINCT symbol) AS n_prefixed_spellings,
       GROUP_CONCAT(DISTINCT symbol) AS spellings
FROM daily_bar_cache WHERE LENGTH(symbol)=8
GROUP BY 1 HAVING COUNT(DISTINCT symbol) > 1 ORDER BY 1
""", ops)

show("B3 count of 6-digit codes shared by >1 PREFIXED symbol", """
SELECT COUNT(*) AS n_colliding_codes FROM (
  SELECT substr(symbol,3) FROM daily_bar_cache WHERE LENGTH(symbol)=8
  GROUP BY 1 HAVING COUNT(DISTINCT symbol) > 1)
""", ops)

print("\n" + "#" * 100)
print("# C. IS THE BARE '000001' REALLY AMBIGUOUS?  (data test, not a hand-wave)")
print("#" * 100)

show("C1 bare 000001 vs SZ000001 vs SH000001 -- exact-match counts + price scale", """
SELECT p.symbol AS candidate,
       COUNT(*) AS shared_dates,
       SUM(CASE WHEN b.close = p.close THEN 1 ELSE 0 END) AS close_exact_equal,
       SUM(CASE WHEN ABS(b.close-p.close) <= 0.005 THEN 1 ELSE 0 END) AS close_within_half_cent,
       ROUND(MAX(ABS(b.close-p.close)),4) AS max_abs_diff,
       ROUND(AVG(ABS(b.close-p.close)/NULLIF(p.close,0))*100,6) AS avg_pct_diff,
       ROUND(MIN(b.close),3) AS bare_close_min, ROUND(MAX(b.close),3) AS bare_close_max,
       ROUND(MIN(p.close),3) AS cand_close_min, ROUND(MAX(p.close),3) AS cand_close_max
FROM daily_bar_cache b JOIN daily_bar_cache p
  ON p.trade_date=b.trade_date AND p.symbol IN ('SZ000001','SH000001')
WHERE b.symbol='000001'
GROUP BY p.symbol
""", ops)

show("C2 volume/amount fingerprint for the same three series in the shadow window", """
SELECT symbol, COUNT(*) AS rows_,
       ROUND(AVG(close),3) AS avg_close, ROUND(AVG(volume),1) AS avg_volume,
       ROUND(AVG(amount),1) AS avg_amount
FROM daily_bar_cache WHERE symbol IN ('000001','SZ000001','SH000001')
  AND trade_date BETWEEN '2026-03-12' AND '2026-09-03'
GROUP BY symbol
""", ops)

show("C3 is SH000001 classified as an index in market_history.instruments?", """
SELECT symbol, exchange, asset_type, board, status, list_date, delist_date
FROM instruments WHERE symbol IN ('SH000001','SZ000001','000001','SH600519','600519',
  'SZ300750','300750','BJ920099','920099','SH920099','SZ920099')
ORDER BY symbol
""", his)

print("\n" + "#" * 100)
print("# D. FAITHFULNESS OF EVERY SHADOW SERIES (all OHLCV columns, not just close)")
print("#" * 100)

show("D1 bare vs same-code prefixed: full-column divergence", """
SELECT b.symbol AS bare, p.symbol AS prefixed, COUNT(*) AS shared_dates,
       MIN(b.trade_date) AS min_d, MAX(b.trade_date) AS max_d,
       SUM(CASE WHEN b.close  = p.close  THEN 1 ELSE 0 END) AS close_exact,
       SUM(CASE WHEN b.open   = p.open   THEN 1 ELSE 0 END) AS open_exact,
       SUM(CASE WHEN b.volume = p.volume THEN 1 ELSE 0 END) AS vol_exact,
       SUM(CASE WHEN b.amount = p.amount THEN 1 ELSE 0 END) AS amt_exact,
       ROUND(MAX(ABS(b.close-p.close)),4) AS max_close_diff,
       ROUND(MAX(ABS(b.close-p.close)/NULLIF(p.close,0))*100,5) AS max_pct_close_diff
FROM daily_bar_cache b JOIN daily_bar_cache p
  ON p.trade_date=b.trade_date AND LENGTH(p.symbol)=8 AND substr(p.symbol,3)=b.symbol
WHERE LENGTH(b.symbol)=6
GROUP BY b.symbol, p.symbol ORDER BY b.symbol, p.symbol
""", ops)

show("D2 date coverage asymmetry: dates present in the bare spelling only", """
WITH bare AS (SELECT symbol, trade_date FROM daily_bar_cache WHERE LENGTH(symbol)=6),
     pre  AS (SELECT substr(symbol,3) AS code, symbol AS psym, trade_date
              FROM daily_bar_cache WHERE LENGTH(symbol)=8)
SELECT b.symbol AS code,
       COUNT(*) AS bare_dates,
       SUM(CASE WHEN NOT EXISTS (SELECT 1 FROM pre WHERE pre.code=b.symbol
             AND pre.trade_date=b.trade_date) THEN 1 ELSE 0 END) AS bare_only_dates
FROM bare b GROUP BY b.symbol ORDER BY b.symbol
""", ops)

show("D3 first/last date of each spelling in every alias group", """
SELECT CASE WHEN LENGTH(symbol)=6 THEN symbol ELSE substr(symbol,3) END AS code,
       CASE WHEN LENGTH(symbol)=6 THEN 'bare' ELSE 'prefixed' END AS kind,
       symbol, MIN(trade_date) AS first_d, MAX(trade_date) AS last_d, COUNT(*) AS rows_
FROM daily_bar_cache
WHERE (CASE WHEN LENGTH(symbol)=6 THEN symbol ELSE substr(symbol,3) END)
      IN (SELECT DISTINCT symbol FROM daily_bar_cache WHERE LENGTH(symbol)=6)
GROUP BY symbol ORDER BY code, kind
""", ops)

print("\n" + "#" * 100)
print("# E. WINDOW / DENOMINATOR CHECKS + CROSS-DB CONTAMINATION CHECK")
print("#" * 100)

show("E1 are the shadow rows inside the fixed research window 2023-09-04..2026-09-04?", """
SELECT symbol, COUNT(*) AS total_rows,
       SUM(CASE WHEN trade_date BETWEEN '2023-09-04' AND '2026-09-04' THEN 1 ELSE 0 END) AS in_window,
       SUM(CASE WHEN trade_date < '2023-09-04' THEN 1 ELSE 0 END) AS before_window,
       SUM(CASE WHEN trade_date > '2026-09-04' THEN 1 ELSE 0 END) AS after_window,
       MIN(trade_date) AS min_d, MAX(trade_date) AS max_d
FROM daily_bar_cache WHERE LENGTH(symbol)=6 GROUP BY symbol
""", ops)

show("E2 does the SAME aliasing exist in market_history.daily_bars? (cross-db)", """
SELECT LENGTH(symbol) AS len, COUNT(DISTINCT symbol) AS syms, COUNT(*) AS rows_
FROM daily_bars GROUP BY 1 ORDER BY 1
""", his)

show("E3 market_history: any collapsed-code alias groups at all?", """
SELECT CASE WHEN LENGTH(symbol)=8 THEN substr(symbol,3) ELSE symbol END AS code,
       COUNT(DISTINCT symbol) AS n_spellings, GROUP_CONCAT(DISTINCT symbol) AS spellings
FROM daily_bars GROUP BY 1 HAVING COUNT(DISTINCT symbol)>1 ORDER BY 1 LIMIT 40
""", his)

show("E4 instruments: distinct spellings vs collapsed codes", """
SELECT COUNT(*) AS n_instruments,
       COUNT(DISTINCT symbol) AS distinct_spellings,
       COUNT(DISTINCT CASE WHEN LENGTH(symbol)=8 THEN substr(symbol,3) ELSE symbol END) AS collapsed_codes
FROM instruments
""", his)

print("\n" + "#" * 100)
print("# F. THE CLAIMED IMPACT: does anything actually request a bare symbol?")
print("#" * 100)

show("F1 spelling shape used by forecast_decisions", """
SELECT LENGTH(symbol) AS len, COUNT(*) AS rows_, COUNT(DISTINCT symbol) AS syms,
       MIN(symbol) AS ex_min, MAX(symbol) AS ex_max
FROM forecast_decisions GROUP BY 1 ORDER BY 1
""", ops)

show("F2 indices sitting in the cache as quality_status='ready' tradable rows", """
SELECT symbol, COUNT(*) AS rows_, GROUP_CONCAT(DISTINCT quality_status) AS qs,
       MIN(trade_date) AS min_d, MAX(trade_date) AS max_d
FROM daily_bar_cache
WHERE symbol IN ('SH000001','SH000300','SH000905','SZ399001','SZ399006')
GROUP BY symbol ORDER BY symbol
""", ops)

show("F3 how many cache symbols are indices per market_history.instruments?", """
SELECT asset_type, exchange, COUNT(*) AS n FROM instruments GROUP BY 1,2 ORDER BY 3 DESC LIMIT 25
""", his)

ops.close()
his.close()
print("\nDONE")
