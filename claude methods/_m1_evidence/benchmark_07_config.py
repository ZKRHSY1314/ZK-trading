import sqlite3, sys, json
sys.stdout.reconfigure(encoding='utf-8')
OP = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
op=ro(OP)
print("### Q20 config_json top-level keys per run")
seen={}
for rid, cj in op.execute("SELECT id, config_json FROM historical_backtest_runs ORDER BY id"):
    d=json.loads(cj); k=tuple(sorted(d.keys()))
    seen.setdefault(k,[]).append(rid)
for k,v in seen.items(): print("   keys:", k, " runs:", v)
print("\n   full rule ids of run 39:")
d=json.loads(op.execute("SELECT config_json FROM historical_backtest_runs WHERE id=39").fetchone()[0])
for r in d.get("rules",[]): print("      ", r.get("id"), "| group=",r.get("group"), "| enabled=",r.get("enabled"), "| hard_block=",r.get("hard_block"), "| weight=",r.get("weight"), "| params=", r.get("params"))
print("   other config keys:", {k:v for k,v in d.items() if k!="rules"})
print("\n### Q21 does config_json ever record the symbol universe / initial cash / dates?")
for k in ("symbols","universe","max_positions","per_symbol_cap","initial_cash"):
    n=op.execute(f"SELECT COUNT(*) FROM historical_backtest_runs WHERE config_json LIKE '%\"{k}\"%'").fetchone()[0]
    print(f"   runs whose config_json mentions \"{k}\": {n}")
print("\n### Q22 distinct config across runs (hash groups)")
for cj,cnt,ids in op.execute("SELECT config_json, COUNT(*), group_concat(id) FROM historical_backtest_runs GROUP BY config_json ORDER BY 2 DESC"):
    dd=json.loads(cj)
    print(f"   cnt={cnt} runs={ids} n_rules={len(dd.get('rules',[]))} tiers={dd.get('candidate_tiers')} exit_rules={dd.get('exit_rules')}")
op.close()
