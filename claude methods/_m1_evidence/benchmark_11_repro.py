import sqlite3, sys, json
sys.stdout.reconfigure(encoding='utf-8')
OP = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
op=ro(OP)

print("### Q27 SH000300 created_at batches")
q="SELECT substr(created_at,1,10) d, COUNT(*), MIN(trade_date), MAX(trade_date) FROM daily_bar_cache WHERE symbol='SH000300' GROUP BY d ORDER BY d"
print("SQL:", q)
for r in op.execute(q): print("   ", r)

def bench(sd, ed):
    rows=op.execute("SELECT trade_date, close FROM daily_bar_cache WHERE symbol IN ('SH000300') AND quality_status='ready' AND trade_date>=? AND trade_date<=? ORDER BY trade_date ASC",(sd,ed)).fetchall()
    closes=[float(c) for _,c in rows if c is not None]
    if len(closes)<2: return None
    ret=closes[-1]/closes[0]-1
    peak=closes[0]; mdd=0.0
    for c in closes:
        peak=max(peak,c); mdd=max(mdd,(peak-c)/peak if peak else 0)
    return len(rows), rows[0][0], rows[-1][0], round(ret,6), round(mdd,6)

print("\n### Q28 replay engine._benchmark math on TODAY's rows, per distinct run window")
q="SELECT DISTINCT start_date, end_date FROM historical_backtest_runs ORDER BY start_date"
print("SQL:", q)
for sd, ed in op.execute(q):
    ids=[r[0] for r in op.execute("SELECT id FROM historical_backtest_runs WHERE start_date=? AND end_date=?", (sd,ed))]
    stored=op.execute("SELECT benchmark_json FROM historical_backtest_runs WHERE start_date=? AND end_date=? LIMIT 1",(sd,ed)).fetchone()[0]
    print(f"   window {sd}..{ed}  runs={ids}")
    print(f"      recomputed_now(n_rows,first,last,return,maxdd) = {bench(sd,ed)}")
    print(f"      stored_at_run_time = {stored}")

print("\n### Q29 union of symbol universes for the 39 persisted runs (from offhour_research_runs)")
uni={}
for rid, bj in op.execute("SELECT id, backtest_json FROM offhour_research_runs"):
    try: d=json.loads(bj)
    except Exception: continue
    if d.get("run_id"):
        uni[d["run_id"]] = d.get("symbols") or []
allsyms=set()
for k in sorted(uni):
    allsyms |= set(uni[k])
print("   persisted run_ids recovered:", sorted(uni))
print("   run_ids in historical_backtest_runs but NOT recoverable:", sorted(set(range(1,40))-set(uni)))
print("   union symbol count:", len(allsyms))
print("   union symbols:", sorted(allsyms))
print("   symbols per run:", {k: len(v) for k,v in sorted(uni.items())})
print("\n   sanity: rejected_by_risk / (symbols x trading days)")
for rid in sorted(uni):
    m=json.loads(op.execute("SELECT metrics_json FROM historical_backtest_runs WHERE id=?", (rid,)).fetchone()[0])
    n=op.execute("SELECT COUNT(*) FROM historical_backtest_daily_equity WHERE run_id=?", (rid,)).fetchone()[0]
    ns=len(uni[rid])
    print(f"      run {rid}: symbols={ns} equity_days={n} rejected_by_risk={m['rejected_by_risk_count']} ratio={m['rejected_by_risk_count']/(ns*n):.3f}")
op.close()
