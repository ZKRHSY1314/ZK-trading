import sqlite3
OP=r"D:/codex-A股交易/trading_local.sqlite3"; MH=r"D:/codex-A股交易/market_history.sqlite3"
op=sqlite3.connect(f"file:{OP}?mode=ro",uri=True); op.row_factory=sqlite3.Row
print("--- daily_bar_cache quality_status ---")
for r in op.execute("SELECT quality_status,COUNT(*) n,COUNT(DISTINCT symbol) s FROM daily_bar_cache GROUP BY 1 ORDER BY 2 DESC").fetchall():
    print(f"  {r['quality_status']!r:<24} rows={r['n']:>9} sym={r['s']}")
print("--- symbol shape sample ---")
for r in op.execute("SELECT symbol,COUNT(*) n,MIN(trade_date),MAX(trade_date) FROM daily_bar_cache GROUP BY symbol ORDER BY symbol LIMIT 8").fetchall():
    print("  ",tuple(r))
print("  distinct symbols:", op.execute("SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache").fetchone()[0])
print("  symbol length hist:", [tuple(r) for r in op.execute("SELECT length(symbol),COUNT(DISTINCT symbol) FROM daily_bar_cache GROUP BY 1").fetchall()])
print("  prefixes:", [tuple(r) for r in op.execute("SELECT substr(symbol,1,2) p,COUNT(DISTINCT symbol) FROM daily_bar_cache GROUP BY 1 ORDER BY 2 DESC LIMIT 20").fetchall()])
print("--- symbol_fundamental_snapshot ---")
r=op.execute("SELECT COUNT(*) n,COUNT(DISTINCT symbol) s,COUNT(DISTINCT as_of) a,MIN(as_of),MAX(as_of),MIN(available_at),MAX(available_at),COUNT(DISTINCT source) FROM symbol_fundamental_snapshot").fetchone()
print("  ",tuple(r))
print("  as_of counts:", [tuple(x) for x in op.execute("SELECT as_of,COUNT(*) FROM symbol_fundamental_snapshot GROUP BY 1 ORDER BY 1").fetchall()])
print("  non-null pb:", op.execute("SELECT COUNT(*) FROM symbol_fundamental_snapshot WHERE pb IS NOT NULL AND pb>0").fetchone()[0],
      " non-null bvps:", op.execute("SELECT COUNT(*) FROM symbol_fundamental_snapshot WHERE book_value_per_share IS NOT NULL AND book_value_per_share>0").fetchone()[0],
      " non-null share:", op.execute("SELECT COUNT(*) FROM symbol_fundamental_snapshot WHERE total_share_billion IS NOT NULL AND total_share_billion>0").fetchone()[0])
print("--- trading dates in run windows (from daily_bar_cache) ---")
for (a,b,lbl) in [("2025-10-12","2026-06-09","run1"),("2025-06-17","2026-06-12","run13"),("2025-10-15","2026-06-12","run19")]:
    n=op.execute("SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ?",(a,b)).fetchone()[0]
    rows=op.execute("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ? AND quality_status='ready'",(a,b)).fetchone()[0]
    syms=op.execute("SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ? AND quality_status='ready'",(a,b)).fetchone()[0]
    print(f"  {lbl} {a}..{b}: dates={n} ready_rows={rows} ready_syms={syms}")
op.close()
mh=sqlite3.connect(f"file:{MH}?mode=ro",uri=True); mh.row_factory=sqlite3.Row
print("--- instruments exchange/asset_type ---")
for r in mh.execute("SELECT exchange,asset_type,COUNT(*) FROM instruments GROUP BY 1,2 ORDER BY 3 DESC").fetchall():
    print("  ",tuple(r))
mh.close()
