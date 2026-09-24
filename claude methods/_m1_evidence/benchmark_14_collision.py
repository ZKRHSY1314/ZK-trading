import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
op=ro(OP); mh=ro(MH)
q="SELECT symbol, COUNT(*), MIN(trade_date), MAX(trade_date), MIN(close), MAX(close) FROM daily_bar_cache WHERE symbol IN ('SZ000001','000001','SH000001') GROUP BY symbol"
print("SQL:", q)
for r in op.execute(q): print("   ", r)
print("  instruments name for SZ000001:", mh.execute("SELECT symbol,name,exchange,board FROM instruments WHERE symbol='SZ000001'").fetchall())
print("  is there an instruments row for SH000001/SH000300?:", mh.execute("SELECT symbol,name FROM instruments WHERE symbol IN ('SH000001','SH000300')").fetchall())
q2="SELECT COUNT(*) FROM daily_bar_cache WHERE symbol='000001' AND trade_date IN (SELECT trade_date FROM daily_bar_cache WHERE symbol='SH000001')"
print("SQL(overlapping dates between bare 000001 and SH000001):", q2, "->", op.execute(q2).fetchone()[0])
op.close(); mh.close()
