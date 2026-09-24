import sqlite3
H=r"D:/codex-A股交易/market_history.sqlite3"
C=r"D:/codex-A股交易/trading_local.sqlite3"
con=sqlite3.connect(f"file:{H}?mode=ro",uri=True)
con.execute("ATTACH DATABASE ? AS cache", (f"file:{C}?mode=ro",))
def q(label,sql,p=()):
    print("\n### "+label); print("SQL:",' '.join(sql.split()))
    rows=con.execute(sql,p).fetchall()
    for r in rows[:40]: print("   ",r)
    if len(rows)>40: print("    ...",len(rows),"rows total")
    return rows

q("B0 date ranges",
 """SELECT (SELECT MIN(trade_date) FROM daily_bars),(SELECT MAX(trade_date) FROM daily_bars),
           (SELECT MIN(trade_date) FROM cache.daily_bar_cache),(SELECT MAX(trade_date) FROM cache.daily_bar_cache)""")

q("B1 hist symbol shapes",
 """SELECT CASE WHEN symbol GLOB '[0-9]*' THEN 'numeric' ELSE substr(symbol,1,2) END shape,
    COUNT(DISTINCT symbol) syms, COUNT(*) rows FROM daily_bars GROUP BY 1""")
q("B1b cache symbol shapes",
 """SELECT CASE WHEN symbol GLOB '[0-9]*' THEN 'numeric' ELSE substr(symbol,1,2) END shape,
    COUNT(DISTINCT symbol) syms, COUNT(*) rows FROM cache.daily_bar_cache GROUP BY 1""")

q("B2 cache adjustment_mode / source mix",
 """SELECT adjustment_mode, source, COUNT(*) n, SUM(amount IS NULL) nulls
    FROM cache.daily_bar_cache GROUP BY 1,2 ORDER BY 3 DESC""")

# INDEPENDENT join: LEFT JOIN from hist so I control the denominator myself,
# and I count "usable" = amount IS NOT NULL AND amount > 0 (execution.py treats <=0 as missing)
q("B3 INDEPENDENT: hist->cache left join, usable-amount matrix (all hist rows)",
 """SELECT
      CASE WHEN b.amount IS NULL OR b.amount<=0 THEN 'hist_unusable' ELSE 'hist_ok' END,
      CASE WHEN c.symbol IS NULL THEN 'no_cache_row'
           WHEN c.amount IS NULL OR c.amount<=0 THEN 'cache_unusable' ELSE 'cache_ok' END,
      COUNT(*)
    FROM daily_bars b
    LEFT JOIN cache.daily_bar_cache c
      ON c.symbol=b.symbol AND c.trade_date=b.trade_date
    GROUP BY 1,2 ORDER BY 3 DESC""")

q("B4 fan-out sanity: does any (symbol,trade_date) repeat in hist?",
 """SELECT COUNT(*) FROM (SELECT symbol,trade_date FROM daily_bars GROUP BY 1,2 HAVING COUNT(*)>1)""")

q("B5 distinct SECURITIES with any unusable-amount bar in hist (window)",
 """SELECT COUNT(DISTINCT symbol) FROM daily_bars WHERE amount IS NULL OR amount<=0""")
q("B5b distinct securities where EVERY hist bar is unusable",
 """SELECT COUNT(*) FROM (SELECT symbol FROM daily_bars GROUP BY symbol
    HAVING SUM(CASE WHEN amount IS NULL OR amount<=0 THEN 1 ELSE 0 END)=COUNT(*))""")
q("B5c total distinct securities in hist","SELECT COUNT(DISTINCT symbol) FROM daily_bars")

q("B6 volume availability on hist rows lacking amount (is a proxy possible?)",
 """SELECT volume_unit, COUNT(*) n, SUM(volume IS NULL OR volume<=0) vol_unusable
    FROM daily_bars WHERE amount IS NULL OR amount<=0 GROUP BY 1 ORDER BY 2 DESC""")
con.close()
