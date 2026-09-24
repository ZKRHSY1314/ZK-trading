import sqlite3, json
OP = r"D:/codex-A股交易/trading_local.sqlite3"
op = sqlite3.connect(f"file:{OP}?mode=ro", uri=True); op.row_factory = sqlite3.Row
q = "SELECT id,start_date,end_date,config_json,metrics_json,execution_warnings_json FROM historical_backtest_runs WHERE id IN (1,13,19,39)"
print(q)
for r in op.execute(q).fetchall():
    cfg = json.loads(r["config_json"]); met = json.loads(r["metrics_json"])
    print("\n########## RUN", r["id"], r["start_date"], "->", r["end_date"])
    print("-- config top keys:", sorted(cfg.keys()))
    print("-- candidate_tiers:", cfg.get("candidate_tiers"))
    print("-- symbols in config:", ("symbols" in cfg) and len(cfg.get("symbols") or []))
    for k in ("symbols","universe","symbol_list"):
        if k in cfg:
            v = cfg[k]; print(f"-- {k}: n={len(v)} sample={v[:8]}")
    for rule in cfg.get("rules", []):
        print("   RULE", rule.get("id"), "enabled=",rule.get("enabled"), "group=",rule.get("group"),
              "weight=",rule.get("weight"), "hard_block=",rule.get("hard_block"), "params=",rule.get("params"))
    print("-- metrics keys:", sorted(met.keys()))
    print("-- metrics:", json.dumps({k:v for k,v in met.items() if not isinstance(v,(list,dict))}, ensure_ascii=False)[:1200])
    print("-- warnings:", r["execution_warnings_json"][:500])
