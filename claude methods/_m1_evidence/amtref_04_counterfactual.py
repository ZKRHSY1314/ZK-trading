import sqlite3
H=r"D:/codex-A股交易/market_history.sqlite3"
C=r"D:/codex-A股交易/trading_local.sqlite3"
con=sqlite3.connect(f"file:{H}?mode=ro",uri=True)
con.execute("ATTACH DATABASE ? AS cache", (f"file:{C}?mode=ro",))
def q(label,sql,p=()):
    print("\n### "+label); print("SQL:",' '.join(sql.split()))
    rows=con.execute(sql,p).fetchall()
    for r in rows[:30]: print("   ",r)
    return rows

# EXACT counterfactual: on the 1,652,094 bars that would lose amount, how wrong is
# the proxy the engine would compute from market_history's OWN volume/high/low/close,
# measured against the cache's real amount for the same (symbol, trade_date)?
q("D1 proxy-vs-truth on the exact bars that would regress",
 """WITH t AS (
      SELECT (b.volume*100.0*((b.high+b.low+b.close)/3.0))/c.amount AS r
      FROM daily_bars b
      JOIN cache.daily_bar_cache c ON c.symbol=b.symbol AND c.trade_date=b.trade_date
      WHERE (b.amount IS NULL OR b.amount<=0) AND c.amount>0
        AND b.volume>0 AND b.high>0 AND b.low>0 AND b.close>0
    )
    SELECT COUNT(*) n, ROUND(AVG(r),4) mean, ROUND(MIN(r),4) mn, ROUND(MAX(r),4) mx,
      SUM(r<0.5) lt50, SUM(r<0.8) lt80, SUM(r BETWEEN 0.8 AND 1.25) within25, SUM(r>1.25) gt125
    FROM t""")

q("D2 percentiles of that ratio",
 """WITH t AS (
      SELECT (b.volume*100.0*((b.high+b.low+b.close)/3.0))/c.amount AS r
      FROM daily_bars b JOIN cache.daily_bar_cache c ON c.symbol=b.symbol AND c.trade_date=b.trade_date
      WHERE (b.amount IS NULL OR b.amount<=0) AND c.amount>0 AND b.volume>0 AND b.close>0
      ORDER BY r
    ), n AS (SELECT COUNT(*) k FROM t)
    SELECT 'p01',(SELECT ROUND(r,4) FROM t LIMIT 1 OFFSET (SELECT k/100 FROM n))
    UNION ALL SELECT 'p10',(SELECT ROUND(r,4) FROM t LIMIT 1 OFFSET (SELECT k/10 FROM n))
    UNION ALL SELECT 'p50',(SELECT ROUND(r,4) FROM t LIMIT 1 OFFSET (SELECT k/2 FROM n))
    UNION ALL SELECT 'p90',(SELECT ROUND(r,4) FROM t LIMIT 1 OFFSET (SELECT 9*k/10 FROM n))
    UNION ALL SELECT 'p99',(SELECT ROUND(r,4) FROM t LIMIT 1 OFFSET (SELECT 99*k/100 FROM n))""")

# Is the regression segment time-bounded? split the 1.65M by era
q("D3 regressing bars (hist null, cache ok) by year-month",
 """SELECT substr(b.trade_date,1,7) ym, COUNT(*) regress
    FROM daily_bars b JOIN cache.daily_bar_cache c ON c.symbol=b.symbol AND c.trade_date=b.trade_date
    WHERE (b.amount IS NULL OR b.amount<=0) AND c.amount>0
    GROUP BY 1 ORDER BY 1""")

# Confirm the reverse direction is truly zero under MY definition (usable, not just NOT NULL)
q("D4 rows where hist is BETTER than cache (usable definition)",
 """SELECT COUNT(*) FROM daily_bars b JOIN cache.daily_bar_cache c
      ON c.symbol=b.symbol AND c.trade_date=b.trade_date
    WHERE b.amount>0 AND (c.amount IS NULL OR c.amount<=0)""")

# And: bars present in cache but absent from hist (the other half of a switch)
q("D5 cache bars with no hist row at all",
 """SELECT COUNT(*) n, SUM(c.amount>0) with_amount FROM cache.daily_bar_cache c
    LEFT JOIN daily_bars b ON b.symbol=c.symbol AND b.trade_date=c.trade_date
    WHERE b.symbol IS NULL""")
con.close()
