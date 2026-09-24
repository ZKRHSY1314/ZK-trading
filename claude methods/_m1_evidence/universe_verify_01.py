import sqlite3, json, sys
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"

def ro(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c

mh = ro(MH); tl = ro(TL)
def q(conn, sql, args=()):
    return conn.execute(sql, args).fetchall()
def p(title): print("\n" + "="*78 + "\n" + title + "\n" + "="*78)

p("A. daily_bars global extents + adjustment_mode composition")
for r in q(mh, "SELECT COUNT(*) rows, COUNT(DISTINCT symbol) syms, MIN(trade_date) mn, MAX(trade_date) mx FROM daily_bars"):
    print("SQL: SELECT COUNT(*),COUNT(DISTINCT symbol),MIN(trade_date),MAX(trade_date) FROM daily_bars")
    print("   ->", dict(r))
print("SQL: SELECT adjustment_mode, COUNT(*), COUNT(DISTINCT symbol) FROM daily_bars GROUP BY 1")
for r in q(mh, "SELECT adjustment_mode, COUNT(*) n, COUNT(DISTINCT symbol) s, MIN(trade_date) mn, MAX(trade_date) mx FROM daily_bars GROUP BY adjustment_mode ORDER BY n DESC"):
    print("   ->", dict(r))

p("B. Does COUNT(*) per symbol double-count across adjustment_mode?")
print("SQL: per-symbol distinct adjustment_mode count histogram")
for r in q(mh, """SELECT k, COUNT(*) syms FROM (SELECT symbol, COUNT(DISTINCT adjustment_mode) k FROM daily_bars GROUP BY symbol) GROUP BY k ORDER BY k"""):
    print("   ->", dict(r))

p("C. Bar-count histogram using DISTINCT trade_date (mode-safe), top 20")
print("SQL: WITH c AS (SELECT symbol, COUNT(DISTINCT trade_date) n FROM daily_bars GROUP BY symbol) SELECT n, COUNT(*) FROM c GROUP BY n ORDER BY COUNT(*) DESC LIMIT 20")
for r in q(mh, """WITH c AS (SELECT symbol, COUNT(DISTINCT trade_date) n FROM daily_bars GROUP BY symbol)
                  SELECT n, COUNT(*) syms FROM c GROUP BY n ORDER BY syms DESC, n DESC LIMIT 20"""):
    print("   ->", dict(r))

p("D. Are the 'symbols' in daily_bars stocks? join instruments exchange/asset_type")
print("SQL: SELECT i.exchange, i.asset_type, COUNT(DISTINCT d.symbol) FROM (SELECT DISTINCT symbol FROM daily_bars) d LEFT JOIN instruments i ON i.symbol=d.symbol GROUP BY 1,2")
for r in q(mh, """SELECT COALESCE(i.exchange,'<no instruments row>') ex, COALESCE(i.asset_type,'<null>') at, COUNT(*) syms
                  FROM (SELECT DISTINCT symbol FROM daily_bars) d
                  LEFT JOIN instruments i ON i.symbol=d.symbol
                  GROUP BY 1,2 ORDER BY syms DESC"""):
    print("   ->", dict(r))

p("E. instruments status / delist composition, and whether delisted names carry bars")
print("SQL: SELECT status, COUNT(*), SUM(delist_date IS NOT NULL) FROM instruments GROUP BY status")
for r in q(mh, "SELECT COALESCE(status,'<null>') st, COUNT(*) n, SUM(CASE WHEN delist_date IS NOT NULL AND delist_date<>'' THEN 1 ELSE 0 END) with_delist FROM instruments GROUP BY 1 ORDER BY n DESC"):
    print("   ->", dict(r))
print("SQL: instruments with delist_date in window, and how many have bars")
for r in q(mh, """SELECT COUNT(*) delisted_in_window,
                         SUM(CASE WHEN EXISTS(SELECT 1 FROM daily_bars b WHERE b.symbol=i.symbol) THEN 1 ELSE 0 END) with_any_bars
                  FROM instruments i
                  WHERE i.delist_date IS NOT NULL AND i.delist_date<>'' AND i.delist_date >= '2023-09-04' AND i.delist_date <= '2026-09-04'"""):
    print("   ->", dict(r))

p("F. STOCKS ONLY (exclude INDEX/OTHER): first-bar-date distribution by year-month, top 15")
STOCK = "i.exchange IN ('SH','SZ','BJ')"
print(f"SQL: WITH f AS (SELECT b.symbol, MIN(b.trade_date) ft, COUNT(DISTINCT b.trade_date) n FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol WHERE {STOCK} GROUP BY b.symbol) SELECT substr(ft,1,7), COUNT(*) FROM f GROUP BY 1 ORDER BY 2 DESC LIMIT 15")
for r in q(mh, f"""WITH f AS (SELECT b.symbol s, MIN(b.trade_date) ft, COUNT(DISTINCT b.trade_date) n
                              FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol WHERE {STOCK} GROUP BY b.symbol)
                   SELECT substr(ft,1,7) ym, COUNT(*) syms FROM f GROUP BY 1 ORDER BY syms DESC LIMIT 15"""):
    print("   ->", dict(r))

p("G. STOCKS ONLY: denominator-clean truncation test")
print("Definition: a symbol is TRUNCATED if it was already listed >=20 trading days before 2023-09-04")
print("            (list_date < '2023-08-01') yet its first bar is after '2023-09-30'.")
for r in q(mh, f"""WITH f AS (SELECT b.symbol s, MIN(b.trade_date) ft, MAX(b.trade_date) lt, COUNT(DISTINCT b.trade_date) n
                              FROM daily_bars b GROUP BY b.symbol)
                   SELECT COUNT(*) stock_syms_with_bars,
                          SUM(CASE WHEN i.list_date IS NOT NULL AND i.list_date<>'' THEN 1 ELSE 0 END) have_list_date,
                          SUM(CASE WHEN i.list_date < '2023-08-01' THEN 1 ELSE 0 END) listed_before_window,
                          SUM(CASE WHEN i.list_date < '2023-08-01' AND f.ft > '2023-09-30' THEN 1 ELSE 0 END) truncated,
                          SUM(CASE WHEN i.list_date < '2023-08-01' AND f.ft > '2023-09-30' AND f.n >= 480 THEN 1 ELSE 0 END) truncated_but_dense
                   FROM f JOIN instruments i ON i.symbol=f.s WHERE {STOCK}"""):
    print("   ->", dict(r))

p("H. Cross-sectional breadth around the alleged 2024-06-24 jump (STOCKS ONLY)")
print("SQL: SELECT trade_date, COUNT(DISTINCT b.symbol) FROM daily_bars b JOIN instruments i ... WHERE exchange IN (SH,SZ,BJ) AND trade_date BETWEEN '2024-06-10' AND '2024-07-05' GROUP BY 1")
for r in q(mh, f"""SELECT b.trade_date td, COUNT(DISTINCT b.symbol) syms
                   FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
                   WHERE {STOCK} AND b.trade_date BETWEEN '2024-06-10' AND '2024-07-05'
                   GROUP BY 1 ORDER BY 1"""):
    print("   ->", dict(r))

p("I. Breadth samples across the whole research window (STOCKS ONLY), quarterly")
for r in q(mh, f"""SELECT substr(b.trade_date,1,7) ym, COUNT(DISTINCT b.symbol) syms, COUNT(DISTINCT b.trade_date) days
                   FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
                   WHERE {STOCK} AND b.trade_date BETWEEN '2023-09-04' AND '2026-09-04'
                   GROUP BY 1 ORDER BY 1"""):
    print("   ->", dict(r))
