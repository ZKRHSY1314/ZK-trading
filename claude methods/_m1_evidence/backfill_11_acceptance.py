"""BEFORE-side acceptance queries. Read-only; run again AFTER promotion and diff."""
import sqlite3, os, json
ROOT=r"D:\codex-A股交易"
tl=sqlite3.connect(f"file:{os.path.join(ROOT,'trading_local.sqlite3')}?mode=ro",uri=True); tl.row_factory=sqlite3.Row
mh=sqlite3.connect(f"file:{os.path.join(ROOT,'market_history.sqlite3')}?mode=ro",uri=True); mh.row_factory=sqlite3.Row
A={}
def run(db,key,sql):
    A[key]=[dict(r) for r in db.execute(sql).fetchall()]
    print(f"--- {key}\nSQL: {' '.join(sql.split())}")
    for r in A[key][:12]: print("   ",r)
    print()

run(mh,"A1_coverage_by_year","""
 SELECT substr(trade_date,1,4) AS yr, COUNT(*) rows, COUNT(DISTINCT symbol) syms,
        COUNT(DISTINCT trade_date) sessions
 FROM daily_bars WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'
 GROUP BY yr ORDER BY yr""")
run(mh,"A2_untouched_rows_fingerprint","""
 SELECT COUNT(*) rows, SUM(length(row_hash)) hashlen,
        MIN(trade_date) mn, MAX(trade_date) mx
 FROM daily_bars WHERE trade_date >= '2024-04-09'""")
run(mh,"A3_constraint_health","""
 SELECT SUM(high < low) bad_hl, SUM(high < open) bad_ho, SUM(low > close) bad_lc,
        SUM(close <= 0) bad_close, SUM(length(trade_date)<>10) bad_date,
        SUM(adjustment_mode NOT IN ('none','qfq','hfq')) bad_adj,
        SUM(volume_unit NOT IN ('hand','share','unknown')) bad_unit
 FROM daily_bars""")
run(mh,"A4_provider_mix","""
 SELECT provider, adjustment_mode, COUNT(*) rows FROM daily_bars
 GROUP BY provider, adjustment_mode ORDER BY rows DESC""")
run(mh,"A5_amount_completeness","""
 SELECT SUM(amount IS NULL) amount_null, COUNT(*) rows FROM daily_bars""")
run(mh,"A6_run_ledger","""
 SELECT COUNT(*) runs, SUM(inserted_row_count) ins, SUM(updated_row_count) upd,
        SUM(rejected_row_count) rej FROM ingest_runs""")
run(tl,"A7_cache_shape","""
 SELECT COUNT(*) rows, COUNT(DISTINCT symbol) syms, MIN(trade_date) mn, MAX(trade_date) mx,
        SUM(amount IS NULL) amount_null,
        SUM(adjustment_mode <> 'qfq') non_qfq,
        SUM(quality_status <> 'ready') non_ready
 FROM daily_bar_cache WHERE length(trade_date)=10""")
run(tl,"A8_untouched_control_slice","""
 SELECT COUNT(*) rows, ROUND(SUM(close),4) close_sum, ROUND(SUM(COALESCE(amount,0)),2) amt_sum
 FROM daily_bar_cache WHERE trade_date BETWEEN '2025-01-02' AND '2025-12-31'""")
run(tl,"A9_downstream_backtest_inputs","""
 SELECT COUNT(*) runs FROM historical_backtest_runs""")
with open("backfill_acceptance_BEFORE.json","w",encoding="utf-8") as f:
    json.dump(A,f,ensure_ascii=False,indent=1,default=str)
print("wrote backfill_acceptance_BEFORE.json")
