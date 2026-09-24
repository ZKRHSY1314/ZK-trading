import sqlite3
CACHE = r"D:/codex-A股交易/trading_local.sqlite3"
HIST  = r"D:/codex-A股交易/market_history.sqlite3"
con = sqlite3.connect(f"file:{HIST}?mode=ro", uri=True)
con.execute("ATTACH DATABASE ? AS cache", (f"file:{CACHE}?mode=ro",))
con.row_factory = sqlite3.Row
def q(label, sql, params=()):
    print("\n### "+label, flush=True)
    print("SQL:", " ".join(sql.split()), flush=True)
    for r in con.execute(sql, params).fetchall()[:40]:
        print("   ", dict(r), flush=True)

q("H date floor/ceiling of BOTH stores",
  """SELECT 'cache_qfq_ready' AS store, MIN(trade_date) d0, MAX(trade_date) d1, COUNT(*) n
       FROM cache.daily_bar_cache WHERE trade_date!='ERROR' AND adjustment_mode='qfq' AND quality_status='ready'
     UNION ALL
     SELECT 'cache_all', MIN(trade_date), MAX(trade_date), COUNT(*) FROM cache.daily_bar_cache WHERE trade_date!='ERROR'
     UNION ALL
     SELECT 'hist_all', MIN(trade_date), MAX(trade_date), COUNT(*) FROM main.daily_bars""")

q("I cache rows by year, and how many have a hist twin (cheap year buckets)",
  """SELECT substr(c.trade_date,1,4) AS yr, COUNT(*) AS cache_rows
       FROM cache.daily_bar_cache c WHERE c.trade_date!='ERROR' GROUP BY 1 ORDER BY 1""")
q("I2 hist rows by year",
  "SELECT substr(trade_date,1,4) AS yr, COUNT(*) AS hist_rows FROM main.daily_bars GROUP BY 1 ORDER BY 1")

q("J WHY the cache-only rows are excluded: classify cache rows that fail the seeder filters",
  """SELECT
       SUM(CASE WHEN quality_status!='ready' THEN 1 ELSE 0 END) AS not_ready,
       SUM(CASE WHEN adjustment_mode!='qfq' THEN 1 ELSE 0 END) AS not_qfq,
       SUM(CASE WHEN lower(COALESCE(source,'')) LIKE '%sina%'
                 AND lower(COALESCE(source,''))!='tencent.fqkline.raw+sina.qfq_factor.unit_verified'
                THEN 1 ELSE 0 END) AS untrusted_sina,
       COUNT(*) AS total_nonerror
     FROM cache.daily_bar_cache WHERE trade_date!='ERROR'""")

q("K seeder-eligible cache rows (passes ALL filters) vs hist rows -- the real 'loss' denominator",
  """SELECT COUNT(*) AS cache_rows_passing_seeder_filters
       FROM cache.daily_bar_cache
      WHERE trade_date!='ERROR' AND quality_status='ready' AND adjustment_mode='qfq'
        AND (lower(COALESCE(source,'')) NOT LIKE '%sina%'
             OR lower(COALESCE(source,''))='tencent.fqkline.raw+sina.qfq_factor.unit_verified')""")
con.close()
