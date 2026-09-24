# -*- coding: utf-8 -*-
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
TL = r"D:/codex-A股交易/trading_local.sqlite3"; MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
t = ro(TL)
W0,W1 = "2023-09-04","2026-09-04"

print("### Q. Exact leading/trailing benchmark gap vs stock calendar (window)")
q = (f"SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN '{W0}' AND '2024-06-18' AND symbol LIKE 'SH6%'")
print("  SQL:", q, "-> stock trading days BEFORE first index bar =", t.execute(q).fetchone()[0])
q = (f"SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN '2026-09-03' AND '{W1}' AND symbol LIKE 'SH6%'")
print("  SQL:", q, "-> stock trading days AFTER last index bar =", t.execute(q).fetchone()[0])
q = (f"SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN '{W0}' AND '{W1}' AND symbol LIKE 'SH6%' "
     f"AND trade_date NOT IN (SELECT trade_date FROM daily_bar_cache WHERE symbol='SH000300')")
print("  SQL:", q, "-> stock trading days with NO CSI300 bar =", t.execute(q).fetchone()[0])

print("\n### R. Ambiguous/malformed bare symbols in daily_bar_cache (prefix-less)")
q = ("SELECT symbol, COUNT(*), MIN(trade_date), MAX(trade_date), source FROM daily_bar_cache "
     "WHERE symbol NOT LIKE 'SH%' AND symbol NOT LIKE 'SZ%' AND symbol NOT LIKE 'BJ%' GROUP BY symbol, source")
print("  SQL:", q)
for r in t.execute(q).fetchall(): print("      ", r)

print("\n### S. Sanity: is SH000300 series economically real? (CSI300 level + a return)")
q = "SELECT trade_date, close FROM daily_bar_cache WHERE symbol='SH000300' ORDER BY trade_date"
rows = t.execute(q).fetchall()
print("      first:", rows[0], " last:", rows[-1], f" total_return={(rows[-1][1]/rows[0][1]-1):+.2%}")

print("\n### T. Control: same index symbols in market_history? (the disputed store)")
m = ro(MH)
q = "SELECT COUNT(*) FROM daily_bars WHERE symbol IN ('SH000001','SH000300','SZ399001','SZ399006','BJ899050')"
print("  SQL:", q, "->", m.execute(q).fetchone()[0])
q = "SELECT COUNT(*) FROM instruments WHERE symbol IN ('SH000001','SH000300')"
print("  SQL:", q, "->", m.execute(q).fetchone()[0])
m.close(); t.close()
