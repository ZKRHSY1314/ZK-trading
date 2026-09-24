import sqlite3, statistics
OP = r"D:\codex-A股交易\trading_local.sqlite3"
def q(c,s,a=()): return c.execute(s,a).fetchall()
op = sqlite3.connect(f"file:{OP}?mode=ro", uri=True)

print("### N. The 2026-07-15 bulk batch: per-symbol ROW COUNT distribution (clamp fingerprint?)")
print("N1 rows-per-symbol histogram for created_at date 2026-07-15, top 10:",
      q(op,"""WITH b AS (SELECT symbol, COUNT(*) n FROM daily_bar_cache
                          WHERE substr(created_at,1,10)='2026-07-15' AND length(trade_date)=10 GROUP BY symbol)
              SELECT n, COUNT(*) FROM b GROUP BY n ORDER BY 2 DESC LIMIT 10"""))
print("N2 how many symbols got EXACTLY 500 rows in that batch:",
      q(op,"""WITH b AS (SELECT symbol, COUNT(*) n FROM daily_bar_cache
                          WHERE substr(created_at,1,10)='2026-07-15' AND length(trade_date)=10 GROUP BY symbol)
              SELECT SUM(n=500), SUM(n>500), SUM(n<500), COUNT(*) FROM b"""))
print("N3 max rows any single symbol got in that batch:",
      q(op,"""WITH b AS (SELECT symbol, COUNT(*) n FROM daily_bar_cache
                          WHERE substr(created_at,1,10)='2026-07-15' AND length(trade_date)=10 GROUP BY symbol)
              SELECT MAX(n), MIN(n) FROM b"""))

print()
print("### O. Does tail(500) ROWS explain the 2024-04-09 union floor? "
      "(few-traded symbols reach further back with the same 500 rows)")
print("O1 symbols whose earliest cached bar IS the floor 2024-04-09, and their total row count:",
      q(op,"""WITH m AS (SELECT symbol, MIN(trade_date) mn, COUNT(*) n FROM daily_bar_cache
                          WHERE length(trade_date)=10 GROUP BY symbol)
              SELECT COUNT(*) syms, MIN(n), MAX(n), AVG(n) FROM m WHERE mn='2024-04-09'"""))
print("O2 distribution of per-symbol MIN(trade_date), 12 earliest buckets:",
      q(op,"""WITH m AS (SELECT symbol, MIN(trade_date) mn FROM daily_bar_cache WHERE length(trade_date)=10 GROUP BY symbol)
              SELECT mn, COUNT(*) FROM m GROUP BY mn ORDER BY mn LIMIT 12"""))
print("O3 correlation check: symbols with FEWEST total rows should have EARLIEST min date if tail() is row-based")
print("   ",q(op,"""WITH m AS (SELECT symbol, MIN(trade_date) mn, COUNT(*) n FROM daily_bar_cache
                       WHERE length(trade_date)=10 GROUP BY symbol)
              SELECT CASE WHEN n<505 THEN 'a:<505' WHEN n<535 THEN 'b:505-534' ELSE 'c:>=535' END bucket,
                     COUNT(*) syms, MIN(mn) earliest, MAX(mn) latest FROM m GROUP BY bucket ORDER BY bucket"""))

print()
print("### P. Did ANY symbol ever receive >550 sessions of depth? (would disprove a hard 500 ceiling)")
print("P1 global max rows per symbol:",
      q(op,"WITH m AS (SELECT symbol,COUNT(*) n FROM daily_bar_cache WHERE length(trade_date)=10 GROUP BY symbol) SELECT MAX(n) FROM m"))
print("P2 sessions available 2024-04-09..2026-07-15 (the bulk batch span):",
      q(op,"SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN '2024-04-09' AND '2026-07-15'"))
print("P3 sessions 2026-07-16..2026-09-04 (post-batch daily appends):",
      q(op,"SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN '2026-07-16' AND '2026-09-04'"))
print("   => a 500-row batch + %s daily appends caps a symbol near 500+appends, matching the 536/537/538 mode" %
      q(op,"SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN '2026-07-16' AND '2026-09-04'")[0][0])

print()
print("### Q. sanity: is 2024-04-09 also the floor for the akshare/Sina source specifically?")
print("Q1 min trade_date per source (cache):",
      q(op,"SELECT source, MIN(trade_date), COUNT(DISTINCT trade_date), COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE length(trade_date)=10 GROUP BY source ORDER BY 2"))
op.close()
