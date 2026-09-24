import sqlite3, json
OP = r"D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
c.row_factory = sqlite3.Row

print("### Q1 per-run: status, cash, dates, equity rows, DISTINCT equity values")
q1 = """
SELECT r.id, r.status, r.data_source, r.start_date, r.end_date,
       r.initial_cash, r.final_cash, r.benchmark_symbol,
       COUNT(e.id)                        AS eq_rows,
       COUNT(DISTINCT e.total_equity)     AS distinct_total_equity,
       COUNT(DISTINCT e.positions_value)  AS distinct_pos_val,
       COUNT(DISTINCT e.cash)             AS distinct_cash,
       MIN(e.total_equity) AS min_eq, MAX(e.total_equity) AS max_eq,
       MIN(e.trade_date) AS eq_first, MAX(e.trade_date) AS eq_last,
       LENGTH(r.benchmark_json) AS bj_len, LENGTH(r.execution_warnings_json) AS ew_len
FROM historical_backtest_runs r
LEFT JOIN historical_backtest_daily_equity e ON e.run_id = r.id
GROUP BY r.id ORDER BY r.id
"""
rows = c.execute(q1).fetchall()
hdr = ("id","status","src","start","end","init$","final$","bench","eqN","dEq","dPos","dCash","minEq","maxEq","eqFirst","eqLast","bjLen","ewLen")
print(" | ".join(f"{h:>9}" for h in hdr))
for r in rows:
    print(" | ".join(f"{str(v)[:9]:>9}" for v in tuple(r)))
print(f"\nTOTAL RUNS = {len(rows)}")

print("\n### Q2 orphan equity rows / trades pointing at nonexistent runs")
for t in ("historical_backtest_daily_equity","historical_backtest_trades","historical_backtest_closed_trades"):
    n = c.execute(f"SELECT COUNT(*) FROM {t} e WHERE NOT EXISTS (SELECT 1 FROM historical_backtest_runs r WHERE r.id=e.run_id)").fetchone()[0]
    tot = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  {t}: total={tot} orphan={n}")

print("\n### Q3 GLOBAL: is any equity row anywhere non-flat? (own formulation, per-run relative)")
q3 = """
SELECT COUNT(*) AS nonflat_rows,
       COUNT(DISTINCT run_id) AS nonflat_runs
FROM historical_backtest_daily_equity e
JOIN historical_backtest_runs r ON r.id = e.run_id
WHERE ABS(e.total_equity - COALESCE(r.initial_cash, 0)) > 1e-9
   OR ABS(e.positions_value) > 1e-9
   OR ABS(e.cash - COALESCE(r.initial_cash, 0)) > 1e-9
"""
print(dict(c.execute(q3).fetchone()))

print("\n### Q3b distinct value tuples across the WHOLE equity table")
for r in c.execute("SELECT cash, positions_value, total_equity, COUNT(*) n, COUNT(DISTINCT run_id) runs FROM historical_backtest_daily_equity GROUP BY 1,2,3 ORDER BY n DESC LIMIT 10"):
    print("  ", tuple(r))

print("\n### Q4 final_cash vs initial_cash on runs table")
for r in c.execute("SELECT initial_cash, final_cash, COUNT(*) n, GROUP_CONCAT(id) ids FROM historical_backtest_runs GROUP BY 1,2"):
    print("  ", tuple(r))

print("\n### Q5 status distribution")
for r in c.execute("SELECT status, COUNT(*) FROM historical_backtest_runs GROUP BY 1"):
    print("  ", tuple(r))

print("\n### Q6 metrics_json full key union + value spread")
import collections
keyvals = collections.defaultdict(set)
allkeys = collections.Counter()
for r in c.execute("SELECT id, metrics_json FROM historical_backtest_runs ORDER BY id"):
    m = json.loads(r["metrics_json"] or "{}")
    for k,v in m.items():
        allkeys[k]+=1
        keyvals[k].add(json.dumps(v, sort_keys=True, ensure_ascii=False)[:60])
for k,n in allkeys.most_common():
    vals = sorted(keyvals[k])
    print(f"  {k:34s} present_in={n:2d}/39  distinct_values={len(vals)}  ex={vals[:3]}")

print("\n### Q7 benchmark_json content (BENCHMARK DIMENSION)")
bcount = collections.Counter()
for r in c.execute("SELECT id, benchmark_symbol, benchmark_json FROM historical_backtest_runs ORDER BY id"):
    b = r["benchmark_json"]
    bcount[(r["benchmark_symbol"], b if len(b)<80 else b[:80]+"...")] += 1
for k,v in bcount.most_common():
    print("  n=%d  symbol=%r  json=%r" % (v, k[0], k[1]))

print("\n### Q8 execution_warnings_json content")
wc = collections.Counter()
for r in c.execute("SELECT id, execution_warnings_json FROM historical_backtest_runs ORDER BY id"):
    wc[r["execution_warnings_json"][:300]] += 1
for k,v in wc.most_common():
    print(f"  n={v}  {k!r}")
c.close()
