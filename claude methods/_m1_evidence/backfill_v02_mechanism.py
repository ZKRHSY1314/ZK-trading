import sqlite3
MH=r"D:\codex-A股交易\market_history.sqlite3"
TL=r"D:\codex-A股交易\trading_local.sqlite3"
c=sqlite3.connect(f"file:{MH}?mode=ro",uri=True)
c.execute(f"ATTACH DATABASE 'file:{TL}?mode=ro' AS tl")
def q(label,sql,p=()):
    print(f"\n--- {label}\nSQL: {' '.join(sql.split())}")
    for r in c.execute(sql,p): print("   ",r)

q("D1 provider x date-range x fetched_at range in daily_bars",
  "SELECT provider, MIN(trade_date), MAX(trade_date), MIN(fetched_at), MAX(fetched_at), COUNT(*) FROM daily_bars GROUP BY 1 ORDER BY 6 DESC")
q("D2 akshare-vs-tencent boundary: rows per trade_date bucket by provider family",
  "SELECT substr(trade_date,1,7) ym, SUM(provider LIKE 'tencent%') tencent, SUM(provider LIKE 'akshare%') akshare, COUNT(*) tot FROM daily_bars GROUP BY 1 ORDER BY 1 DESC LIMIT 24")

q("E1 ingest_runs tail (last 16)",
  "SELECT id, provider, status, started_at, completed_at, requested_symbol_count, processed_symbol_count, inserted_row_count, updated_row_count, rejected_row_count, substr(parameters_json,1,120) FROM ingest_runs ORDER BY id DESC LIMIT 16")
q("E2 ingest_runs aggregate by requested_at session",
  "SELECT requested_at, COUNT(*) runs, SUM(processed_symbol_count) syms, SUM(inserted_row_count) ins, SUM(updated_row_count) upd, SUM(rejected_row_count) rej FROM ingest_runs GROUP BY 1 ORDER BY 1 DESC LIMIT 12")
q("E3 distinct bars_per_symbol-ish params seen",
  "SELECT DISTINCT parameters_json FROM ingest_runs LIMIT 12")

q("F1 VALIDITY: for repairable rows, does cache VOLUME match daily_bars VOLUME? (same-bar proof)",
  """SELECT CASE WHEN d.volume IS NULL OR c.volume IS NULL THEN 'null_side'
        WHEN d.volume=c.volume THEN 'exact_match'
        WHEN ABS(d.volume-c.volume) <= 0.005*MAX(d.volume,c.volume) THEN 'within_0.5pct'
        ELSE 'MISMATCH' END k, COUNT(*)
     FROM daily_bars d JOIN tl.daily_bar_cache c ON c.symbol=d.symbol AND c.trade_date=d.trade_date
     WHERE d.amount IS NULL AND c.amount IS NOT NULL AND c.quality_status='ready' AND c.adjustment_mode='qfq'
     GROUP BY 1 ORDER BY 2 DESC""")
q("F2 VALIDITY: implied VWAP from cache amount/volume vs daily_bars qfq low..high band",
  """SELECT CASE WHEN c.volume IS NULL OR c.volume=0 THEN 'no_vol'
        WHEN (c.amount/(c.volume*100.0)) BETWEEN d.low*0.98 AND d.high*1.02 THEN 'vwap_in_band_hand'
        WHEN (c.amount/c.volume) BETWEEN d.low*0.98 AND d.high*1.02 THEN 'vwap_in_band_share'
        ELSE 'OUT_OF_BAND' END k, COUNT(*)
     FROM daily_bars d JOIN tl.daily_bar_cache c ON c.symbol=d.symbol AND c.trade_date=d.trade_date
     WHERE d.amount IS NULL AND c.amount IS NOT NULL AND c.quality_status='ready' AND c.adjustment_mode='qfq'
     GROUP BY 1 ORDER BY 2 DESC""")
q("F3 CONTROL: rows where BOTH stores have amount -- do they agree?",
  """SELECT CASE WHEN d.amount=c.amount THEN 'exact' WHEN ABS(d.amount-c.amount)<=0.005*MAX(d.amount,c.amount) THEN 'within_0.5pct' ELSE 'DISAGREE' END k,
        COUNT(*) FROM daily_bars d JOIN tl.daily_bar_cache c ON c.symbol=d.symbol AND c.trade_date=d.trade_date
     WHERE d.amount IS NOT NULL AND c.amount IS NOT NULL GROUP BY 1 ORDER BY 2 DESC""")
q("F4 CONTROL: close price agreement on repairable rows (qfq base drift check)",
  """SELECT CASE WHEN ABS(d.close-c.close)<=0.005*MAX(d.close,c.close) THEN 'close_agrees' ELSE 'close_differs' END k, COUNT(*)
     FROM daily_bars d JOIN tl.daily_bar_cache c ON c.symbol=d.symbol AND c.trade_date=d.trade_date
     WHERE d.amount IS NULL AND c.amount IS NOT NULL AND c.quality_status='ready' AND c.adjustment_mode='qfq' GROUP BY 1 ORDER BY 2 DESC""")

q("G1 cache ready+qfq rows with NO daily_bars row at all (never promoted)",
  "SELECT COUNT(*) FROM tl.daily_bar_cache c WHERE c.quality_status='ready' AND c.adjustment_mode='qfq' AND NOT EXISTS (SELECT 1 FROM daily_bars d WHERE d.symbol=c.symbol AND d.trade_date=c.trade_date)")
q("G2 that residue by source and by year",
  """SELECT c.source, substr(c.trade_date,1,4) yr, COUNT(*) FROM tl.daily_bar_cache c
     WHERE c.quality_status='ready' AND c.adjustment_mode='qfq' AND NOT EXISTS (SELECT 1 FROM daily_bars d WHERE d.symbol=c.symbol AND d.trade_date=c.trade_date)
     GROUP BY 1,2 ORDER BY 3 DESC LIMIT 15""")
c.close()
