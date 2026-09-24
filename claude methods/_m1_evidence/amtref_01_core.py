import sqlite3
H=r"D:/codex-A股交易/market_history.sqlite3"
C=r"D:/codex-A股交易/trading_local.sqlite3"
con=sqlite3.connect(f"file:{H}?mode=ro",uri=True)
con.execute("ATTACH DATABASE ? AS cache", (f"file:{C}?mode=ro",))
def q(label,sql,p=()):
    print("\n### "+label)
    print("SQL:",' '.join(sql.split()))
    rows=con.execute(sql,p).fetchall()
    for r in rows[:40]: print("   ",r)
    if len(rows)>40: print("    ...",len(rows),"rows")
    return rows

# 1. reproduce headline raw denominator
q("A1 hist total + null amount (raw, no filter)",
 "SELECT COUNT(*), SUM(amount IS NULL), SUM(amount IS NOT NULL AND amount<=0) FROM daily_bars")

# 2. break down by adjustment_mode  <-- their denominator mixes 3 modes
q("A2 hist null-amount by adjustment_mode",
 "SELECT adjustment_mode, COUNT(*) n, SUM(amount IS NULL) nulls, ROUND(100.0*SUM(amount IS NULL)/COUNT(*),2) pct FROM daily_bars GROUP BY 1 ORDER BY 2 DESC")

# 3. by provider
q("A3 hist null-amount by provider",
 "SELECT provider, COUNT(*) n, SUM(amount IS NULL) nulls FROM daily_bars GROUP BY 1 ORDER BY 2 DESC")

# 4. same but restricted to research window
q("A4 hist null-amount IN WINDOW 2023-09-04..2026-09-04 by mode",
 "SELECT adjustment_mode, COUNT(*) n, SUM(amount IS NULL) nulls, ROUND(100.0*SUM(amount IS NULL)/COUNT(*),2) pct FROM daily_bars WHERE trade_date>='2023-09-04' AND trade_date<='2026-09-04' GROUP BY 1 ORDER BY 2 DESC")

# 5. indices vs stocks
q("A5 hist null-amount by exchange (index vs stock), window",
 """SELECT i.exchange, i.asset_type, COUNT(*) n, SUM(b.amount IS NULL) nulls
    FROM daily_bars b JOIN instruments i USING(symbol)
    WHERE b.trade_date>='2023-09-04' AND b.trade_date<='2026-09-04'
    GROUP BY 1,2 ORDER BY 3 DESC""")

# 6. cache: usable amount (>0), raw + window
q("A6 cache totals raw / window / amount usability",
 """SELECT COUNT(*) n, SUM(amount IS NULL) nulls, SUM(amount IS NOT NULL AND amount<=0) zeros
    FROM cache.daily_bar_cache""")
q("A6b cache window",
 """SELECT COUNT(*) n, SUM(amount IS NULL) nulls, SUM(amount IS NOT NULL AND amount<=0) zeros
    FROM cache.daily_bar_cache WHERE trade_date>='2023-09-04' AND trade_date<='2026-09-04'""")

# 7. symbol format check
q("A7 sample symbols hist", "SELECT symbol FROM daily_bars LIMIT 5")
q("A7b sample symbols cache", "SELECT symbol FROM cache.daily_bar_cache LIMIT 5")
q("A7c symbol overlap counts",
 """SELECT (SELECT COUNT(DISTINCT symbol) FROM daily_bars),
           (SELECT COUNT(DISTINCT symbol) FROM cache.daily_bar_cache),
           (SELECT COUNT(*) FROM (SELECT DISTINCT symbol FROM daily_bars INTERSECT SELECT DISTINCT symbol FROM cache.daily_bar_cache))""")
con.close()
