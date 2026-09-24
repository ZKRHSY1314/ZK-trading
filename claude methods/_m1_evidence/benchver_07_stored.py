import sqlite3, json
con=sqlite3.connect(r"file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True)
print("=== STORED vs CLAIMED ===")
for rid,claimed_blk,claimed_evals in ((1,1626,1760),(13,4644,4810),(19,3082,3220)):
    sd,ed,mj=con.execute("SELECT start_date,end_date,metrics_json FROM historical_backtest_runs WHERE id=?",(rid,)).fetchone()
    m=json.loads(mj); stored=m.get("rejected_by_risk_count")
    nd=con.execute("SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ?",(sd,ed)).fetchone()[0]
    ns=con.execute("SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ? AND quality_status='ready'",(sd,ed)).fetchone()[0]
    print(f"  run {rid:<3} {sd}..{ed} stored_rejected_by_risk_count={stored:<6} claimed_blocked={claimed_blk:<6} delta={claimed_blk-stored:+d}")
    print(f"          claimed_evals={claimed_evals} / {nd} trading dates => implied universe {claimed_evals/nd:.2f} symbols; market universe available = {ns}")
    print(f"          metrics_json keys = {sorted(m.keys())}")
    print(f"          total_trades={m.get('total_trades')} entry_fill={m.get('entry_fill_count')} evaluated_bars={m.get('evaluated_bars')}")
con.close()
