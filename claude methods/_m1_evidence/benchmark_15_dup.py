import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
OP = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
op=ro(OP)
q="""SELECT COUNT(*) shared_dates,
  SUM(CASE WHEN a.close = b.close THEN 1 ELSE 0 END) same_close,
  SUM(CASE WHEN a.close <> b.close THEN 1 ELSE 0 END) diff_close
FROM daily_bar_cache a JOIN daily_bar_cache b
  ON a.trade_date = b.trade_date AND a.symbol='000001' AND b.symbol='SZ000001'"""
print("SQL:", q.replace("\n"," "))
print("   ", op.execute(q).fetchone())
q2="""SELECT COUNT(*) FROM (
 SELECT substr(symbol,3) AS core FROM daily_bar_cache WHERE length(symbol)=8 GROUP BY core
 INTERSECT SELECT symbol FROM daily_bar_cache WHERE length(symbol)=6 GROUP BY symbol)"""
print("SQL(6-char symbols that duplicate an 8-char instrument):", q2.replace("\n"," "))
print("   ", op.execute(q2).fetchone())
op.close()
