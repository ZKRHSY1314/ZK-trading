import sqlite3
tl=sqlite3.connect("file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True)
q=lambda s: tl.execute(s).fetchall()
# Framed the opposite way: count securities whose ENTIRE bar history ends before the window's final month.
print("stocks whose last bar is before 2026-06-01 (a true mid-window death):",
 q("""SELECT COUNT(*) FROM (
   SELECT symbol, MAX(trade_date) mx FROM daily_bar_cache
   WHERE symbol GLOB '[A-Z][A-Z][0-9]*' AND symbol NOT IN ('SH000001','SH000300')
     AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
     AND trade_date <= '2026-09-04'
   GROUP BY symbol) WHERE mx < '2026-06-01'"""))
print("...and in the research store market_history.daily_bars:")
mh=sqlite3.connect("file:D:/codex-A股交易/market_history.sqlite3?mode=ro",uri=True)
print(mh.execute("""SELECT COUNT(*) FROM (SELECT symbol,MAX(trade_date) mx FROM daily_bars GROUP BY symbol) WHERE mx<'2026-06-01'""").fetchall())
print("distinct trade dates present, per calendar year, mh.daily_bars:")
for r in mh.execute("SELECT substr(trade_date,1,4) y, COUNT(DISTINCT trade_date) FROM daily_bars GROUP BY 1 ORDER BY 1"): print("   ",r)
