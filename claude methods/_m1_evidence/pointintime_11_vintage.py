import sqlite3, sys, time
sys.stdout.reconfigure(encoding='utf-8')
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
c.execute("ATTACH DATABASE ? AS mh", (f"file:{MH}?mode=ro",))
print("### I0 attached read-only; market_history rows fetched 2026-07-15 are the JULY vintage,")
print("###    the same (symbol,trade_date) in trading_local.daily_bar_cache was rewritten 2026-09-03 = SEPT vintage.")
syms=[r[0] for r in c.execute("SELECT DISTINCT symbol FROM mh.daily_bars WHERE substr(fetched_at,1,10)='2026-07-15' ORDER BY symbol LIMIT 300")]
print("sample symbols:", len(syms), syms[:5], "...")
ph=",".join("?"*len(syms))
SQL=f"""
SELECT COUNT(*) AS pairs,
       SUM(CASE WHEN ABS(b.close - m.close) > 1e-6 * MAX(ABS(m.close),1e-9) THEN 1 ELSE 0 END) AS close_changed,
       SUM(CASE WHEN ABS(b.close - m.close) > 0.01 * ABS(m.close) THEN 1 ELSE 0 END) AS close_changed_gt1pct,
       MAX(ABS(b.close - m.close) / MAX(ABS(m.close),1e-9)) AS max_rel_close_change,
       SUM(CASE WHEN ABS(COALESCE(b.volume,-1) - COALESCE(m.volume,-1)) > 1e-6 THEN 1 ELSE 0 END) AS volume_changed
FROM mh.daily_bars m
JOIN main.daily_bar_cache b ON b.symbol=m.symbol AND b.trade_date=m.trade_date
WHERE m.symbol IN ({ph}) AND substr(m.fetched_at,1,10)='2026-07-15'
  AND substr(b.updated_at,1,10)='2026-09-03'
"""
print("### I1 SQL:", " ".join(SQL.split()).replace(ph,"<300 symbol placeholders>"))
t=time.time(); print("   ", c.execute(SQL, syms).fetchone()); print(f"   [{time.time()-t:.1f}s]")

SQL2=f"""
SELECT m.symbol, m.trade_date, m.close AS july_close, b.close AS sept_close,
       ROUND((b.close-m.close)/m.close*100,3) AS pct_change
FROM mh.daily_bars m JOIN main.daily_bar_cache b ON b.symbol=m.symbol AND b.trade_date=m.trade_date
WHERE m.symbol IN ({ph}) AND substr(m.fetched_at,1,10)='2026-07-15'
  AND substr(b.updated_at,1,10)='2026-09-03'
  AND ABS(b.close-m.close) > 0.01*ABS(m.close)
ORDER BY ABS((b.close-m.close)/m.close) DESC LIMIT 15
"""
print("\n### I2 largest close restatements (July vintage vs Sept vintage), SQL:", " ".join(SQL2.split()).replace(ph,"<300 symbol placeholders>"))
for r in c.execute(SQL2, syms): print("   ", tuple(r))

SQL3=f"""SELECT COUNT(DISTINCT m.symbol) FROM mh.daily_bars m JOIN main.daily_bar_cache b
  ON b.symbol=m.symbol AND b.trade_date=m.trade_date
 WHERE m.symbol IN ({ph}) AND substr(m.fetched_at,1,10)='2026-07-15'
   AND substr(b.updated_at,1,10)='2026-09-03' AND ABS(b.close-m.close) > 0.001*ABS(m.close)"""
print("\n### I3 symbols (of 300 sampled) with >=0.1% close restatement somewhere in history")
print("SQL:", " ".join(SQL3.split()).replace(ph,"<300 symbol placeholders>"))
print("   ", c.execute(SQL3, syms).fetchone())
c.close()
