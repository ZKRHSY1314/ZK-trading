import sqlite3
LOCAL = r"D:/codex-A股交易/trading_local.sqlite3"
MH    = r"D:/codex-A股交易/market_history.sqlite3"
W0, W1 = "2023-09-04", "2026-09-04"
c = sqlite3.connect(f"file:{LOCAL}?mode=ro", uri=True)
c.execute("ATTACH DATABASE ? AS mh", (f"file:{MH}?mode=ro",))

def q(label, sql, params=()):
    print("="*100); print(label); print("SQL:", " ".join(sql.split())); 
    for r in c.execute(sql, params).fetchall(): print("   ", r)

q("A1 source values + quality_status in window",
  """SELECT source, quality_status, COUNT(*) rows_, COUNT(DISTINCT symbol) syms,
            MIN(trade_date), MAX(trade_date)
     FROM daily_bar_cache
     WHERE trade_date BETWEEN ? AND ?
     GROUP BY source, quality_status ORDER BY rows_ DESC""", (W0,W1))

q("A2 adjustment_mode / volume_unit in window",
  """SELECT adjustment_mode, volume_unit, COUNT(*) FROM daily_bar_cache
     WHERE trade_date BETWEEN ? AND ? GROUP BY 1,2""", (W0,W1))

q("A3 distinct symbols in window (all vs quality ready)",
  """SELECT COUNT(DISTINCT symbol) all_syms,
            COUNT(DISTINCT CASE WHEN quality_status='ready' THEN symbol END) ready_syms
     FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ?""", (W0,W1))

q("A4 how many window cache symbols are INDEX per mh.instruments",
  """SELECT COALESCE(i.exchange,'<no-instrument-row>') ex, COALESCE(i.asset_type,'?') at_, COUNT(*) n
     FROM (SELECT DISTINCT symbol FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ?) d
     LEFT JOIN mh.instruments i ON i.symbol = d.symbol
     GROUP BY 1,2 ORDER BY n DESC""", (W0,W1))

q("A5 sample symbols per source",
  """SELECT source, MIN(symbol), MAX(symbol) FROM daily_bar_cache
     WHERE trade_date BETWEEN ? AND ? GROUP BY source""", (W0,W1))

q("A6 mh adjustment_mode coverage in window",
  """SELECT adjustment_mode, COUNT(*), COUNT(DISTINCT symbol) FROM mh.daily_bars
     WHERE trade_date BETWEEN ? AND ? GROUP BY 1""", (W0,W1))
