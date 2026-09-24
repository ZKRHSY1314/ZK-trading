import sqlite3
OP=r"D:/codex-A股交易/trading_local.sqlite3"; RH=r"D:/codex-A股交易/market_history.sqlite3"
def ro(p):
    c=sqlite3.connect(f"file:{p}?mode=ro",uri=True); c.row_factory=sqlite3.Row; return c
op,rh=ro(OP),ro(RH)
def show(t,conn,sql,params=()):
    print("\n### "+t); print("SQL: "+" ".join(sql.split()))
    try: rows=conn.execute(sql,params).fetchall()
    except Exception as e: print("  ERROR:",e); return []
    for r in rows[:30]: print("   ",dict(r))
    return rows

# G. Benchmark: engine reads SH000300 from daily_bar_cache. Why did 37/39 fail?
show("G1 run windows actually requested", op,
 "SELECT start_date, end_date, COUNT(*) n, SUM(CASE WHEN benchmark_json LIKE '%insufficient%' THEN 1 ELSE 0 END) bad FROM historical_backtest_runs GROUP BY 1,2 ORDER BY n DESC")
show("G2 SH000300 in daily_bar_cache (the store the engine reads)", op,
 "SELECT COUNT(*) n, MIN(trade_date) mn, MAX(trade_date) mx, COUNT(DISTINCT quality_status) qs FROM daily_bar_cache WHERE symbol IN ('SH000300','sh000300','000300')")
show("G3 SH000300 in market_history.daily_bars (the store the engine CANNOT read)", rh,
 "SELECT adjustment_mode, COUNT(*) n, MIN(trade_date) mn, MAX(trade_date) mx FROM daily_bars WHERE symbol IN ('SH000300','sh000300','000300') GROUP BY 1")
show("G4 what index symbols exist in the cache at all", op,
 "SELECT symbol, COUNT(*) n, MIN(trade_date) mn, MAX(trade_date) mx FROM daily_bar_cache WHERE symbol LIKE 'SH000%' OR symbol LIKE 'SZ399%' GROUP BY 1 ORDER BY n DESC LIMIT 15")

# H. COUNTERFACTUAL: is market_history a strict SUBSET of daily_bar_cache?
#    If yes, "no path to market_history" costs the backtest nothing in coverage.
print("\n### H1 symbol-level set difference between the two stores")
print("SQL: SELECT DISTINCT symbol FROM daily_bar_cache WHERE quality_status='ready'  /  SELECT DISTINCT symbol FROM daily_bars")
cache_syms={r[0] for r in op.execute("SELECT DISTINCT symbol FROM daily_bar_cache WHERE quality_status='ready'")}
hist_syms={r[0] for r in rh.execute("SELECT DISTINCT symbol FROM daily_bars")}
print(f"    cache_ready_symbols={len(cache_syms)}  history_symbols={len(hist_syms)}")
print(f"    in history but NOT in cache = {len(hist_syms-cache_syms)}  -> {sorted(hist_syms-cache_syms)[:10]}")
print(f"    in cache but NOT in history = {len(cache_syms-hist_syms)}  -> {sorted(cache_syms-hist_syms)[:10]}")

print("\n### H2 (symbol,trade_date) pair-level: does history hold ANY bar the cache lacks?")
print("SQL: SELECT symbol||'|'||trade_date FROM daily_bar_cache WHERE quality_status='ready'  vs  SELECT DISTINCT symbol||'|'||trade_date FROM daily_bars")
cache_pairs={r[0] for r in op.execute("SELECT symbol||'|'||trade_date FROM daily_bar_cache WHERE quality_status='ready'")}
hist_pairs={r[0] for r in rh.execute("SELECT DISTINCT symbol||'|'||trade_date FROM daily_bars")}
only_hist=hist_pairs-cache_pairs
print(f"    cache_ready_pairs={len(cache_pairs)}  history_distinct_pairs={len(hist_pairs)}")
print(f"    bars ONLY in market_history (unreachable by the engine) = {len(only_hist)}")
print(f"    sample: {sorted(only_hist)[:10]}")
print(f"    bars only in cache (never promoted to history) = {len(cache_pairs-hist_pairs)}")
op.close(); rh.close()
