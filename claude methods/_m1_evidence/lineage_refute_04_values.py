import sqlite3
CACHE = r"D:/codex-A股交易/trading_local.sqlite3"
HIST  = r"D:/codex-A股交易/market_history.sqlite3"
con = sqlite3.connect(f"file:{HIST}?mode=ro", uri=True)
con.execute("ATTACH DATABASE ? AS cache", (f"file:{CACHE}?mode=ro",))
con.row_factory = sqlite3.Row
print("=== value/provenance fidelity of overlapping rows ===", flush=True)
SQL = """
SELECT COUNT(*)                                                   AS overlap_rows,
       SUM(CASE WHEN b.provider IS NOT c.source THEN 1 ELSE 0 END) AS provider_differs,
       SUM(CASE WHEN ROUND(b.close,6) IS NOT ROUND(c.close,6) THEN 1 ELSE 0 END) AS close_differs,
       SUM(CASE WHEN ROUND(b.open,6)  IS NOT ROUND(c.open,6)  THEN 1 ELSE 0 END) AS open_differs,
       SUM(CASE WHEN ROUND(b.volume,6) IS NOT ROUND(c.volume,6) THEN 1 ELSE 0 END) AS volume_differs,
       SUM(CASE WHEN b.amount IS NULL AND c.amount IS NOT NULL THEN 1 ELSE 0 END) AS amount_lost,
       SUM(CASE WHEN b.volume_unit IS NOT c.volume_unit THEN 1 ELSE 0 END) AS volume_unit_differs,
       SUM(CASE WHEN b.available_at IS NOT c.updated_at THEN 1 ELSE 0 END) AS available_at_not_cache_updated_at
FROM main.daily_bars b
JOIN cache.daily_bar_cache c
  ON c.symbol=b.symbol AND c.trade_date=b.trade_date
"""
print("SQL:", " ".join(SQL.split()), flush=True)
for r in con.execute(SQL).fetchall():
    print("   ", dict(r), flush=True)
con.close()
