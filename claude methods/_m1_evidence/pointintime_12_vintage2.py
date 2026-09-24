import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
TL=r"D:/codex-A股交易/trading_local.sqlite3"; MH=r"D:/codex-A股交易/market_history.sqlite3"
c=sqlite3.connect(f"file:{TL}?mode=ro",uri=True); c.execute("ATTACH DATABASE ? AS mh",(f"file:{MH}?mode=ro",))
syms=[r[0] for r in c.execute("SELECT DISTINCT symbol FROM mh.daily_bars WHERE substr(fetched_at,1,10)='2026-07-15' ORDER BY symbol LIMIT 300")]
ph=",".join("?"*len(syms))
SQL=f"""SELECT m.provider AS july_provider, b.source AS sept_source, COUNT(*) pairs,
 SUM(CASE WHEN ABS(b.close-m.close) > 0.001*ABS(m.close) THEN 1 ELSE 0 END) chg_gt_0p1pct,
 SUM(CASE WHEN ABS(b.close-m.close) > 0.01*ABS(m.close) THEN 1 ELSE 0 END) chg_gt_1pct
 FROM mh.daily_bars m JOIN main.daily_bar_cache b ON b.symbol=m.symbol AND b.trade_date=m.trade_date
 WHERE m.symbol IN ({ph}) AND substr(m.fetched_at,1,10)='2026-07-15' AND substr(b.updated_at,1,10)='2026-09-03'
 GROUP BY july_provider, sept_source ORDER BY pairs DESC"""
print("### J1 restatement split by provider pair -- separates RE-ADJUSTMENT from PROVIDER SWAP")
print("SQL:", " ".join(SQL.split()).replace(ph,"<300 symbols>"))
for r in c.execute(SQL,syms): print("   ", tuple(r))

SQL2=f"""SELECT COUNT(*) pairs,
 SUM(CASE WHEN ABS(b.close-m.close) > 0.001*ABS(m.close) THEN 1 ELSE 0 END) chg_gt_0p1pct,
 SUM(CASE WHEN ABS(b.close-m.close) > 0.01*ABS(m.close) THEN 1 ELSE 0 END) chg_gt_1pct
 FROM mh.daily_bars m JOIN main.daily_bar_cache b ON b.symbol=m.symbol AND b.trade_date=m.trade_date
 WHERE m.symbol IN ({ph}) AND substr(m.fetched_at,1,10)='2026-07-15' AND substr(b.updated_at,1,10)='2026-09-03'
   AND m.provider = b.source"""
print("\n### J2 SAME-PROVIDER-ONLY restatement (pure qfq re-adjustment, no provider swap)")
print("SQL:", " ".join(SQL2.split()).replace(ph,"<300 symbols>"))
print("   ", c.execute(SQL2,syms).fetchone())

SQL3=f"""SELECT m.symbol, COUNT(*) n, MIN(m.trade_date), MAX(m.trade_date),
  ROUND(AVG((b.close-m.close)/m.close)*100,4) avg_pct
 FROM mh.daily_bars m JOIN main.daily_bar_cache b ON b.symbol=m.symbol AND b.trade_date=m.trade_date
 WHERE m.symbol IN ({ph}) AND substr(m.fetched_at,1,10)='2026-07-15' AND substr(b.updated_at,1,10)='2026-09-03'
   AND m.provider=b.source AND ABS(b.close-m.close)>0.01*ABS(m.close)
 GROUP BY m.symbol ORDER BY n DESC LIMIT 10"""
print("\n### J3 same-provider symbols with >1% restated bars")
print("SQL:", " ".join(SQL3.split()).replace(ph,"<300 symbols>"))
for r in c.execute(SQL3,syms): print("   ", tuple(r))
c.close()
