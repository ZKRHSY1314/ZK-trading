import sqlite3, datetime
TL = r"D:\codex-A股交易\trading_local.sqlite3"
con = sqlite3.connect(f"file:{TL}?mode=ro", uri=True); con.execute("PRAGMA query_only=ON")
c = con.cursor()
d0=datetime.date(2023,9,4); d1=datetime.date(2026,9,4); dg=datetime.date(2024,4,8); dobs=datetime.date(2024,4,9)
span=(d1-d0).days+1; gap=(dg-d0).days+1; obs=(d1-dobs).days+1
print(f"window calendar span 2023-09-04..2026-09-04 = {span} days")
print(f"EMPTY head 2023-09-04..2024-04-08          = {gap} days = {100*gap/span:.1f}% of the window, 0 rows")
print(f"observed  2024-04-09..2026-09-04           = {obs} days = {100*obs/span:.1f}%, 587 sessions")
full0=datetime.date(2024,6,24); fobs=(d1-full0).days+1
print(f"full-breadth 2024-06-24..2026-09-04        = {fobs} days = {100*fobs/span:.1f}%, 536 sessions")
print()
print("observed session density in the full-breadth region: 536 sessions / %.2f months = %.2f sessions/month"
      % (fobs/30.437, 536/(fobs/30.437)))
print("(ESTIMATE ONLY, not a measurement - no trading calendar exists on disk:")
print("  the 217-day empty head would hold roughly %d sessions at that density)" % round(217/30.437*536/(fobs/30.437)))
print()
print("=== FINAL headline numbers, my own queries ===")
q="""SELECT COUNT(*) FROM (SELECT trade_date, COUNT(DISTINCT symbol) n FROM daily_bar_cache
 WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'
   AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
   AND LENGTH(symbol)=8 AND SUBSTR(symbol,1,2) IN ('SH','SZ','BJ')
   AND symbol NOT IN ('SH000001','SH000300') GROUP BY 1 HAVING n>=5000)"""
print(" sessions with >=5000 distinct stocks:", c.execute(q).fetchone()[0])
print(" sessions total in window            :", c.execute("""SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache
 WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04' AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'""").fetchone()[0])
print(" rows created before 2026-06         :", c.execute("SELECT COUNT(*) FROM daily_bar_cache WHERE created_at < '2026-06-01'").fetchone()[0])
con.close()
