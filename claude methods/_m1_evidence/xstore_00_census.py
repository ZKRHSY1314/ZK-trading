import sqlite3, sys
OPS = r"D:/codex-A股交易/trading_local.sqlite3"
HIST= r"D:/codex-A股交易/market_history.sqlite3"
con = sqlite3.connect(f"file:{OPS}?mode=ro", uri=True)
con.execute(f"ATTACH DATABASE 'file:{HIST}?mode=ro' AS mh")
def q(label, sql, args=()):
    print("="*100); print(label); print("SQL:", " ".join(sql.split())); 
    cur=con.execute(sql,args); cols=[d[0] for d in cur.description]
    rows=cur.fetchall()
    print(" | ".join(cols))
    for r in rows[:60]: print(" | ".join("" if v is None else str(v) for v in r))
    if len(rows)>60: print(f"... ({len(rows)} rows)")
    print()

q("A1 ops daily_bar_cache: rows by adjustment_mode x quality_status",
  "SELECT adjustment_mode, quality_status, COUNT(*) n, MIN(trade_date) mn, MAX(trade_date) mx FROM daily_bar_cache GROUP BY 1,2 ORDER BY n DESC")

q("A2 hist daily_bars: rows by adjustment_mode x quality_status",
  "SELECT adjustment_mode, quality_status, COUNT(*) n, MIN(trade_date) mn, MAX(trade_date) mx FROM mh.daily_bars GROUP BY 1,2 ORDER BY n DESC")

q("A3 ops distinct symbols / hist distinct symbols",
  """SELECT (SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache) ops_syms,
            (SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE quality_status='ready' AND adjustment_mode='qfq') ops_syms_ready_qfq,
            (SELECT COUNT(DISTINCT symbol) FROM mh.daily_bars) hist_syms,
            (SELECT COUNT(DISTINCT symbol) FROM mh.daily_bars WHERE adjustment_mode='qfq') hist_syms_qfq""")

q("A4 hist instruments: exchange/asset_type census",
  "SELECT exchange, asset_type, COUNT(*) n FROM mh.instruments GROUP BY 1,2 ORDER BY n DESC")

q("A5 ops cache: source census (top 25)",
  "SELECT source, COUNT(*) n, MIN(trade_date) mn, MAX(trade_date) mx FROM daily_bar_cache GROUP BY 1 ORDER BY n DESC LIMIT 25")

q("A6 hist daily_bars provider census",
  "SELECT provider, COUNT(*) n, MIN(trade_date) mn, MAX(trade_date) mx, MIN(fetched_at) fmin, MAX(fetched_at) fmax FROM mh.daily_bars GROUP BY 1 ORDER BY n DESC LIMIT 25")

q("A7 last trade_date per store (global anchor check)",
  """SELECT (SELECT MAX(trade_date) FROM daily_bar_cache WHERE quality_status='ready' AND adjustment_mode='qfq') ops_max,
            (SELECT MAX(trade_date) FROM mh.daily_bars WHERE adjustment_mode='qfq') hist_max,
            (SELECT MIN(trade_date) FROM daily_bar_cache WHERE quality_status='ready' AND adjustment_mode='qfq') ops_min,
            (SELECT MIN(trade_date) FROM mh.daily_bars WHERE adjustment_mode='qfq') hist_min""")
con.close()
