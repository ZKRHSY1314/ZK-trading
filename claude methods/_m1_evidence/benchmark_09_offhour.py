import sqlite3, sys, json
sys.stdout.reconfigure(encoding='utf-8')
OP = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
op=ro(OP)
print("schema:", op.execute("SELECT sql FROM sqlite_master WHERE name='offhour_research_runs'").fetchone()[0])
cols=[d[1] for d in op.execute("PRAGMA table_info(offhour_research_runs)")]
print("cols:", cols)
q="SELECT COUNT(*), MIN(created_at), MAX(created_at) FROM offhour_research_runs"
print("SQL:", q, "->", op.execute(q).fetchone())
print("\n### Q26 offhour runs referencing a persisted backtest run_id")
n=0
for row in op.execute("SELECT * FROM offhour_research_runs ORDER BY id"):
    d=dict(zip(cols,row))
    blob=json.dumps(d, ensure_ascii=False)
    if '"run_id"' in blob and 'backtest' in blob:
        try:
            payload=None
            for k,v in d.items():
                if isinstance(v,str) and v.startswith("{") and '"backtest"' in v:
                    payload=json.loads(v); break
            bt=(payload or {}).get("backtest") or {}
            if bt.get("run_id"):
                n+=1
                print("   offhour id",d.get("id"),"created",d.get("created_at"),"-> backtest run_id",bt.get("run_id"),
                      "symbols",bt.get("symbols"), bt.get("start_date"), bt.get("end_date"), "status",bt.get("status"))
        except Exception as e:
            print("   parse err", e)
print("   offhour rows linking a persisted backtest run_id:", n)
op.close()
