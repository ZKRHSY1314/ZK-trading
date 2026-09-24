# -*- coding: utf-8 -*-
import sqlite3,sys,io,json
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
tl=sqlite3.connect("file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True)
def q(s,a=()): return tl.execute(s,a).fetchall()
print("Was the CSI300 series ingested AFTER the failing runs executed? (data-arrival vs lookup-bug)")
print("-"*95)
print("  SH000300 rows created_at MIN/MAX:", q("SELECT MIN(created_at),MAX(created_at) FROM daily_bar_cache WHERE symbol='SH000300'")[0])
print("  SH000001 rows created_at MIN/MAX:", q("SELECT MIN(created_at),MAX(created_at) FROM daily_bar_cache WHERE symbol='SH000001'")[0])
print()
for st in ('insufficient_benchmark_data','ready'):
    rows=[r for r in q("SELECT id,created_at,completed_at,benchmark_json FROM historical_backtest_runs") if json.loads(r[3]).get('status')==st]
    cs=sorted(r[1] for r in rows if r[1])
    print(f"  runs with status={st}: n={len(rows)} created_at {cs[0]} .. {cs[-1]}")
print()
print("  ready runs' benchmark payloads:")
for rid,bj in q("SELECT id,benchmark_json FROM historical_backtest_runs"):
    d=json.loads(bj)
    if d.get('status')=='ready': print(f"    run {rid}: {json.dumps(d,ensure_ascii=False)}")
