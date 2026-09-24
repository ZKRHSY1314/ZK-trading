import sqlite3
OP = r"D:/codex-A股交易/trading_local.sqlite3"
op = sqlite3.connect(f"file:{OP}?mode=ro", uri=True); op.row_factory = sqlite3.Row
def show(t, sql):
    print("\n"+"="*100); print(t); print("-- SQL:", " ".join(sql.split()))
    rows = op.execute(sql).fetchall()
    if not rows: print("   (none)"); return
    c = rows[0].keys(); print("   "+" | ".join(c))
    for r in rows[:40]: print("   "+" | ".join(str(r[x]) for x in c))

print("#"*100)
print("# F1: WHY did 8,254 eastmoney rows survive the 2026-09-03 Sina rebuild?")
print("#     daily_bar_cache has UNIQUE(symbol,trade_date), so an overlapping upsert would")
print("#     have relabelled them. Surviving rows = dates Sina never covered.")
print("#"*100)

show("F1a. Year-month of the surviving eastmoney rows vs the Sina floor (Sina first_bar=2024-06-04)",
"""
SELECT substr(trade_date,1,7) AS ym, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS syms
FROM daily_bar_cache WHERE source='akshare.stock_zh_a_hist'
GROUP BY ym ORDER BY ym
""")

show("F1b. Split the surviving eastmoney rows around the Sina coverage floor",
"""
SELECT CASE WHEN trade_date < '2024-06-04' THEN 'before_sina_floor' ELSE 'inside_sina_range' END AS zone,
       COUNT(*) AS rows, COUNT(DISTINCT symbol) AS syms,
       MIN(trade_date) AS first_bar, MAX(trade_date) AS last_bar
FROM daily_bar_cache WHERE source='akshare.stock_zh_a_hist'
GROUP BY zone
""")

print("\n"+"#"*100)
print("# F2: Is the eastmoney source in the LIVE path? Empirical test on the last backfill day.")
print("#     Under akshare_first, stock_zh_a_hist is tried FIRST for every symbol.")
print("#     Under tonghuasun_first it is 4th of 4 and Sina (position 2) carries 成交额.")
print("#"*100)

show("F2a. Sources that wrote on 2026-09-03/04 -- this IS the chain that ran",
"""
SELECT source, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS syms
FROM daily_bar_cache WHERE substr(updated_at,1,10) IN ('2026-09-03','2026-09-04')
GROUP BY source ORDER BY rows DESC
""")

show("F2b. Does the freshest chain actually carry 成交额 (amount)? -- the harm the claim asserts",
"""
SELECT source, COUNT(*) AS rows,
       SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) AS amount_null,
       ROUND(100.0*SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END)/COUNT(*),2) AS pct_null
FROM daily_bar_cache WHERE substr(updated_at,1,10) IN ('2026-09-03','2026-09-04')
GROUP BY source ORDER BY rows DESC
""")

print("\n"+"#"*100)
print("# F3: severity test -- are the 123 stale symbols still stale TODAY, or refreshed by Sina")
print("#     at other dates? (per-symbol max trade_date across ALL sources)")
print("#"*100)

show("F3a. For the 123 symbols eastmoney touched, freshest bar from ANY source",
"""
SELECT CASE WHEN mx >= '2026-09-04' THEN 'fresh_to_2026-09-04'
            WHEN mx >= '2026-09-01' THEN 'fresh_within_sept'
            ELSE 'STALE_' || mx END AS freshness,
       COUNT(*) AS symbols
FROM (SELECT symbol, MAX(trade_date) AS mx FROM daily_bar_cache
      WHERE symbol IN (SELECT DISTINCT symbol FROM daily_bar_cache
                       WHERE source='akshare.stock_zh_a_hist')
      GROUP BY symbol)
GROUP BY freshness ORDER BY symbols DESC
""")
op.close()
