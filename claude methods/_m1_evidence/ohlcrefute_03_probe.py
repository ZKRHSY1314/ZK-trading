# -*- coding: utf-8 -*-
"""ADVERSARIAL VERIFY part 3: consumer-side reachability. READ-ONLY."""
import sqlite3, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OPS = r"D:/codex-A股交易/trading_local.sqlite3"


def ro(p):
    c = sqlite3.connect("file:{}?mode=ro".format(p), uri=True)
    c.row_factory = sqlite3.Row
    return c


def show(title, sql, conn, params=(), lim=40):
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
    for r in rows[:lim]:
        print("  " + " | ".join("NULL" if v is None else repr(v) for v in tuple(r)))
    if len(rows) > lim:
        print("  ... {} more rows".format(len(rows) - lim))
    return rows


ops = ro(OPS)

show("K1 forecast_decisions.subject spelling shape (scope=symbol rows are the securities)", """
SELECT scope, LENGTH(subject) AS len, COUNT(*) AS rows_, COUNT(DISTINCT subject) AS subjects,
       MIN(subject) AS ex_min, MAX(subject) AS ex_max
FROM forecast_decisions GROUP BY 1,2 ORDER BY 1,2
""", ops)

show("K2 any forecast subject spelled bare 6-digit that collides with the shadow set?", """
SELECT subject, COUNT(*) AS rows_, MIN(decision_cutoff) AS min_cut, MAX(decision_cutoff) AS max_cut
FROM forecast_decisions
WHERE subject IN ('000001','300750','600519','920099')
GROUP BY subject
""", ops)

show("K3 benchmark_symbol spellings actually used by persisted backtest runs", """
SELECT benchmark_symbol, COUNT(*) AS runs, MIN(start_date) AS min_s, MAX(end_date) AS max_e,
       GROUP_CONCAT(DISTINCT status) AS statuses
FROM historical_backtest_runs GROUP BY 1 ORDER BY 2 DESC
""", ops)

show("K4 do any persisted backtest configs name a bare 6-digit symbol?", """
SELECT id, data_source, start_date, end_date, status, substr(config_json,1,220) AS cfg
FROM historical_backtest_runs
WHERE config_json LIKE '%"000001"%' OR config_json LIKE '%"600519"%'
   OR config_json LIKE '%"300750"%' OR config_json LIKE '%"920099"%'
ORDER BY id
""", ops)

show("K5 every distinct source in the cache, with its spelling shape", """
SELECT source,
       SUM(CASE WHEN LENGTH(symbol)=6 THEN 1 ELSE 0 END) AS bare_rows,
       SUM(CASE WHEN LENGTH(symbol)=8 THEN 1 ELSE 0 END) AS prefixed_rows,
       COUNT(DISTINCT symbol) AS syms, COUNT(*) AS rows_,
       MIN(trade_date) AS min_d, MAX(trade_date) AS max_d
FROM daily_bar_cache GROUP BY source ORDER BY rows_ DESC
""", ops)

show("K6 which source wrote each bare row (the ingestion path that created the alias)", """
SELECT symbol, source, COUNT(*) AS rows_, MIN(trade_date) AS min_d, MAX(trade_date) AS max_d,
       MIN(created_at) AS min_created, MAX(updated_at) AS max_updated
FROM daily_bar_cache WHERE LENGTH(symbol)=6
GROUP BY symbol, source ORDER BY symbol, source
""", ops)

show("K7 same-source control: do prefixed rows from those sources exist in the same window?", """
SELECT symbol, source, COUNT(*) AS rows_, MIN(trade_date) AS min_d, MAX(trade_date) AS max_d
FROM daily_bar_cache
WHERE symbol IN ('SZ000001','SH600519','SZ300750','BJ920099')
  AND trade_date BETWEEN '2026-03-12' AND '2026-09-03'
GROUP BY symbol, source ORDER BY symbol, source
""", ops)

ops.close()
print("\nDONE")
