import sqlite3, os
OPS = r"D:/codex-A股交易/trading_local.sqlite3"
HIS = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{OPS}?mode=ro", uri=True)
c.execute("ATTACH DATABASE ? AS mh", (f"file:{HIS}?mode=ro",))
def q(label, sql, params=()):
    print("="*100); print(label); print("SQL:", " ".join(sql.split())); 
    try:
        rows = c.execute(sql, params).fetchall()
        for r in rows[:60]: print("   ", r)
        if len(rows) > 60: print(f"    ... {len(rows)} rows total")
    except Exception as e:
        print("    ERROR:", e)

q("A. daily_bar_cache totals + adjustment_mode census",
  "SELECT adjustment_mode, quality_status, COUNT(*), MIN(trade_date), MAX(trade_date), COUNT(DISTINCT symbol) FROM daily_bar_cache GROUP BY 1,2 ORDER BY 3 DESC")

q("B. mh.daily_bars adjustment_mode census",
  "SELECT adjustment_mode, quality_status, COUNT(*), MIN(trade_date), MAX(trade_date), COUNT(DISTINCT symbol) FROM mh.daily_bars GROUP BY 1,2 ORDER BY 3 DESC")

q("C. mh.daily_bars provider census",
  "SELECT provider, adjustment_mode, COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date), MAX(trade_date) FROM mh.daily_bars GROUP BY 1,2 ORDER BY 3 DESC")

q("D. daily_bar_cache source census",
  "SELECT source, adjustment_mode, COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date), MAX(trade_date) FROM daily_bar_cache GROUP BY 1,2 ORDER BY 3 DESC")

q("E. instruments exchange/asset_type census",
  "SELECT exchange, asset_type, COUNT(*) FROM mh.instruments GROUP BY 1,2 ORDER BY 3 DESC")
c.close()
