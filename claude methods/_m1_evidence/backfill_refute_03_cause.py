import sqlite3
L = r"D:/codex-A股交易/trading_local.sqlite3"
H = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
lc, hc = ro(L), ro(H)
def q(con, sql, p=(), lim=25):
    print("SQL:", " ".join(sql.split()))
    rs = con.execute(sql, p).fetchall()
    for r in rs[:lim]: print("   ->", r)
    if len(rs) > lim: print(f"   ... ({len(rs)} rows total)")
    print()
    return rs

print("### D. Symbols in cache but NOT in instruments -- are indices in the cache?")
lc.execute("ATTACH DATABASE ? AS mh", (f"file:{H}?mode=ro",))
q(lc, "SELECT c.symbol, COUNT(*) FROM daily_bar_cache c LEFT JOIN mh.instruments i ON i.symbol=c.symbol "
      "WHERE i.symbol IS NULL GROUP BY c.symbol ORDER BY 2 DESC")
print("### D2. symbols with >=1 valid 10-char date (the '5,566' denominator?)")
q(lc, "SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE length(trade_date)=10")
q(lc, "SELECT symbol, trade_date, source, quality_status FROM daily_bar_cache WHERE length(trade_date)<>10")

print("### E. CAUSAL TEST: when did ingestion first write? Is the floor 500 sessions before first write?")
q(lc, "SELECT MIN(created_at), MAX(created_at), MIN(updated_at), MAX(updated_at) FROM daily_bar_cache")
q(lc, "SELECT substr(created_at,1,7) ym, COUNT(*), MIN(trade_date), MAX(trade_date) "
      "FROM daily_bar_cache GROUP BY ym ORDER BY ym LIMIT 12")
print("### E2. how many sessions lie between the data floor and the earliest write date?")
first_write = lc.execute("SELECT MIN(created_at) FROM daily_bar_cache").fetchone()[0]
fw = (first_write or "")[:10]
n = lc.execute("SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache "
               "WHERE length(trade_date)=10 AND trade_date BETWEEN '2024-04-09' AND ?", (fw,)).fetchone()[0]
print(f"first created_at = {first_write}; sessions from floor 2024-04-09 .. {fw} = {n}")
print("   (if ~500, the 500-clamp explains the floor; if far from 500, it does not)")
print()

print("### F. per-symbol row-count distribution -- FULL, not top-4")
rs = q(lc, "WITH per AS (SELECT symbol, COUNT(*) n FROM daily_bar_cache WHERE length(trade_date)=10 GROUP BY symbol) "
           "SELECT n, COUNT(*) c FROM per GROUP BY n ORDER BY n DESC LIMIT 15")
q(lc, "WITH per AS (SELECT symbol, COUNT(*) n FROM daily_bar_cache WHERE length(trade_date)=10 GROUP BY symbol) "
      "SELECT MIN(n), MAX(n), AVG(n), SUM(CASE WHEN n>500 THEN 1 ELSE 0 END), COUNT(*) FROM per")

print("### G. Gap-period cohort accounting the claim omits")
q(hc, "SELECT COUNT(*) FROM instruments WHERE list_date > '2023-09-04' AND list_date <= '2024-04-08'")
q(hc, "SELECT COUNT(*) FROM instruments WHERE delist_date IS NOT NULL AND delist_date <> '' "
      "AND delist_date BETWEEN '2023-09-04' AND '2024-04-08'")
q(hc, "SELECT COUNT(*) FROM instruments WHERE delist_date IS NOT NULL AND delist_date <> ''")
q(hc, "SELECT status, COUNT(*) FROM instruments GROUP BY status")

print("### H. realized rows/session near the floor (what a session actually costs)")
q(lc, "SELECT trade_date, COUNT(DISTINCT symbol) FROM daily_bar_cache "
      "WHERE trade_date BETWEEN '2024-04-09' AND '2024-04-30' GROUP BY trade_date ORDER BY trade_date")
lc.close(); hc.close()
