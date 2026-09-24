import sqlite3
H=r"D:/codex-A股交易/market_history.sqlite3"
C=r"D:/codex-A股交易/trading_local.sqlite3"
con=sqlite3.connect(f"file:{H}?mode=ro",uri=True)
con.execute("ATTACH DATABASE ? AS cache", (f"file:{C}?mode=ro",))
def q(label,sql,p=()):
    print("\n### "+label); print("SQL:",' '.join(sql.split()))
    for r in con.execute(sql,p).fetchall()[:25]: print("   ",r)

q("E1 hist vs cache VOLUME ratio on the regressing bars (unit test)",
 """WITH t AS (SELECT b.volume/c.volume AS vr
    FROM daily_bars b JOIN cache.daily_bar_cache c ON c.symbol=b.symbol AND c.trade_date=b.trade_date
    WHERE (b.amount IS NULL OR b.amount<=0) AND c.amount>0 AND c.volume>0 AND b.volume>0)
    SELECT COUNT(*) n, SUM(vr BETWEEN 0.99 AND 1.01) same_unit,
           SUM(vr BETWEEN 99 AND 101) hist_100x, SUM(vr NOT BETWEEN 0.99 AND 1.01 AND vr NOT BETWEEN 99 AND 101) other
    FROM t""")

q("E2 hist declares volume_unit for those 100x rows",
 """SELECT b.volume_unit, COUNT(*) FROM daily_bars b
    JOIN cache.daily_bar_cache c ON c.symbol=b.symbol AND c.trade_date=b.trade_date
    WHERE (b.amount IS NULL OR b.amount<=0) AND c.volume>0 AND b.volume/c.volume BETWEEN 99 AND 101
    GROUP BY 1""")

q("E3 how many DISTINCT securities carry mislabelled-unit bars",
 """SELECT COUNT(DISTINCT b.symbol) FROM daily_bars b
    JOIN cache.daily_bar_cache c ON c.symbol=b.symbol AND c.trade_date=b.trade_date
    WHERE (b.amount IS NULL OR b.amount<=0) AND c.volume>0 AND b.volume/c.volume BETWEEN 99 AND 101""")

q("E4 proxy overstatement >2x count and its liquidity impact",
 """SELECT COUNT(*) FROM daily_bars b JOIN cache.daily_bar_cache c
      ON c.symbol=b.symbol AND c.trade_date=b.trade_date
    WHERE (b.amount IS NULL OR b.amount<=0) AND c.amount>0 AND b.volume>0
      AND (b.volume*100.0*((b.high+b.low+b.close)/3.0))/c.amount > 2.0""")

q("E5 provider of the 100x-volume rows",
 """SELECT b.provider, COUNT(*) FROM daily_bars b
    JOIN cache.daily_bar_cache c ON c.symbol=b.symbol AND c.trade_date=b.trade_date
    WHERE c.volume>0 AND b.volume/c.volume BETWEEN 99 AND 101 GROUP BY 1 ORDER BY 2 DESC""")
con.close()
