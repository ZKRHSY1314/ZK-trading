# -*- coding: utf-8 -*-
import sqlite3, sys, io, json
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
tl=sqlite3.connect("file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True)
def q(s,a=()): return tl.execute(s,a).fetchall()
print("Why did 37/39 fail? run date-range vs SH000300 bar availability")
print("-"*95)
for rid,sd,ed,bj in q("SELECT id,start_date,end_date,benchmark_json FROM historical_backtest_runs ORDER BY start_date"):
    st=json.loads(bj).get('status') if bj else None
    n=q("SELECT COUNT(*) FROM daily_bar_cache WHERE symbol='SH000300' AND trade_date>=? AND trade_date<=?",(sd,ed))[0][0]
    print(f"  run {rid:>4} {sd}..{ed} status={st:28s} CSI300 bars in range={n}")
print()
print("SH000300 exact bar span & gap structure:")
print(" ", q("SELECT MIN(trade_date),MAX(trade_date),COUNT(*) FROM daily_bar_cache WHERE symbol='SH000300'")[0])
print("  bars in 2025-06..2026-06 (the backtest era):",
      q("SELECT COUNT(*) FROM daily_bar_cache WHERE symbol='SH000300' AND trade_date BETWEEN '2025-06-01' AND '2026-07-01'")[0][0])
print("  per-year bar counts:", q("SELECT substr(trade_date,1,4),COUNT(*) FROM daily_bar_cache WHERE symbol='SH000300' GROUP BY 1"))
