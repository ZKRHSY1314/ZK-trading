import sqlite3
L = r"D:/codex-A股交易/trading_local.sqlite3"
H = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
lc, hc = ro(L), ro(H)
def q(con, sql, p=(), lim=30):
    print("SQL:", " ".join(sql.split()))
    rs = con.execute(sql, p).fetchall()
    for r in rs[:lim]: print("   ->", r)
    if len(rs) > lim: print(f"   ... ({len(rs)} rows total)")
    print()
    return rs

print("### I. WHERE does market-wide coverage actually begin? breadth per session")
q(lc, "SELECT trade_date, COUNT(DISTINCT symbol) n FROM daily_bar_cache WHERE length(trade_date)=10 "
      "AND trade_date <= '2024-08-01' GROUP BY trade_date HAVING n > 100 ORDER BY trade_date LIMIT 5")
print("### I2. first session with >=1000 / >=3000 / >=5000 distinct symbols")
for thr in (100, 1000, 3000, 5000, 5400):
    r = lc.execute("SELECT trade_date, n FROM (SELECT trade_date, COUNT(DISTINCT symbol) n FROM daily_bar_cache "
                   "WHERE length(trade_date)=10 GROUP BY trade_date) WHERE n>=? ORDER BY trade_date LIMIT 1", (thr,)).fetchone()
    print(f"   first session with >={thr} symbols: {r}")
print()
print("### I3. how many of the 587 'covered' sessions are broad (>=5000 symbols)?")
q(lc, "SELECT SUM(CASE WHEN n>=5000 THEN 1 ELSE 0 END) broad, SUM(CASE WHEN n<5000 THEN 1 ELSE 0 END) thin, COUNT(*) tot "
      "FROM (SELECT trade_date, COUNT(DISTINCT symbol) n FROM daily_bar_cache WHERE length(trade_date)=10 "
      "AND trade_date BETWEEN '2023-09-04' AND '2026-09-04' GROUP BY trade_date)")
print("### I4. same for market_history.daily_bars")
q(hc, "SELECT SUM(CASE WHEN n>=5000 THEN 1 ELSE 0 END), COUNT(*), MIN(trade_date) FROM "
      "(SELECT trade_date, COUNT(DISTINCT symbol) n FROM daily_bars GROUP BY trade_date)")
for thr in (5000,):
    r = hc.execute("SELECT trade_date, n FROM (SELECT trade_date, COUNT(DISTINCT symbol) n FROM daily_bars "
                   "GROUP BY trade_date) WHERE n>=? ORDER BY trade_date LIMIT 1", (thr,)).fetchone()
    print(f"   hist first session with >={thr} symbols: {r}")
print()

print("### J. Did ONE ingest run already exceed 500 sessions? (kills the '500 clamp' mechanism)")
q(lc, "SELECT substr(created_at,1,10) d, COUNT(*) rows_, COUNT(DISTINCT symbol) syms, "
      "MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date) sessions "
      "FROM daily_bar_cache WHERE length(trade_date)=10 GROUP BY d ORDER BY d", lim=40)

print("### J2. per-symbol sessions delivered by a SINGLE created_at day (top)")
q(lc, "SELECT d, MAX(n), AVG(n) FROM (SELECT substr(created_at,1,10) d, symbol, COUNT(*) n "
      "FROM daily_bar_cache WHERE length(trade_date)=10 GROUP BY d, symbol) GROUP BY d ORDER BY d", lim=40)

print("### K. which provider supplied the deep history? source distribution")
q(lc, "SELECT source, COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date), MAX(trade_date) "
      "FROM daily_bar_cache WHERE length(trade_date)=10 GROUP BY source ORDER BY 2 DESC")
lc.close(); hc.close()
