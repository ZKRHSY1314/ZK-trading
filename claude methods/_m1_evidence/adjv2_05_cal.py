import sqlite3, collections
c=sqlite3.connect(r"file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True)
print("=== symbols-per-day, by month (cache) ===")
for r in c.execute("""SELECT substr(trade_date,1,7) ym, COUNT(DISTINCT trade_date) days,
   COUNT(*) rows, COUNT(DISTINCT symbol) syms, COUNT(*)/COUNT(DISTINCT trade_date) avg_per_day
   FROM daily_bar_cache WHERE length(trade_date)=10 AND date(trade_date) IS NOT NULL
   AND trade_date BETWEEN '2023-09-04' AND '2026-09-04' GROUP BY ym ORDER BY ym"""):
    print(r)
