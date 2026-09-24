import sqlite3, datetime
# Sensitivity: does the conclusion survive ANY plausible real-calendar denominator?
# Anchor the session rate on OBSERVED data only (no external calendar assumed).
c=sqlite3.connect(r"file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True)
c.execute(r"ATTACH DATABASE 'file:D:/codex-A股交易/market_history.sqlite3?mode=ro' AS mh")
# observed sessions per calendar-year-fragment, measured from the dense part of the spine
SQL="""SELECT substr(trade_date,1,4) yr, COUNT(DISTINCT trade_date) FROM daily_bar_cache
       WHERE trade_date>='2024-06-24' AND trade_date<='2026-09-04'
         AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' GROUP BY 1"""
print("SQL:"," ".join(SQL.split()))
for r in c.execute(SQL): print("   sessions observed in",r[0],"=",r[1])
print("\n2025 is a COMPLETE observed year -> that is the empirical A-share sessions/year.")
S2025=[r[1] for r in c.execute(SQL) if r[0]=='2025'][0]
print("   empirical sessions/year =",S2025)
print("\nSensitivity of the 3-year window denominator and the resulting ceiling (max observed = 538):")
for label,D in (("3 x empirical 2025 year", S2025*3),
                ("my ratio estimate", 733),
                ("conservative low (240/yr)", 720),
                ("all Mon-Fri weekdays (hard upper bound)", 785)):
    print("   denominator=%3d (%-38s) -> best-covered stock = %.4f ; stocks >=0.80 = %s"
          % (D,label,538/D, "0" if 538/D<0.80 else "SOME"))
c.close()
