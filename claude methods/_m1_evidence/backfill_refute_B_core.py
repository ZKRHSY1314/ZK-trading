import sqlite3
MH = r"D:\codex-A股交易\market_history.sqlite3"
TL = r"D:\codex-A股交易\trading_local.sqlite3"
c = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)
c.execute("PRAGMA query_only=ON")

def q(label, sql, params=()):
    print("-"*78)
    print(label)
    print("SQL:", " ".join(sql.split()))
    for r in c.execute(sql, params):
        print("   ", r)

# ---------- 1. denominator decomposition ----------
q("1a. daily_bars rows by adjustment_mode, with amount-null split",
  """SELECT adjustment_mode, COUNT(*) rows,
            SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) amt_null,
            ROUND(100.0*SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END)/COUNT(*),3) pct_null
     FROM daily_bars GROUP BY adjustment_mode ORDER BY 2 DESC""")

q("1b. daily_bars: distinct (symbol,trade_date) cells vs raw rows",
  """SELECT COUNT(*) raw_rows, COUNT(DISTINCT symbol||'|'||trade_date) distinct_cells,
            COUNT(DISTINCT symbol) distinct_symbols FROM daily_bars""")

q("1c. amount-null rows by provider (is it really ALL tencent?)",
  """SELECT provider, COUNT(*) rows,
            SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) amt_null
     FROM daily_bars GROUP BY provider ORDER BY 2 DESC""")

# ---------- 2. indices vs stocks ----------
q("2a. amount-null split by instrument exchange (indices must not count as stocks)",
  """SELECT i.exchange, i.asset_type, COUNT(*) rows,
            SUM(CASE WHEN d.amount IS NULL THEN 1 ELSE 0 END) amt_null
     FROM daily_bars d JOIN instruments i ON i.symbol=d.symbol
     GROUP BY 1,2 ORDER BY 3 DESC""")

# ---------- 3. research window ----------
q("3a. amount-null inside vs outside research window 2023-09-04..2026-09-04",
  """SELECT CASE WHEN trade_date BETWEEN '2023-09-04' AND '2026-09-04'
                 THEN 'in_window' ELSE 'out_window' END w,
            MIN(trade_date), MAX(trade_date), COUNT(*) rows,
            SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) amt_null
     FROM daily_bars GROUP BY 1""")
c.close()

# ---------- 4. cache side ----------
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
c.execute("PRAGMA query_only=ON")
q("4a. cache rows by source x adjustment_mode x quality_status, amount nullity",
  """SELECT source, adjustment_mode, quality_status, COUNT(*) rows,
            SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) amt_null,
            SUM(CASE WHEN amount = 0 THEN 1 ELSE 0 END) amt_zero
     FROM daily_bar_cache GROUP BY 1,2,3 ORDER BY 4 DESC""")
q("4b. cache symbol format sample",
  """SELECT symbol, trade_date, close, volume, amount, source, adjustment_mode, volume_unit
     FROM daily_bar_cache LIMIT 5""")
c.close()
