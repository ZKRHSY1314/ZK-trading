# -*- coding: utf-8 -*-
"""READ-ONLY round 3: CHECK provenance, rejected-row footprint, engine consequence."""
import sqlite3, sys, json, io, urllib.parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

OPS = r"D:\codex-A股交易\trading_local.sqlite3"
HIST = r"D:\codex-A股交易\market_history.sqlite3"

def uri(p):
    return "file:" + urllib.parse.quote(p.replace("\\", "/")) + "?mode=ro"

results = {}

def q(conn, name, sql, params=()):
    cur = conn.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    results[name] = {"sql": " ".join(sql.split()), "rows": rows}
    print("\n### %s" % name)
    print("SQL: %s" % " ".join(sql.split()))
    for r in rows[:40]:
        print("   ", r)
    if len(rows) > 40:
        print("    ... (%d rows total)" % len(rows))
    return rows

hist = sqlite3.connect(uri(HIST), uri=True)
hist.row_factory = sqlite3.Row

print("=" * 100)
print("PART G - market_history CHECK PROVENANCE")
print("=" * 100)

q(hist, "hist.schema_metadata", "SELECT * FROM schema_metadata")
q(hist, "hist.688173_dates_around", """
SELECT symbol, trade_date, open, high, low, close, volume, amount, provider
FROM daily_bars WHERE symbol='SH688173' AND trade_date BETWEEN '2024-11-01' AND '2024-11-12'
ORDER BY trade_date
""")
q(hist, "hist.688173_total", """
SELECT COUNT(*) AS n, MIN(trade_date) AS min_td, MAX(trade_date) AS max_td
FROM daily_bars WHERE symbol='SH688173'
""")
q(hist, "hist.688143_688089_on_date", """
SELECT symbol, COUNT(*) AS n,
       SUM(CASE WHEN trade_date='2024-11-06' THEN 1 ELSE 0 END) AS has_2024_11_06
FROM daily_bars WHERE symbol IN ('SH688143','SH688089') GROUP BY symbol
""")
q(hist, "hist.rows_on_2024_11_06", """
SELECT COUNT(*) AS symbols_with_bar FROM daily_bars WHERE trade_date='2024-11-06'
""")
q(hist, "hist.instrument_bj920289", """
SELECT symbol, list_date, delist_date, status, exchange, asset_type, board
FROM instruments WHERE symbol='BJ920289'
""")
q(hist, "hist.bar_quality_issues_count", "SELECT COUNT(*) AS n FROM bar_quality_issues")

print("\n" + "=" * 100)
print("PART H - CROSS-DB: rows present in ops-ready but absent from market_history")
print("=" * 100)

conn = sqlite3.connect(uri(OPS), uri=True)
conn.row_factory = sqlite3.Row
conn.execute("ATTACH DATABASE ? AS mh", (uri(HIST),))

q(conn, "x.ops_ready_not_in_hist", """
SELECT COUNT(*) AS n_ops_ready_rows_absent_from_market_history
FROM daily_bar_cache d
WHERE d.quality_status='ready'
  AND d.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
  AND NOT EXISTS (
    SELECT 1 FROM mh.daily_bars b
    WHERE b.symbol = d.symbol AND b.trade_date = d.trade_date AND b.adjustment_mode='qfq'
  )
""")

q(conn, "x.hist_not_in_ops", """
SELECT COUNT(*) AS n_hist_rows_absent_from_ops
FROM mh.daily_bars b
WHERE b.adjustment_mode='qfq'
  AND NOT EXISTS (
    SELECT 1 FROM daily_bar_cache d WHERE d.symbol = b.symbol AND d.trade_date = b.trade_date
  )
""")

q(conn, "x.the_three_bad_rows_in_hist", """
SELECT d.symbol, d.trade_date,
       (SELECT COUNT(*) FROM mh.daily_bars b WHERE b.symbol=d.symbol AND b.trade_date=d.trade_date) AS in_hist
FROM daily_bar_cache d
WHERE d.high < d.low OR d.high < d.open OR d.high < d.close OR d.low > d.open OR d.low > d.close
""")

q(conn, "x.zero_volume_rows_in_hist", """
SELECT d.symbol, d.trade_date, d.volume AS ops_volume, d.amount AS ops_amount,
       b.volume AS hist_volume, b.amount AS hist_amount
FROM daily_bar_cache d
LEFT JOIN mh.daily_bars b ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
WHERE d.volume = 0
ORDER BY d.trade_date DESC
""")

q(conn, "x.close_divergence_ops_vs_hist", """
SELECT COUNT(*) AS common_rows,
       SUM(CASE WHEN ABS(d.close - b.close) > 0.005 THEN 1 ELSE 0 END) AS close_differs_gt_half_cent,
       ROUND(MAX(ABS(d.close - b.close)),4) AS max_abs_close_diff
FROM daily_bar_cache d
JOIN mh.daily_bars b ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
WHERE d.quality_status='ready'
""")

print("\n" + "=" * 100)
print("PART I - LAST-SESSION COMPLETENESS")
print("=" * 100)

q(conn, "ops.last_session_partial", """
SELECT trade_date, COUNT(DISTINCT symbol) AS symbols,
       SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) AS amount_null,
       GROUP_CONCAT(DISTINCT source) AS sources
FROM daily_bar_cache WHERE trade_date IN ('2026-09-04','2026-09-03')
GROUP BY trade_date
""")

q(conn, "ops.symbols_missing_last_full_session", """
SELECT COUNT(*) AS symbols_without_2026_09_03_bar FROM (
  SELECT DISTINCT symbol FROM daily_bar_cache WHERE quality_status='ready'
  EXCEPT
  SELECT symbol FROM daily_bar_cache WHERE trade_date='2026-09-03'
)
""")

with open(r"D:\codex-A股交易\claude methods\_m1_evidence\integrity_results3.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=1, default=str)
print("\n\nSAVED integrity_results3.json")
