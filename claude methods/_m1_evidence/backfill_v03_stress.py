import sqlite3
MH=r"D:\codex-A股交易\market_history.sqlite3"
TL=r"D:\codex-A股交易\trading_local.sqlite3"
c=sqlite3.connect(f"file:{MH}?mode=ro",uri=True)
c.execute(f"ATTACH DATABASE 'file:{TL}?mode=ro' AS tl")
def q(label,sql,p=()):
    print(f"\n--- {label}\nSQL: {' '.join(sql.split())}")
    for r in c.execute(sql,p): print("   ",r)

q("H1 daily_bars rows attributable to each ingest session (where did 753,717 come from?)",
  """SELECT r.requested_at, COUNT(*) bars_rows, SUM(d.amount IS NULL) amt_null
     FROM daily_bars d JOIN ingest_runs r ON r.id=d.ingest_run_id GROUP BY 1 ORDER BY 1 DESC LIMIT 8""")
q("H2 ingest_runs 89-100 vs 90-100 processed-symbol sums (their '5,056')",
  "SELECT 'ids_89_100' k, SUM(processed_symbol_count) FROM ingest_runs WHERE id BETWEEN 89 AND 100 UNION ALL SELECT 'ids_90_100', SUM(processed_symbol_count) FROM ingest_runs WHERE id BETWEEN 90 AND 100")
q("H3 the 11:24:33 session: inserted vs updated vs their 753,717",
  "SELECT SUM(inserted_row_count) ins, SUM(updated_row_count) upd, SUM(inserted_row_count)+SUM(updated_row_count) touched, SUM(processed_symbol_count) syms FROM ingest_runs WHERE requested_at='2026-09-04T11:24:33+08:00'")

q("I1 distinct trade_dates carried by akshare.stock_zh_a_daily in daily_bars (is it really 150?)",
  "SELECT COUNT(DISTINCT trade_date) sessions, MIN(trade_date), MAX(trade_date) FROM daily_bars WHERE provider='akshare.stock_zh_a_daily'")
q("I2 distinct trade_dates in daily_bars total, and last-150-session cutoff date",
  "SELECT COUNT(DISTINCT trade_date) FROM daily_bars")
q("I3 amount-null rate on/after the akshare boundary vs before",
  """SELECT CASE WHEN trade_date>='2026-02-01' THEN 'from_2026_02' ELSE 'before_2026_02' END k,
       COUNT(*) rows, SUM(amount IS NULL) nulls, ROUND(100.0*SUM(amount IS NULL)/COUNT(*),1) pct FROM daily_bars GROUP BY 1""")

q("J1 CACHE-INTERNAL consistency: is cache.amount consistent with cache's OWN ohlc? (repairable set)",
  """SELECT CASE WHEN c.volume IS NULL OR c.volume=0 THEN 'no_vol'
        WHEN (c.amount/(c.volume*100.0)) BETWEEN c.low*0.98 AND c.high*1.02 THEN 'self_consistent_hand'
        ELSE 'SELF_INCONSISTENT' END k, COUNT(*)
     FROM daily_bars d JOIN tl.daily_bar_cache c ON c.symbol=d.symbol AND c.trade_date=d.trade_date
     WHERE d.amount IS NULL AND c.amount IS NOT NULL AND c.quality_status='ready' AND c.adjustment_mode='qfq'
     GROUP BY 1 ORDER BY 2 DESC""")
q("J2 how many repairable rows land on a bar whose OHLC disagrees between stores (mixed-frame risk)",
  """SELECT CASE WHEN ABS(d.close-c.close)<=0.005*MAX(d.close,c.close) THEN 'same_price_frame' ELSE 'DIFFERENT_PRICE_FRAME' END frame,
        CASE WHEN d.volume IS NOT NULL AND c.volume IS NOT NULL AND ABS(d.volume-c.volume)<=0.005*MAX(d.volume,c.volume) THEN 'vol_ok' ELSE 'vol_diff' END vol,
        COUNT(*)
     FROM daily_bars d JOIN tl.daily_bar_cache c ON c.symbol=d.symbol AND c.trade_date=d.trade_date
     WHERE d.amount IS NULL AND c.amount IS NOT NULL AND c.quality_status='ready' AND c.adjustment_mode='qfq'
     GROUP BY 1,2 ORDER BY 3 DESC""")
q("J3 for DIFFERENT_PRICE_FRAME rows: is close ratio == volume ratio (pure qfq rebase) ?",
  """SELECT CASE WHEN c.volume IS NULL OR c.volume=0 OR d.volume IS NULL OR d.volume=0 THEN 'no_vol'
        WHEN ABS( (d.close/c.close) - (c.volume/d.volume) ) <= 0.02 THEN 'pure_qfq_rebase'
        ELSE 'NOT_A_REBASE' END k, COUNT(*)
     FROM daily_bars d JOIN tl.daily_bar_cache c ON c.symbol=d.symbol AND c.trade_date=d.trade_date
     WHERE d.amount IS NULL AND c.amount IS NOT NULL AND c.quality_status='ready' AND c.adjustment_mode='qfq'
       AND ABS(d.close-c.close)>0.005*MAX(d.close,c.close) AND c.close>0 AND d.close>0
     GROUP BY 1 ORDER BY 2 DESC""")

q("K1 PROVENANCE FRAMING: mismatched-provider rows -- does daily_bars still hold DIFFERENT values than cache?",
  """SELECT CASE WHEN ABS(d.close-c.close)<=1e-6 THEN 'values_identical' ELSE 'values_differ' END k, COUNT(*)
     FROM daily_bars d JOIN tl.daily_bar_cache c ON c.symbol=d.symbol AND c.trade_date=d.trade_date
     WHERE d.provider<>c.source GROUP BY 1 ORDER BY 2 DESC""")
q("K2 their provider-mismatch top row, reproduced",
  "SELECT d.provider, c.source, COUNT(*) FROM daily_bars d JOIN tl.daily_bar_cache c ON c.symbol=d.symbol AND c.trade_date=d.trade_date WHERE d.provider<>c.source GROUP BY 1,2 ORDER BY 3 DESC LIMIT 5")
q("K3 total provider-mismatch rows and pct of store",
  "SELECT COUNT(*) mism, (SELECT COUNT(*) FROM daily_bars) tot, ROUND(100.0*COUNT(*)/(SELECT COUNT(*) FROM daily_bars),1) pct FROM daily_bars d JOIN tl.daily_bar_cache c ON c.symbol=d.symbol AND c.trade_date=d.trade_date WHERE d.provider<>c.source")
q("K4 do tencent-provider daily_bars rows have fetched_at BEFORE the cache row's updated_at? (lineage is point-in-time, not wrong)",
  """SELECT CASE WHEN d.fetched_at < c.updated_at THEN 'db_fetched_before_cache_update' ELSE 'db_fetched_after' END k, COUNT(*)
     FROM daily_bars d JOIN tl.daily_bar_cache c ON c.symbol=d.symbol AND c.trade_date=d.trade_date
     WHERE d.provider LIKE 'tencent%' AND c.source='akshare.stock_zh_a_daily' GROUP BY 1 ORDER BY 2 DESC""")
c.close()
