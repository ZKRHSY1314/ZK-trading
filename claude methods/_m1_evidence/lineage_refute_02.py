import sqlite3
OP = r"D:/codex-A股交易/trading_local.sqlite3"
RH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True); c.row_factory = sqlite3.Row; return c
op, rh = ro(OP), ro(RH)
def show(t, conn, sql, params=()):
    print("\n### "+t); print("SQL: "+" ".join(sql.split()))
    try: rows = conn.execute(sql, params).fetchall()
    except Exception as e: print("  ERROR:", e); return []
    for r in rows[:50]: print("   ", dict(r))
    if len(rows)>50: print(f"    ...{len(rows)} rows")
    return rows

# D. Runs denominator -- do NOT trust "39". Count independently, look for other data_source values.
show("D1 historical_backtest_runs: every distinct data_source, no grouping by status", op,
 "SELECT COALESCE(data_source,'<NULL>') AS ds, COUNT(*) n, MIN(id) min_id, MAX(id) max_id, MIN(completed_at) first_at, MAX(completed_at) last_at FROM historical_backtest_runs GROUP BY 1")
show("D2 schema default for data_source (is it forced by DDL, not by engine?)", op,
 "SELECT sql FROM sqlite_master WHERE name='historical_backtest_runs'")
show("D3 do any runs actually reference a benchmark index, and did benchmark resolve?", op,
 "SELECT benchmark_symbol, COUNT(*) n, SUM(CASE WHEN benchmark_json LIKE '%insufficient_benchmark_data%' THEN 1 ELSE 0 END) AS insufficient FROM historical_backtest_runs GROUP BY 1 ORDER BY n DESC")
show("D4 runs that produced ANY P&L movement (final_cash != initial_cash)", op,
 "SELECT COUNT(*) AS runs, SUM(CASE WHEN final_cash <> initial_cash THEN 1 ELSE 0 END) AS runs_with_pnl_change, SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed FROM historical_backtest_runs")

# E. Other simulated-P&L stores: does ANY of them cite market_history?
show("E1 every table whose name hints at simulation/backtest/replay/paper", op,
 "SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%backtest%' OR name LIKE '%simul%' OR name LIKE '%replay%' OR name LIKE '%paper%' OR name LIKE '%offhour%') ORDER BY name")
# F. Any column literally named data_source anywhere in trading_local, with its values
rows = op.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("\n### F1 scan every table for a data_source/source column and its distinct values")
print("SQL: PRAGMA table_info(<t>) then SELECT <col>, COUNT(*) FROM <t> GROUP BY 1")
hits=[]
for r in rows:
    t=r["name"]
    try: cols=[c[1] for c in op.execute(f"PRAGMA table_info('{t}')").fetchall()]
    except Exception: continue
    for c in cols:
        if c in ("data_source","source","price_source","bar_source","market_data_source"):
            try:
                vals=op.execute(f"SELECT \"{c}\" v, COUNT(*) n FROM \"{t}\" GROUP BY 1 ORDER BY n DESC LIMIT 6").fetchall()
            except Exception: continue
            if vals: hits.append((t,c,[(v["v"],v["n"]) for v in vals]))
for t,c,v in hits:
    flag = "  <-- MENTIONS market_history" if any("market_history" in str(x[0]) or "daily_bars" in str(x[0]) for x in v) else ""
    print(f"    {t}.{c}: {v}{flag}")
op.close(); rh.close()
