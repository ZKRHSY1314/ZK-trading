import sqlite3, json
OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c
op = ro(OP)

def q(conn, sql, params=(), label=""):
    print("="*100)
    print("SQL:", " ".join(sql.split()))
    rows = conn.execute(sql, params).fetchall()
    for r in rows:
        print("   ", dict(r))
    print(f"   [{len(rows)} rows]")
    return rows

# ---- 1. The REAL risk set for ZeroDivisionError is open<=0, NOT relational OHLC violation.
q(op, """
SELECT
  COUNT(*) AS total_rows,
  SUM(CASE WHEN open IS NULL THEN 1 ELSE 0 END) AS open_null,
  SUM(CASE WHEN open = 0 THEN 1 ELSE 0 END) AS open_zero,
  SUM(CASE WHEN open < 0 THEN 1 ELSE 0 END) AS open_neg,
  SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) AS close_null,
  SUM(CASE WHEN close = 0 THEN 1 ELSE 0 END) AS close_zero,
  SUM(CASE WHEN high = 0 THEN 1 ELSE 0 END) AS high_zero,
  SUM(CASE WHEN low = 0 THEN 1 ELSE 0 END) AS low_zero,
  SUM(CASE WHEN open=0 AND high=0 AND low=0 AND close=0 THEN 1 ELSE 0 END) AS all_four_zero
FROM daily_bar_cache
""")

# ---- 2. open<=0 AND quality_status='ready' (the engine's ONLY filter) -- full breakdown
q(op, """
SELECT quality_status, COUNT(*) n, COUNT(DISTINCT symbol) syms, COUNT(DISTINCT trade_date) dates,
       MIN(trade_date) mn, MAX(trade_date) mx
FROM daily_bar_cache
WHERE open IS NOT NULL AND open <= 0
GROUP BY quality_status
""")

# ---- 3. Every row the engine could actually divide by zero on
q(op, """
SELECT symbol, trade_date, open, high, low, close, volume, amount, source,
       quality_status, adjustment_mode, volume_unit
FROM daily_bar_cache
WHERE quality_status = 'ready' AND open IS NOT NULL AND open <= 0
ORDER BY trade_date, symbol
""")

# ---- 4. Independent restatement of the relational-violation set (my own predicate,
#         including equality-tolerant and NULL-safe forms they may have missed)
q(op, """
SELECT COUNT(*) n, COUNT(DISTINCT symbol) syms, COUNT(DISTINCT trade_date) dates
FROM daily_bar_cache
WHERE open IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL AND close IS NOT NULL
  AND (high < low OR high < open OR high < close OR low > open OR low > close)
""")

# ---- 5. Do they overlap? relational-violating rows vs open<=0 rows
q(op, """
SELECT
  SUM(CASE WHEN viol=1 AND zero=1 THEN 1 ELSE 0 END) AS both,
  SUM(CASE WHEN viol=1 AND zero=0 THEN 1 ELSE 0 END) AS viol_only,
  SUM(CASE WHEN viol=0 AND zero=1 THEN 1 ELSE 0 END) AS zero_only
FROM (
  SELECT
    CASE WHEN open IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL AND close IS NOT NULL
          AND (high<low OR high<open OR high<close OR low>open OR low>close) THEN 1 ELSE 0 END AS viol,
    CASE WHEN open IS NOT NULL AND open<=0 THEN 1 ELSE 0 END AS zero
  FROM daily_bar_cache
)
""")

# ---- 6. Also NULL-open rows: dropna removes them, but do they exist under 'ready'?
q(op, """
SELECT quality_status, COUNT(*) n, COUNT(DISTINCT symbol) syms
FROM daily_bar_cache
WHERE open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL
GROUP BY quality_status
""")

# ---- 7. quality_status value distribution (is 'ready' even the dominant value?)
q(op, """
SELECT quality_status, COUNT(*) n FROM daily_bar_cache GROUP BY quality_status ORDER BY n DESC
""")

# ---- 8. Are the 3 symbols stocks or indices? check symbol shape + instruments in market_history
q(op, """
SELECT symbol, COUNT(*) bars, MIN(trade_date) first_bar, MAX(trade_date) last_bar
FROM daily_bar_cache
WHERE symbol IN ('SH688089','SH688143','SH688173')
GROUP BY symbol
""")

mh = ro(MH)
q(mh, """
SELECT symbol, name, exchange, asset_type, board, status, list_date, delist_date
FROM instruments WHERE symbol IN ('SH688089','SH688143','SH688173')
""")

# ---- 9. Is the same (symbol,trade_date) present in market_history?
q(mh, """
SELECT symbol, trade_date, adjustment_mode, open, high, low, close, volume, amount, quality_status
FROM daily_bars
WHERE symbol IN ('SH688089','SH688143','SH688173') AND trade_date BETWEEN '2024-11-04' AND '2024-11-08'
ORDER BY symbol, trade_date, adjustment_mode
""")

# ---- 10. Do these symbols have a PRIOR-day bar (needed to become an entry candidate)?
q(op, """
SELECT symbol, trade_date, open, high, low, close, volume, amount, quality_status
FROM daily_bar_cache
WHERE symbol IN ('SH688089','SH688143','SH688173') AND trade_date BETWEEN '2024-11-01' AND '2024-11-11'
ORDER BY symbol, trade_date
""")
