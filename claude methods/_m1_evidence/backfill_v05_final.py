import sqlite3
OP = r"D:\codex-A股交易\trading_local.sqlite3"
def q(c,s,a=()): return c.execute(s,a).fetchall()
op = sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
print("### R. The USABLE floor is later than the union floor")
for d in ('2024-04-09','2024-05-01','2024-06-03','2024-06-04','2024-06-05','2024-07-01'):
    n = q(op,"SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE trade_date=?", (d,))
    print("   symbols with a bar on %s: %s" % (d, n[0][0]))
print("R1 symbols with ANY bar strictly before 2024-06-04:",
      q(op,"SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE length(trade_date)=10 AND trade_date<'2024-06-04'"))
print("R2 rows strictly before 2024-06-04 (of 2.89M):",
      q(op,"SELECT COUNT(*) FROM daily_bar_cache WHERE length(trade_date)=10 AND trade_date<'2024-06-04'"))
print("R3 sessions 2024-04-09..2024-06-03:",
      q(op,"SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN '2024-04-09' AND '2024-06-03'"))
print("R4 median symbols-per-session in that stretch vs after:")
print("   before:", q(op,"""SELECT AVG(c) FROM (SELECT trade_date, COUNT(DISTINCT symbol) c FROM daily_bar_cache
                            WHERE trade_date BETWEEN '2024-04-09' AND '2024-06-03' GROUP BY trade_date)"""))
print("   after :", q(op,"""SELECT AVG(c) FROM (SELECT trade_date, COUNT(DISTINCT symbol) c FROM daily_bar_cache
                            WHERE trade_date BETWEEN '2024-06-04' AND '2024-08-01' GROUP BY trade_date)"""))
print()
print("### S. CORRECTED missing-row scale, using the DENSE floor 2024-06-04 and 141 gap sessions")
print("S1 gap 2023-09-04..2024-04-08 = 141 sessions (calendar arithmetic) x 5167 symbols x 0.9112 attendance =",
      int(141*5167*0.9112))
print("S2 EXTRA near-empty stretch 2024-04-09..2024-06-03 = 35 sessions where only 20 symbols/session exist")
print("S3 total effectively-missing sessions per symbol from 2023-09-04 to 2024-06-03 =",
      141 + q(op,"SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN '2024-04-09' AND '2024-06-03'")[0][0])
op.close()
