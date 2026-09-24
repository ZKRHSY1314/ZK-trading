import sqlite3, time
TL=r"D:/codex-A股交易/trading_local.sqlite3"; MH=r"D:/codex-A股交易/market_history.sqlite3"
def ro(p):
    c=sqlite3.connect(f"file:{p}?mode=ro",uri=True); c.execute("PRAGMA query_only=1"); return c
tl=ro(TL); mh=ro(MH)
def show(title,cur):
    print("\n###",title)
    cols=[d[0] for d in cur.description]
    print(" | ".join(cols))
    for r in cur.fetchall(): print(" | ".join("" if v is None else str(v) for v in r))

print("=== FIELD AVAILABILITY: per-column NULL census (contract item, absent from report) ===")
show("daily_bar_cache NULL counts (valid dates only)", tl.execute("""
SELECT COUNT(*) rows, SUM(open IS NULL) open_null, SUM(high IS NULL) high_null,
       SUM(low IS NULL) low_null, SUM(close IS NULL) close_null, SUM(volume IS NULL) vol_null,
       SUM(amount IS NULL) amt_null, SUM(source IS NULL OR source='') src_null,
       SUM(quality_status IS NULL) qs_null, SUM(adjustment_mode IS NULL) am_null,
       SUM(volume_unit IS NULL) vu_null, SUM(created_at IS NULL) cr_null, SUM(updated_at IS NULL) up_null
FROM daily_bar_cache WHERE length(trade_date)=10"""))
show("daily_bar_cache NULL counts, ready+qfq only", tl.execute("""
SELECT COUNT(*) rows, SUM(open IS NULL) open_null, SUM(close IS NULL) close_null,
       SUM(volume IS NULL) vol_null, SUM(amount IS NULL) amt_null
FROM daily_bar_cache WHERE length(trade_date)=10 AND quality_status='ready' AND adjustment_mode='qfq'"""))
show("daily_bars NULL counts", mh.execute("""
SELECT COUNT(*) rows, SUM(open IS NULL) open_null, SUM(high IS NULL) high_null, SUM(low IS NULL) low_null,
       SUM(close IS NULL) close_null, SUM(volume IS NULL) vol_null, SUM(amount IS NULL) amt_null,
       SUM(available_at IS NULL) avail_null, SUM(row_hash IS NULL) hash_null,
       SUM(ingest_run_id IS NULL) run_null, SUM(provider IS NULL) prov_null
FROM daily_bars"""))

print("\n=== NON-POSITIVE / ABSURD PRICES beyond the 3 rows the report found ===")
show("cache: non-positive prices", tl.execute("""
SELECT SUM(open<=0) open_le0, SUM(high<=0) high_le0, SUM(low<=0) low_le0, SUM(close<=0) close_le0,
       SUM(volume<0) vol_neg, SUM(amount<0) amt_neg, SUM(volume=0) vol_zero,
       SUM(amount=0) amt_zero, SUM(volume>0 AND amount=0) v_pos_a_zero
FROM daily_bar_cache WHERE length(trade_date)=10"""))
show("market_history: non-positive prices", mh.execute("""
SELECT SUM(open<=0) open_le0, SUM(high<=0) high_le0, SUM(low<=0) low_le0, SUM(close<=0) close_le0,
       SUM(volume<0) vol_neg, SUM(volume=0) vol_zero FROM daily_bars"""))

print("\n=== SOURCE INVENTORY (contract: 'source'); report gives only a partial view ===")
show("daily_bar_cache by source", tl.execute("""
SELECT source, COUNT(*) rows, COUNT(DISTINCT symbol) syms, MIN(trade_date) mn, MAX(trade_date) mx,
       SUM(amount IS NULL) amt_null, COUNT(DISTINCT adjustment_mode) modes, COUNT(DISTINCT quality_status) qs
FROM daily_bar_cache WHERE length(trade_date)=10 GROUP BY source ORDER BY rows DESC"""))
show("daily_bars by provider", mh.execute("""
SELECT provider, COUNT(*) rows, COUNT(DISTINCT symbol) syms, MIN(trade_date) mn, MAX(trade_date) mx,
       SUM(amount IS NULL) amt_null, COUNT(DISTINCT volume_unit) vu
FROM daily_bars GROUP BY provider ORDER BY rows DESC"""))
show("daily_bars volume_unit x provider", mh.execute("SELECT volume_unit, provider, COUNT(*) FROM daily_bars GROUP BY 1,2 ORDER BY 3 DESC"))

print("\n=== UNIVERSE SNAPSHOTS: membership per snapshot (report never reports member counts) ===")
show("universe_snapshots", mh.execute("SELECT id, snapshot_date, COALESCE(source,'') src, COALESCE(created_at,'') created FROM universe_snapshots ORDER BY snapshot_date"))
show("members per snapshot", mh.execute("""
SELECT s.snapshot_date, COUNT(*) members FROM universe_members m JOIN universe_snapshots s ON s.id=m.snapshot_id
GROUP BY 1 ORDER BY 1"""))

print("\n=== FORECAST EVALUATIONS: orphan / window checks the report did not run ===")
cols=[r[1] for r in tl.execute("PRAGMA table_info(forecast_evaluations)")]
print("forecast_evaluations columns:", cols)
show("as_of range + status", tl.execute("SELECT status, COUNT(*), MIN(as_of), MAX(as_of) FROM forecast_evaluations GROUP BY 1"))
print("\n=== OTHER RESEARCH LEDGERS not inventoried in the report ===")
for t in ("learning_backtests","learning_reports","agent_learning_samples","agent_learning_outcomes",
          "agent_calibration_proposals","agent_sandbox_experiments","simulation_fills","historical_backtest_trades",
          "full_market_feature_state","candidate_scores","symbol_fundamental_snapshot","capital_flow_snapshots"):
    try:
        n=tl.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:38s} {n}")
    except Exception as e:
        print(f"  {t:38s} ERR {e}")
