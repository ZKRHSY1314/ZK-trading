import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
TL=r"D:/codex-A股交易/trading_local.sqlite3"
c=sqlite3.connect(f"file:{TL}?mode=ro",uri=True)
tabs=["disclosure_facts","symbol_fundamental_snapshot","sector_membership_snapshots","sector_membership_history",
      "candidate_scans","candidate_scan_items","technical_indicators","market_regime_snapshots","global_market_bars",
      "capital_flow_snapshots","full_market_feature_runs","full_market_feature_state","historical_backtest_runs",
      "price_readiness_reports","import_runs","learning_samples","agent_learning_samples"]
print("### K1 PIT-relevant tables: row counts + whether they carry an as-of / available_at column")
for t in tabs:
    try:
        n=c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    except Exception as e:
        print(f"   {t}: ERROR {e}"); continue
    cols=[r[1] for r in c.execute(f"PRAGMA table_info({t})")]
    pit=[x for x in cols if x in ("available_at","as_of","observed_at","snapshot_date","first_seen_at","retrieved_at","effective_at","decision_cutoff","trade_date","created_at")]
    print(f"   {t:34s} rows={n:<10d} pit_cols={pit}")
print("\n### K2 symbol_fundamental_snapshot available_at range (the one table with real PIT gating in code)")
try:
    print("SQL: SELECT COUNT(*), MIN(as_of), MAX(as_of), MIN(available_at), MAX(available_at) FROM symbol_fundamental_snapshot")
    print("   ", c.execute("SELECT COUNT(*), MIN(as_of), MAX(as_of), MIN(available_at), MAX(available_at) FROM symbol_fundamental_snapshot").fetchone())
except Exception as e: print("   ", e)
print("\n### K3 disclosure_facts (bitemporal ledger) volume")
try:
    print("SQL: SELECT COUNT(*), MIN(available_at), MAX(available_at) FROM disclosure_facts")
    print("   ", c.execute("SELECT COUNT(*), MIN(available_at), MAX(available_at) FROM disclosure_facts").fetchone())
except Exception as e: print("   ", e)
print("\n### K4 historical_backtest_runs date ranges actually exercised")
try:
    cols=[r[1] for r in c.execute("PRAGMA table_info(historical_backtest_runs)")]
    print("   cols:", cols)
    for r in c.execute("SELECT * FROM historical_backtest_runs ORDER BY id DESC LIMIT 3"):
        print("   ", dict(zip(cols, r)))
except Exception as e: print("   ", e)
c.close()
