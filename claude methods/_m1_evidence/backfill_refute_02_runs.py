import sqlite3
OP = r"D:/codex-A股交易/trading_local.sqlite3"
op = sqlite3.connect(f"file:{OP}?mode=ro", uri=True); op.row_factory = sqlite3.Row

def show(title, sql, params=()):
    print("\n"+"="*100); print(title); print("-- SQL:", " ".join(sql.split()))
    try: rows = op.execute(sql, params).fetchall()
    except Exception as e: print("   ERROR:", e); return []
    if not rows: print("   (no rows)"); return []
    cols = rows[0].keys(); print("   " + " | ".join(cols))
    for r in rows[:80]: print("   " + " | ".join(str(r[c]) for c in cols))
    if len(rows)>80: print(f"   ...{len(rows)-80} more")
    return rows

print("#"*100); print("# CHECK A: what ENDPOINT/PROVIDER do the failing capital-flow runs actually hit?")
print("#   (their claim: 'against the same host' as stock_zh_a_hist / push2his.eastmoney.com)")
print("#"*100)

show("A1. Distinct provider+endpoint across ALL runs -- is it the same endpoint family as the bar path?",
"""
SELECT provider, endpoint, scope, COUNT(*) AS runs,
       MIN(started_at) AS first_run, MAX(started_at) AS last_run
FROM capital_flow_ingestion_runs
GROUP BY provider, endpoint, scope
ORDER BY runs DESC
""")

show("A2. Every run in full chronological order (no aggregation)",
"""
SELECT id, scope, symbol, status, error_type, endpoint,
       fetched_count, accepted_count, duplicate_count, rejected_count,
       latest_trade_date, started_at
FROM capital_flow_ingestion_runs
ORDER BY started_at
""")

print("\n"+"#"*100); print("# CHECK B: is 'accepted_count>0' the right success test? duplicates count as WORKING fetches.")
print("#"*100)

show("B1. Re-scored: a run that FETCHED rows reached the host, even if all were duplicates",
"""
SELECT COUNT(*)                                              AS runs_total,
       SUM(CASE WHEN fetched_count  > 0 THEN 1 ELSE 0 END)   AS runs_that_FETCHED_rows,
       SUM(CASE WHEN accepted_count > 0 THEN 1 ELSE 0 END)   AS runs_that_ACCEPTED_rows,
       SUM(CASE WHEN duplicate_count> 0 THEN 1 ELSE 0 END)   AS runs_with_duplicates,
       SUM(CASE WHEN error_type IS NULL OR error_type='' THEN 1 ELSE 0 END) AS runs_with_NO_error
FROM capital_flow_ingestion_runs
""")

show("B2. Did capital-flow data actually land in the snapshot table? (the outcome that matters)",
"""
SELECT COUNT(*) AS snapshot_rows, COUNT(DISTINCT symbol) AS syms,
       MIN(trade_date) AS first_td, MAX(trade_date) AS last_td
FROM capital_flow_snapshots
""")

print("\n"+"#"*100); print("# CHECK C: the 2026-07-15 event -- did the lead endpoint fail MID-RUN and hand off?")
print("#"*100)

show("C1. Writes per source on 2026-07-15 (the only day stock_zh_a_hist ever wrote)",
"""
SELECT source, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS syms,
       MIN(updated_at) AS first_write, MAX(updated_at) AS last_write
FROM daily_bar_cache
WHERE substr(updated_at,1,10)='2026-07-15'
GROUP BY source ORDER BY first_write
""")

show("C2. Interleaving: minute-by-minute writer on 2026-07-15 -- shows the handoff",
"""
SELECT substr(updated_at,12,5) AS minute, source,
       COUNT(DISTINCT symbol) AS syms
FROM daily_bar_cache
WHERE substr(updated_at,1,10)='2026-07-15'
GROUP BY minute, source ORDER BY minute
""")

print("\n"+"#"*100); print("# CHECK D: ALTERNATIVE EXPLANATION -- was the endpoint retried at all after 07-15,")
print("#   or did the POLICY simply change so nothing ever asked it again?")
print("#"*100)

show("D1. Which sources wrote in the 51 'silent' days (2026-07-16..2026-09-04)?\n"
     "    akshare.stock_zh_a_daily is NOT a member of the akshare_first chain --\n"
     "    if it dominates, akshare_first was not the policy in force.",
"""
SELECT source, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS syms,
       MIN(substr(updated_at,1,10)) AS first_day, MAX(substr(updated_at,1,10)) AS last_day
FROM daily_bar_cache
WHERE substr(updated_at,1,10) BETWEEN '2026-07-16' AND '2026-09-04'
GROUP BY source ORDER BY rows DESC
""")

show("D2. Exact silent-day gap arithmetic (julianday, not string math)",
"""
SELECT MAX(updated_at) AS last_eastmoney_write,
       (SELECT MAX(updated_at) FROM daily_bar_cache) AS newest_write_anywhere,
       CAST(julianday(substr((SELECT MAX(updated_at) FROM daily_bar_cache WHERE source<>'error'),1,10))
          - julianday(substr(MAX(updated_at),1,10)) AS INT) AS days_silent
FROM daily_bar_cache WHERE source='akshare.stock_zh_a_hist'
""")

print("\n"+"#"*100); print("# CHECK E: the 2 eastmoney-ONLY symbols -- is any real data at risk?")
print("#"*100)

show("E1. Symbols whose ONLY source is akshare.stock_zh_a_hist",
"""
SELECT symbol, COUNT(*) AS rows, MIN(trade_date) AS first_bar, MAX(trade_date) AS last_bar
FROM daily_bar_cache
WHERE symbol IN (
  SELECT symbol FROM daily_bar_cache GROUP BY symbol
  HAVING COUNT(DISTINCT source)=1 AND MIN(source)='akshare.stock_zh_a_hist'
)
GROUP BY symbol
""")

show("E2. Row-level redundancy: of the 8,254 eastmoney rows, how many (symbol,trade_date)\n"
     "    keys are ALSO present from a different source?",
"""
SELECT COUNT(*) AS eastmoney_rows,
       SUM(CASE WHEN dup>0 THEN 1 ELSE 0 END) AS also_held_by_other_source,
       SUM(CASE WHEN dup=0 THEN 1 ELSE 0 END) AS unique_to_eastmoney
FROM (
  SELECT e.symbol, e.trade_date,
         (SELECT COUNT(*) FROM daily_bar_cache o
           WHERE o.symbol=e.symbol AND o.trade_date=e.trade_date
             AND o.source<>'akshare.stock_zh_a_hist') AS dup
  FROM daily_bar_cache e WHERE e.source='akshare.stock_zh_a_hist'
)
""")
op.close()
