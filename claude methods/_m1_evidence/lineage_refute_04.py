import sqlite3
OP=r"D:/codex-A股交易/trading_local.sqlite3"; RH=r"D:/codex-A股交易/market_history.sqlite3"
def ro(p):
    c=sqlite3.connect(f"file:{p}?mode=ro",uri=True); c.row_factory=sqlite3.Row; return c
op,rh=ro(OP),ro(RH)
def show(t,conn,sql,params=()):
    print("\n### "+t); print("SQL: "+" ".join(sql.split()))
    rows=conn.execute(sql,params).fetchall()
    for r in rows[:20]: print("   ",dict(r))
    return rows

show("I1 quality_status of the two index symbols the benchmark needs", op,
 "SELECT symbol, quality_status, source, COUNT(*) n FROM daily_bar_cache WHERE symbol IN ('SH000300','SH000001') GROUP BY 1,2,3")
show("I2 does market_history hold ANY index at all? (asset_type/exchange=INDEX)", rh,
 "SELECT exchange, COUNT(*) n FROM instruments GROUP BY 1 ORDER BY n DESC")
show("I3 index instruments in market_history that have NO bars", rh, """
SELECT i.exchange, COUNT(*) AS instruments, SUM(CASE WHEN b.symbol IS NULL THEN 1 ELSE 0 END) AS with_zero_bars
FROM instruments i LEFT JOIN (SELECT DISTINCT symbol FROM daily_bars) b ON b.symbol=i.symbol
WHERE i.exchange='INDEX' GROUP BY 1""")
show("I4 the 40 history-only bars: which symbols, and are they in the research window?", rh, """
SELECT symbol, adjustment_mode, COUNT(*) n, MIN(trade_date) mn, MAX(trade_date) mx
FROM daily_bars WHERE symbol IN ('SH600135','SH688515') GROUP BY 1,2""")
op.close(); rh.close()
