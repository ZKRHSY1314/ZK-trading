import sqlite3, sys, json
sys.stdout.reconfigure(encoding='utf-8')
OP = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
op=ro(OP)
q="SELECT id, created_at, mode, status, backtest_json FROM offhour_research_runs ORDER BY id"
print("SQL:", q)
hits=0
for rid, ca, mode, st, bj in op.execute(q):
    try: d=json.loads(bj)
    except Exception: d={}
    if d.get("run_id") is not None:
        hits+=1
        print(f"   offhour {rid} {ca} mode={mode} -> run_id={d.get('run_id')} symbols={d.get('symbols')} {d.get('start_date')}..{d.get('end_date')} status={d.get('status')}")
    elif rid<=6 or rid%20==0:
        print(f"   offhour {rid} {ca} mode={mode} backtest_json={bj[:300]}")
print("   rows with run_id:", hits)
op.close()
