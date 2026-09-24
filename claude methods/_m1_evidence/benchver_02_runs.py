import sqlite3, json
OP = r"D:/codex-A股交易/trading_local.sqlite3"
con = sqlite3.connect(f"file:{OP}?mode=ro", uri=True); con.row_factory = sqlite3.Row
rows = con.execute("""
SELECT id,start_date,end_date,status,data_source,initial_cash,final_cash,created_at,
       metrics_json,config_json,execution_warnings_json
FROM historical_backtest_runs ORDER BY id
""").fetchall()
print("total runs:", len(rows))
for r in rows:
    m = json.loads(r["metrics_json"] or "{}")
    cfg = json.loads(r["config_json"] or "{}")
    syms = cfg.get("symbols")
    nsym = len(syms) if isinstance(syms,list) else None
    print(f"id={r['id']:>3} {r['start_date']}..{r['end_date']} st={r['status']:<9} src={r['data_source']:<12} "
          f"created={r['created_at']} nsym={nsym} "
          f"eval={m.get('evaluated_bars')} rej_risk={m.get('rejected_by_risk_count')} "
          f"skip={m.get('skipped_count')} sig={m.get('entry_signal_count')} "
          f"att={m.get('entry_attempt_count')} fill={m.get('entry_fill_count')} "
          f"unknown={m.get('unknown_bars')} trades={m.get('total_trades')}")
print()
print("=== config_json top-level keys sample (run 1) ===")
r1 = [r for r in rows if r["id"]==1][0]
print(json.dumps(json.loads(r1["config_json"]), ensure_ascii=False)[:3000])
con.close()
