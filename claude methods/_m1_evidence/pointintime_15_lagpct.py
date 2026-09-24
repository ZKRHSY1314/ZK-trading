import sqlite3,sys
sys.stdout.reconfigure(encoding='utf-8')
m=sqlite3.connect("file:D:/codex-A股交易/market_history.sqlite3?mode=ro",uri=True)
SQL=("SELECT CAST(julianday(substr(available_at,1,10))-julianday(trade_date) AS INT) lag, COUNT(*) n "
     "FROM daily_bars GROUP BY lag ORDER BY lag")
print("### L1 SQL:", SQL)
rows=m.execute(SQL).fetchall(); tot=sum(n for _,n in rows)
print("total rows:", tot, " distinct lag values:", len(rows), " min lag:", rows[0][0], " max lag:", rows[-1][0])
cum=0; marks={}
for lag,n in rows:
    prev=cum; cum+=n
    for p in (1,5,25,50,75,95,99):
        if p not in marks and cum >= tot*p/100: marks[p]=lag
print("available_at MINUS trade_date, calendar-day percentiles:")
for p in (1,5,25,50,75,95,99): print(f"   p{p:<3d} = {marks[p]} days")
le0=sum(n for l,n in rows if l==0); le3=sum(n for l,n in rows if l<=3); le30=sum(n for l,n in rows if l<=30)
print(f"   lag == 0 days : {le0} ({le0/tot*100:.2f}%)")
print(f"   lag <= 3 days : {le3} ({le3/tot*100:.2f}%)")
print(f"   lag <= 30 days: {le30} ({le30/tot*100:.2f}%)")
print(f"   lag > 365 days: {sum(n for l,n in rows if l>365)} ({sum(n for l,n in rows if l>365)/tot*100:.2f}%)")
m.close()

c=sqlite3.connect("file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True)
print("\n### L2 warm-up region (SEPARATE from window coverage)")
for lbl,sql in [
 ("daily_bar_cache rows with trade_date < 2023-09-04","SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date < '2023-09-04'"),
 ("daily_bar_cache rows 2023-09-04..2024-04-08","SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date >= '2023-09-04' AND trade_date <= '2024-04-08'"),
 ("daily_bar_cache rows 2024-04-09..2026-09-04","SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date >= '2024-04-09' AND trade_date <= '2026-09-04'"),
]:
    print(f"   {lbl}: {c.execute(sql).fetchone()[0]}   |SQL| {sql}")
m2=sqlite3.connect("file:D:/codex-A股交易/market_history.sqlite3?mode=ro",uri=True)
print("   market_history rows with trade_date < 2023-09-04:",
      m2.execute("SELECT COUNT(*) FROM daily_bars WHERE trade_date < '2023-09-04'").fetchone()[0],
      "  |SQL| SELECT COUNT(*) FROM daily_bars WHERE trade_date < '2023-09-04'")
m2.close(); c.close()
