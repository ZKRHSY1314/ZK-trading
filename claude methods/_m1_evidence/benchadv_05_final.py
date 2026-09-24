# -*- coding: utf-8 -*-
import sqlite3, sys, io, json, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
TL=r"D:/codex-A股交易/trading_local.sqlite3"; MH=r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
def q(c,s,a=()): return c.execute(s,a).fetchall()
tl=ro(TL); mh=ro(MH)

print("A. Did the 39 backtest runs actually PRODUCE a benchmark, or fall back to insufficient_benchmark_data?")
print("-"*95)
cnt=collections.Counter(); keys=set()
for (bj,) in q(tl,"SELECT benchmark_json FROM historical_backtest_runs WHERE benchmark_json IS NOT NULL"):
    try: d=json.loads(bj)
    except Exception: cnt['UNPARSEABLE']+=1; continue
    cnt[str(d.get('status'))]+=1; keys|=set(d.keys())
print("  benchmark_json status counts:", dict(cnt))
print("  keys present:", sorted(keys))
print("  sample:", q(tl,"SELECT benchmark_json FROM historical_backtest_runs WHERE benchmark_json IS NOT NULL LIMIT 1")[0][0][:400])

print()
print("B. REPRODUCE the auditor's own stated evidence sentence -- does their SQL give their claimed answer?")
print("-"*95)
r1=q(mh,"SELECT symbol, COUNT(*) FROM daily_bars WHERE symbol LIKE 'SZ399%' OR symbol LIKE 'SH000%' OR symbol LIKE 'BJ899%' GROUP BY symbol")
print("  their exact SQL (LIKE 'SZ399%'/'SH000%'/'BJ899%') returns:", r1, "<-- EMPTY, so it cannot 'return SH600399'")
r2=q(mh,"SELECT symbol FROM daily_bars WHERE symbol LIKE '%399%' GROUP BY symbol LIMIT 6")
print("  a LIKE '%399%' search returns:", [x[0] for x in r2], "<-- this is what they actually saw")

print()
print("C. FINAL HEADLINE NUMBERS (mine)")
print("-"*95)
print("  MH.instruments total:", q(mh,"SELECT COUNT(*) FROM instruments")[0][0],
      "| asset_type<>'stock':", q(mh,"SELECT COUNT(*) FROM instruments WHERE asset_type IS NULL OR asset_type<>'stock'")[0][0])
print("  MH.daily_bars distinct symbols:", q(mh,"SELECT COUNT(DISTINCT symbol) FROM daily_bars")[0][0])
idx=q(mh,"""SELECT COUNT(DISTINCT symbol) FROM daily_bars
            WHERE (substr(symbol,1,2)='SH' AND substr(symbol,3,1) IN ('0','9'))
               OR (substr(symbol,1,2)='SZ' AND substr(symbol,3,2)='39')
               OR (substr(symbol,1,2)='BJ' AND substr(symbol,3,2) IN ('89','95'))""")[0][0]
print("  MH.daily_bars symbols in ANY A-share index code range:", idx)
print("  TL.daily_bar_cache TRUE index symbols (source=akshare.stock_zh_index_daily):",
      q(tl,"SELECT symbol, COUNT(*) FROM daily_bar_cache WHERE source='akshare.stock_zh_index_daily' GROUP BY symbol"))
tl.close(); mh.close()
