import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
op=ro(OP); mh=ro(MH)

print("### Q6  daily_bar_cache: all non-stock-shaped symbols (SH0* prefix and 6-char)")
q="""SELECT symbol, COUNT(*) n, MIN(trade_date) d0, MAX(trade_date) d1,
       COUNT(DISTINCT source) nsrc, group_concat(DISTINCT source) srcs,
       group_concat(DISTINCT adjustment_mode) adj, group_concat(DISTINCT volume_unit) vu,
       group_concat(DISTINCT quality_status) qs,
       SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) amt_null,
       SUM(CASE WHEN volume IS NULL THEN 1 ELSE 0 END) vol_null,
       MIN(created_at), MAX(updated_at)
FROM daily_bar_cache
WHERE symbol LIKE 'SH0%' OR length(symbol)<>8
GROUP BY symbol ORDER BY symbol"""
print("SQL:", q)
for r in op.execute(q): print("   ", r)

print("\n### Q7  sample rows for SH000300 / SH000001 / 6-char symbols")
for s in ('SH000300','SH000001','000001','600000','300001','920001'):
    rows = op.execute("SELECT symbol,trade_date,open,high,low,close,volume,amount,source,quality_status,adjustment_mode,volume_unit,created_at,updated_at FROM daily_bar_cache WHERE symbol=? ORDER BY trade_date LIMIT 2", (s,)).fetchall()
    rows += op.execute("SELECT symbol,trade_date,open,high,low,close,volume,amount,source,quality_status,adjustment_mode,volume_unit,created_at,updated_at FROM daily_bar_cache WHERE symbol=? ORDER BY trade_date DESC LIMIT 2", (s,)).fetchall()
    print(f"  --- {s}")
    for r in rows: print("     ", r)

print("\n### Q8  exact 6-char symbol list")
q="SELECT symbol, COUNT(*) FROM daily_bar_cache WHERE length(symbol)=6 GROUP BY symbol"
print("SQL:", q)
for r in op.execute(q): print("   ", r)

print("\n### Q9  global_market_bars full profile")
q="SELECT symbol, asset_class, source, quality_status, COUNT(*) n, MIN(bar_time), MAX(bar_time), MIN(available_at), MAX(available_at) FROM global_market_bars GROUP BY symbol, asset_class, source, quality_status ORDER BY symbol"
print("SQL:", q)
for r in op.execute(q): print("   ", r)
print("  sample rows:")
for r in op.execute("SELECT * FROM global_market_bars ORDER BY bar_time DESC LIMIT 5"): print("     ", r)
for r in op.execute("SELECT * FROM global_market_bars ORDER BY bar_time ASC LIMIT 3"): print("     ", r)
op.close(); mh.close()
