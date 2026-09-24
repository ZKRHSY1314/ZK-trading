import sqlite3
MH = r"D:/codex-A股交易/market_history.sqlite3"; TL = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True); c.row_factory = sqlite3.Row; return c
mh, tl = ro(MH), ro(TL)
def q(c,s,a=()): return c.execute(s,a).fetchall()
def p(t): print("\n"+"="*78+"\n"+t+"\n"+"="*78)
ST = "i.exchange IN ('SH','SZ','BJ')"

p("Q. Window trading-day accounting (STOCKS ONLY, market_history)")
print("SQL: SELECT COUNT(DISTINCT trade_date) FROM daily_bars WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'")
for r in q(mh,"SELECT COUNT(DISTINCT trade_date) d_in_window, MIN(trade_date) mn, MAX(trade_date) mx FROM daily_bars WHERE trade_date>='2023-09-04' AND trade_date<='2026-09-04'"):
    print("   ->", dict(r))
print("SQL: distinct trade_date with >=4000 stocks reporting (a 'usable breadth' day)")
for r in q(mh,f"""WITH d AS (SELECT b.trade_date td, COUNT(DISTINCT b.symbol) s FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol WHERE {ST} GROUP BY 1)
                  SELECT COUNT(*) usable_days, MIN(td) first_usable, MAX(td) last_usable FROM d WHERE s>=4000"""):
    print("   ->", dict(r))
print("SQL: same but >=5000 stocks reporting")
for r in q(mh,f"""WITH d AS (SELECT b.trade_date td, COUNT(DISTINCT b.symbol) s FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol WHERE {ST} GROUP BY 1)
                  SELECT COUNT(*) days_ge_5000, MIN(td) first FROM d WHERE s>=5000"""):
    print("   ->", dict(r))

p("R. Reproducing the auditor's own thresholds, independently")
print("SQL: symbols with list_date<'2024-04-09' AND first_bar>'2024-04-30'  (their numerator)")
for r in q(mh,"""WITH f AS (SELECT symbol s, MIN(trade_date) ft, COUNT(DISTINCT trade_date) n FROM daily_bars GROUP BY symbol)
                 SELECT COUNT(*) their_5258, SUM(CASE WHEN f.n>=480 THEN 1 ELSE 0 END) their_4965
                 FROM f JOIN instruments i ON i.symbol=f.s WHERE i.list_date < '2024-04-09' AND f.ft > '2024-04-30'"""):
    print("   ->", dict(r))
print("SQL: exact-536-bar symbols (their 4,688)")
for r in q(mh,"WITH c AS (SELECT symbol, COUNT(*) n FROM daily_bars GROUP BY symbol) SELECT SUM(n=536) eq536, SUM(n>520) gt520, COUNT(*) total FROM c"):
    print("   ->", dict(r))

p("S. Second onboarding wave: Beijing exchange (BJ)")
print("SQL: SELECT i.exchange, MIN(f.ft), MAX(f.ft), COUNT(*) FROM first-bar per symbol GROUP BY exchange")
for r in q(mh,f"""WITH f AS (SELECT symbol s, MIN(trade_date) ft, MAX(trade_date) lt, COUNT(DISTINCT trade_date) n FROM daily_bars GROUP BY symbol)
                  SELECT i.exchange ex, COUNT(*) syms, MIN(f.ft) earliest_first_bar, ROUND(AVG(f.n),1) avg_bars,
                         SUM(CASE WHEN f.ft <= '2024-06-24' THEN 1 ELSE 0 END) present_at_2024_06_24
                  FROM f JOIN instruments i ON i.symbol=f.s WHERE {ST} GROUP BY 1 ORDER BY syms DESC"""):
    print("   ->", dict(r))
print("SQL: BJ symbols listed before 2024 but first bar in 2025-11/12")
for r in q(mh,"""WITH f AS (SELECT symbol s, MIN(trade_date) ft FROM daily_bars GROUP BY symbol)
                 SELECT COUNT(*) bj_listed_pre2024_first_bar_late FROM f JOIN instruments i ON i.symbol=f.s
                 WHERE i.exchange='BJ' AND i.list_date < '2024-01-01' AND f.ft >= '2025-11-01'"""):
    print("   ->", dict(r))

p("T. Impossible-history / stale-tail checks")
print("SQL: symbols whose FIRST bar precedes their list_date (data contradiction)")
for r in q(mh,"""WITH f AS (SELECT symbol s, MIN(trade_date) ft FROM daily_bars GROUP BY symbol)
                 SELECT COUNT(*) first_bar_before_list_date FROM f JOIN instruments i ON i.symbol=f.s
                 WHERE i.list_date IS NOT NULL AND i.list_date<>'' AND f.ft < i.list_date"""):
    print("   ->", dict(r))
print("SQL: symbols whose LAST bar is >60 calendar days before the store max (2026-09-03)")
for r in q(mh,"""WITH f AS (SELECT symbol s, MAX(trade_date) lt, COUNT(DISTINCT trade_date) n FROM daily_bars GROUP BY symbol)
                 SELECT COUNT(*) stale_tail_syms FROM f WHERE f.lt < date('2026-09-03','-60 day')"""):
    print("   ->", dict(r))
print("SQL: of those, how many are still marked status='active' in instruments")
for r in q(mh,"""WITH f AS (SELECT symbol s, MAX(trade_date) lt FROM daily_bars GROUP BY symbol)
                 SELECT i.status, COUNT(*) n FROM f JOIN instruments i ON i.symbol=f.s
                 WHERE f.lt < date('2026-09-03','-60 day') GROUP BY 1"""):
    print("   ->", dict(r))

p("U. Historical-universe reconstruction: is there ANY as-of-date universe before 2026-07?")
print("SQL: SELECT MIN(snapshot_date), MAX(snapshot_date), COUNT(*) FROM universe_snapshots")
for r in q(mh,"SELECT MIN(snapshot_date) mn, MAX(snapshot_date) mx, COUNT(*) n, COUNT(DISTINCT universe_name) names FROM universe_snapshots"):
    print("   ->", dict(r))
print("SQL: universe_members membership dates")
for r in q(mh,"SELECT COUNT(*) n, COUNT(DISTINCT symbol) syms FROM universe_members"):
    print("   ->", dict(r))
print("SQL: instruments.list_date distribution INSIDE the research window (real new listings)")
for r in q(mh,f"""SELECT COUNT(*) listed_in_window FROM instruments i WHERE {ST} AND i.list_date>='2023-09-04' AND i.list_date<='2026-09-04'"""):
    print("   ->", dict(r))
