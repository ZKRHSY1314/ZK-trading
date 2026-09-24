import sqlite3, textwrap
MH = 'file:D:/codex-A股交易/market_history.sqlite3?mode=ro'
c = sqlite3.connect(MH, uri=True); c.row_factory = sqlite3.Row
def q(label, sql, params=()):
    print('='*78); print(label); print(textwrap.dedent(sql).strip()); print('-'*78)
    for r in c.execute(sql, params): print(dict(r))
    print()

# B1: index contamination -- how many daily_bars symbols are NOT stocks?
q('B1 instrument-class census of daily_bars symbols (never count indices as stocks)', """
SELECT i.exchange, i.asset_type, COUNT(DISTINCT b.symbol) syms, COUNT(*) rows
FROM daily_bars b LEFT JOIN instruments i ON i.symbol = b.symbol
GROUP BY 1,2 ORDER BY rows DESC
""")

# B2: STOCKS ONLY, distinct-security denominator. Does the alias hold per security?
q('B2 STOCKS ONLY (exchange IN SH,SZ,BJ): per-security divergence of available_at vs fetched_at', """
SELECT COUNT(DISTINCT b.symbol) AS stock_syms,
       COUNT(*) AS stock_rows,
       COUNT(DISTINCT CASE WHEN b.available_at IS NOT b.fetched_at THEN b.symbol END) AS syms_with_any_divergence,
       SUM(CASE WHEN b.available_at IS NOT b.fetched_at THEN 1 ELSE 0 END) AS rows_diverging
FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
WHERE i.exchange IN ('SH','SZ','BJ')
""")

# B3: LEAKAGE DIRECTION -- is any bar marked knowable BEFORE its own trade_date?
q('B3 sign of (available_at_date - trade_date), stocks only, julianday not string math', """
SELECT CASE
         WHEN julianday(substr(b.available_at,1,10)) < julianday(b.trade_date) THEN 'NEGATIVE (leak: knowable before it traded)'
         WHEN julianday(substr(b.available_at,1,10)) = julianday(b.trade_date) THEN 'ZERO (same calendar day)'
         WHEN julianday(substr(b.available_at,1,10)) - julianday(b.trade_date) <= 7   THEN '1..7 days'
         WHEN julianday(substr(b.available_at,1,10)) - julianday(b.trade_date) <= 365 THEN '8..365 days'
         ELSE '>365 days' END AS lag_bucket,
       COUNT(*) n,
       ROUND(100.0*COUNT(*)/(SELECT COUNT(*) FROM daily_bars b2 JOIN instruments i2 ON i2.symbol=b2.symbol
                             WHERE i2.exchange IN ('SH','SZ','BJ')),4) AS pct_of_stock_rows,
       COUNT(DISTINCT b.symbol) syms
FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
WHERE i.exchange IN ('SH','SZ','BJ')
GROUP BY 1 ORDER BY n DESC
""")

# B4: same-day rows -- is the intraday time plausible (after 15:00 CST close)?
q('B4 for lag==0 stock rows, hour-of-day of available_at (plausible only if >=15:00)', """
SELECT CAST(substr(b.available_at,12,2) AS INT) AS hh, COUNT(*) n, COUNT(DISTINCT b.trade_date) tds
FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
WHERE i.exchange IN ('SH','SZ','BJ')
  AND substr(b.available_at,1,10) = b.trade_date
GROUP BY 1 ORDER BY hh
""")
c.close()
