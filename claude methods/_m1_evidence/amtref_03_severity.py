import sqlite3, statistics
H=r"D:/codex-A股交易/market_history.sqlite3"
C=r"D:/codex-A股交易/trading_local.sqlite3"
con=sqlite3.connect(f"file:{H}?mode=ro",uri=True)
con.execute("ATTACH DATABASE ? AS cache", (f"file:{C}?mode=ro",))
def q(label,sql,p=()):
    print("\n### "+label); print("SQL:",' '.join(sql.split()))
    rows=con.execute(sql,p).fetchall()
    for r in rows[:30]: print("   ",r)
    if len(rows)>30: print("    ...",len(rows),"rows")
    return rows

q("C1 hist NULL-amount by year-month (temporal shape)",
 """SELECT substr(trade_date,1,7) ym, COUNT(*) n, SUM(amount IS NULL) nulls,
     ROUND(100.0*SUM(amount IS NULL)/COUNT(*),1) pct
     FROM daily_bars GROUP BY 1 ORDER BY 1""")

q("C2 cache volume_unit mix",
 "SELECT volume_unit, COUNT(*) FROM cache.daily_bar_cache GROUP BY 1")

# PROXY ACCURACY on ground truth: rows where amount IS present, apply execution.py formula
q("C3 proxy/actual ratio distribution (cache rows with real amount, volume in hand)",
 """WITH t AS (
      SELECT (volume*100.0*((high+low+close)/3.0))/amount AS r
      FROM cache.daily_bar_cache
      WHERE amount>0 AND volume>0 AND high>0 AND low>0 AND close>0
        AND volume_unit='hand' AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
    )
    SELECT COUNT(*) n,
      ROUND(MIN(r),4) mn, ROUND(AVG(r),4) mean, ROUND(MAX(r),4) mx,
      SUM(r<0.8) lt80pct, SUM(r>1.25) gt125pct
    FROM t""")

q("C3b proxy ratio percentiles",
 """WITH t AS (
      SELECT (volume*100.0*((high+low+close)/3.0))/amount AS r
      FROM cache.daily_bar_cache
      WHERE amount>0 AND volume>0 AND high>0 AND low>0 AND close>0 AND volume_unit='hand'
      ORDER BY r
    ), c AS (SELECT COUNT(*) n FROM t)
    SELECT 'p01',(SELECT ROUND(r,4) FROM t LIMIT 1 OFFSET (SELECT n/100 FROM c))
    UNION ALL SELECT 'p25',(SELECT ROUND(r,4) FROM t LIMIT 1 OFFSET (SELECT n/4 FROM c))
    UNION ALL SELECT 'p50',(SELECT ROUND(r,4) FROM t LIMIT 1 OFFSET (SELECT n/2 FROM c))
    UNION ALL SELECT 'p75',(SELECT ROUND(r,4) FROM t LIMIT 1 OFFSET (SELECT 3*n/4 FROM c))
    UNION ALL SELECT 'p99',(SELECT ROUND(r,4) FROM t LIMIT 1 OFFSET (SELECT 99*n/100 FROM c))""")

q("C4 the 'ERROR' trade_date rows in cache",
 """SELECT trade_date, COUNT(*) FROM cache.daily_bar_cache
    WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' GROUP BY 1""")

q("C5 does hist cover the stated research window start 2023-09-04?",
 """SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM daily_bars WHERE trade_date<'2024-04-09'""")
con.close()
