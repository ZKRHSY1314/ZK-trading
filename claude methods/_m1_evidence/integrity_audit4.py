# -*- coding: utf-8 -*-
"""READ-ONLY round 4: quantify ops-vs-hist close divergence; confirm zero-price crash path."""
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

conn = sqlite3.connect(uri(OPS), uri=True)
conn.row_factory = sqlite3.Row
conn.execute("ATTACH DATABASE ? AS mh", (uri(HIST),))

print("=" * 100)
print("PART J - QUANTIFY ops vs market_history CLOSE DIVERGENCE")
print("=" * 100)

q(conn, "x.divergence_pct", """
SELECT COUNT(*) AS common_rows,
       SUM(CASE WHEN ABS(d.close-b.close) > 0.005 THEN 1 ELSE 0 END) AS differs,
       ROUND(100.0*SUM(CASE WHEN ABS(d.close-b.close) > 0.005 THEN 1 ELSE 0 END)/COUNT(*),2) AS pct_differs,
       SUM(CASE WHEN ABS(d.close-b.close)/NULLIF(b.close,0) > 0.01 THEN 1 ELSE 0 END) AS differs_gt_1pct,
       ROUND(100.0*SUM(CASE WHEN ABS(d.close-b.close)/NULLIF(b.close,0) > 0.01 THEN 1 ELSE 0 END)/COUNT(*),2) AS pct_differs_gt_1pct,
       COUNT(DISTINCT CASE WHEN ABS(d.close-b.close) > 0.005 THEN d.symbol END) AS symbols_affected
FROM daily_bar_cache d
JOIN mh.daily_bars b ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
WHERE d.quality_status='ready' AND d.adjustment_mode='qfq'
""")

q(conn, "x.divergence_by_year", """
SELECT substr(d.trade_date,1,4) AS yr, COUNT(*) AS common_rows,
       SUM(CASE WHEN ABS(d.close-b.close) > 0.005 THEN 1 ELSE 0 END) AS differs,
       ROUND(100.0*SUM(CASE WHEN ABS(d.close-b.close) > 0.005 THEN 1 ELSE 0 END)/COUNT(*),2) AS pct
FROM daily_bar_cache d
JOIN mh.daily_bars b ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
WHERE d.quality_status='ready' AND d.adjustment_mode='qfq'
GROUP BY substr(d.trade_date,1,4) ORDER BY yr
""")

q(conn, "x.divergence_ratio_example_SZ000001", """
SELECT d.trade_date, d.close AS ops_close, b.close AS hist_close,
       ROUND(d.close/NULLIF(b.close,0), 6) AS ratio
FROM daily_bar_cache d
JOIN mh.daily_bars b ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
WHERE d.symbol='SZ000001' AND d.quality_status='ready'
  AND d.trade_date IN ('2024-06-24','2024-12-31','2025-06-30','2025-12-31','2026-06-30','2026-09-03')
ORDER BY d.trade_date
""")

q(conn, "x.divergence_ratio_spread_per_symbol", """
SELECT COUNT(*) AS symbols_checked,
       SUM(CASE WHEN ratio_spread < 0.0001 THEN 1 ELSE 0 END) AS symbols_with_constant_ratio,
       SUM(CASE WHEN ratio_spread >= 0.0001 THEN 1 ELSE 0 END) AS symbols_with_varying_ratio
FROM (
  SELECT d.symbol, MAX(d.close/NULLIF(b.close,0)) - MIN(d.close/NULLIF(b.close,0)) AS ratio_spread
  FROM daily_bar_cache d
  JOIN mh.daily_bars b ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
  WHERE d.quality_status='ready' AND d.adjustment_mode='qfq' AND b.close > 0
  GROUP BY d.symbol HAVING COUNT(*) > 20
)
""")

q(conn, "x.max_divergence_examples", """
SELECT d.symbol, d.trade_date, d.close AS ops_close, b.close AS hist_close,
       ROUND(ABS(d.close-b.close),4) AS abs_diff, d.source
FROM daily_bar_cache d
JOIN mh.daily_bars b ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
WHERE d.quality_status='ready' AND d.adjustment_mode='qfq'
ORDER BY ABS(d.close-b.close) DESC LIMIT 10
""")

print("\n" + "=" * 100)
print("PART K - ZERO-PRICE CRASH PATH (pure arithmetic, no DB writes)")
print("=" * 100)
alloc = 100000.0
buy_price = round(0.0 * (1 + 0.001), 4)
print("engine.py:231-233  reference_price = float(bar['open']) = 0.0")
print("                   buy_price = round(reference_price * (1 + slippage), 4) = %r" % buy_price)
try:
    qty = int(alloc / buy_price) // 100 * 100
    print("                   requested_qty =", qty)
except ZeroDivisionError as exc:
    print("                   int(alloc / buy_price) -> ZeroDivisionError: %s" % exc)
    results["zero_price_crash"] = {
        "sql": "N/A - pure python reproduction of engine.py:231-233 arithmetic",
        "rows": [{"buy_price": buy_price, "exception": "ZeroDivisionError: %s" % exc}],
    }

with open(r"D:\codex-A股交易\claude methods\_m1_evidence\integrity_results4.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=1, default=str)
print("\n\nSAVED integrity_results4.json")
