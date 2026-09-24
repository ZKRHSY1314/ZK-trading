import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
con=sqlite3.connect("file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True)
con.execute("PRAGMA query_only=ON")
sql="""
WITH d AS (SELECT symbol, trade_date, close,
       LAG(close) OVER (PARTITION BY symbol ORDER BY trade_date) AS pc
   FROM daily_bar_cache
   WHERE trade_date BETWEEN '2024-08-05' AND '2024-08-20' AND quality_status='ready')
SELECT trade_date, COUNT(*) AS n,
       ROUND(AVG(close/pc-1.0),5) AS mean_xsec_ret,
       ROUND(SUM(CASE WHEN close/pc-1.0>0 THEN 1 ELSE 0 END)*1.0/COUNT(*),4) AS pct_up
FROM d WHERE pc>0 AND symbol NOT LIKE 'SH00%' GROUP BY 1 ORDER BY 1"""
print("SQL:"," ".join(sql.split()))
for r in con.execute(sql): print("   ",r)
sql2="""SELECT trade_date, close, ROUND(close/LAG(close) OVER (ORDER BY trade_date)-1.0,5) AS idx_ret
FROM daily_bar_cache WHERE symbol='SH000001' AND trade_date BETWEEN '2024-08-05' AND '2024-08-20' ORDER BY trade_date"""
print("\nSQL:"," ".join(sql2.split()))
for r in con.execute(sql2): print("   ",r)
con.close()
