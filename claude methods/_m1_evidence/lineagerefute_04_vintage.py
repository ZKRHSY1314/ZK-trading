import sqlite3
CACHE = r"D:/codex-A股交易/trading_local.sqlite3"
HIST  = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{HIST}?mode=ro", uri=True); c.execute("PRAGMA query_only=ON")
c.execute(f"ATTACH DATABASE 'file:{CACHE}?mode=ro' AS cache")
def show(t, sql):
    cur=c.execute(sql); names=[d[0] for d in cur.description]
    print(f"\n=== {t} ===")
    for row in cur.fetchall():
        print("   " + " | ".join(f"{n}={v}" for n,v in zip(names,row)))

show("A. is hist STALE relative to cache? (direction of timestamp on divergent rows)", """
SELECT
 SUM(CASE WHEN datetime(h.updated_at) <  datetime(k.updated_at) THEN 1 ELSE 0 END) AS hist_older,
 SUM(CASE WHEN datetime(h.updated_at) =  datetime(k.updated_at) THEN 1 ELSE 0 END) AS same_ts,
 SUM(CASE WHEN datetime(h.updated_at) >  datetime(k.updated_at) THEN 1 ELSE 0 END) AS hist_newer,
 COUNT(*) AS divergent_rows
FROM main.daily_bars h JOIN cache.daily_bar_cache k
  ON k.symbol=h.symbol AND k.trade_date=h.trade_date
WHERE NOT (h.open IS k.open AND h.high IS k.high AND h.low IS k.low AND h.close IS k.close
           AND h.volume IS k.volume AND h.amount IS k.amount AND h.provider IS k.source)
""")

show("B. second-writer test: adjustment_mode + ingest_run_id integrity", """
SELECT (SELECT COUNT(DISTINCT adjustment_mode) FROM main.daily_bars)              AS distinct_adj_modes,
       (SELECT group_concat(DISTINCT adjustment_mode) FROM main.daily_bars)       AS adj_modes,
       (SELECT COUNT(*) FROM main.daily_bars WHERE ingest_run_id IS NULL)         AS null_ingest_run,
       (SELECT COUNT(*) FROM main.daily_bars b
          WHERE b.ingest_run_id IS NOT NULL
            AND NOT EXISTS(SELECT 1 FROM main.ingest_runs r WHERE r.id=b.ingest_run_id)) AS orphan_ingest_run,
       (SELECT COUNT(DISTINCT provider) FROM main.ingest_runs)                    AS distinct_run_providers,
       (SELECT COUNT(*) FROM main.ingest_runs
          WHERE provider <> 'trading_local.daily_bar_cache')                      AS runs_not_from_cache
""")

show("C. any hist provider value absent from cache.source vocabulary?", """
SELECT provider, COUNT(*) AS rows FROM main.daily_bars
WHERE provider NOT IN (SELECT DISTINCT source FROM cache.daily_bar_cache)
GROUP BY 1 ORDER BY 2 DESC
""")

show("D. CORRECTED cache_only, namespace-normalised, index-excluded, window-scoped", """
WITH ck AS (
  SELECT CASE WHEN symbol GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]'
              THEN (SELECT i.symbol FROM main.instruments i
                    WHERE i.symbol IN ('SH'||c.symbol,'SZ'||c.symbol,'BJ'||c.symbol) LIMIT 1)
              ELSE symbol END AS nsym,
         symbol AS raw, trade_date, quality_status, adjustment_mode, source
  FROM cache.daily_bar_cache c
  WHERE trade_date <> 'ERROR' AND length(trade_date)=10
)
SELECT
 (SELECT COUNT(*) FROM ck) AS cache_rows_valid_date,
 (SELECT COUNT(*) FROM ck WHERE NOT EXISTS
    (SELECT 1 FROM main.daily_bars b WHERE b.symbol=ck.raw AND b.trade_date=ck.trade_date))
   AS cache_only_THEIR_join,
 (SELECT COUNT(*) FROM ck WHERE nsym IS NOT NULL AND NOT EXISTS
    (SELECT 1 FROM main.daily_bars b WHERE b.symbol=ck.nsym AND b.trade_date=ck.trade_date))
   AS cache_only_namespace_normalised,
 (SELECT COUNT(*) FROM ck WHERE nsym IS NOT NULL AND NOT EXISTS
    (SELECT 1 FROM main.daily_bars b WHERE b.symbol=ck.nsym AND b.trade_date=ck.trade_date)
    AND EXISTS (SELECT 1 FROM main.instruments i WHERE i.symbol=ck.nsym AND i.exchange<>'INDEX'))
   AS cache_only_stocks_only,
 (SELECT COUNT(*) FROM ck WHERE nsym IS NOT NULL AND NOT EXISTS
    (SELECT 1 FROM main.daily_bars b WHERE b.symbol=ck.nsym AND b.trade_date=ck.trade_date)
    AND EXISTS (SELECT 1 FROM main.instruments i WHERE i.symbol=ck.nsym AND i.exchange<>'INDEX')
    AND ck.trade_date BETWEEN '2023-09-04' AND '2026-09-04')
   AS cache_only_stocks_in_window
""")

show("E. WHY are the cache-only rows absent? (seeder filters explain them)", """
WITH miss AS (
  SELECT c.* FROM cache.daily_bar_cache c
  WHERE c.trade_date<>'ERROR' AND length(c.trade_date)=10
    AND NOT EXISTS (SELECT 1 FROM main.daily_bars b
                    WHERE b.symbol=c.symbol AND b.trade_date=c.trade_date)
)
SELECT
  SUM(quality_status<>'ready')                                     AS not_ready,
  SUM(adjustment_mode<>'qfq')                                      AS not_qfq,
  SUM(lower(COALESCE(source,'')) LIKE '%sina%'
      AND lower(COALESCE(source,''))<>'tencent.fqkline.raw+sina.qfq_factor.unit_verified')
                                                                   AS untrusted_sina,
  SUM(symbol GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]')                AS bare_symbol_dupes,
  SUM(quality_status='ready' AND adjustment_mode='qfq')            AS ready_and_qfq_yet_absent,
  COUNT(*)                                                         AS total_missing
FROM miss
""")

show("F. hist rows whose value no longer exists ANYWHERE in the cache (vintage-only info)", """
SELECT COUNT(*) AS hist_rows_with_no_surviving_cache_equivalent
FROM main.daily_bars h JOIN cache.daily_bar_cache k
  ON k.symbol=h.symbol AND k.trade_date=h.trade_date
WHERE h.close IS NOT k.close
""")
