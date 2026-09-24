import sqlite3, json, collections
OP=r"D:/codex-A股交易/trading_local.sqlite3"
c=sqlite3.connect(f"file:{OP}?mode=ro", uri=True); c.row_factory=sqlite3.Row
q=lambda s,p=(): c.execute(s,p).fetchall()

print("### N. rejected_by_risk_count per run vs its own bar-day count")
tot=0
for r in q("""SELECT r.id, json_extract(r.metrics_json,'$.rejected_by_risk_count') rej,
                     COUNT(e.id) days
              FROM historical_backtest_runs r JOIN historical_backtest_daily_equity e ON e.run_id=r.id
              GROUP BY r.id ORDER BY r.id"""):
    tot+=r["rej"]
    if r["id"] in (1,8,13,19,38,39):
        print(f"  run {r['id']:>2}: rejected_by_risk={r['rej']:>5}  equity_days={r['days']:>3}  per_day={r['rej']/r['days']:.1f}")
print(f"  TOTAL rule-engine hard-blocks across all 39 runs = {tot}")
print()

print("### O. INDEPENDENT flatness proof that never touches daily_equity:")
print("     excess_return should equal -benchmark_return iff strategy_return==0")
for r in q("""SELECT id, json_extract(benchmark_json,'$.benchmark_return') br,
                     json_extract(benchmark_json,'$.excess_return') er,
                     json_extract(benchmark_json,'$.correlation_to_benchmark') corr
              FROM historical_backtest_runs
              WHERE json_extract(benchmark_json,'$.status')='ready' ORDER BY id"""):
    print(f"  run {r['id']}: benchmark_return={r['br']}  excess_return={r['er']}  sum={r['br']+r['er']:.10f}  corr={r['corr']}")
print()

print("### P. 'no backtest evidence exists in this system' -- test against learning_backtests (76 rows)")
print("  distinct strategies:", [tuple(x) for x in q("SELECT strategy_name, COUNT(*) FROM learning_backtests GROUP BY strategy_name")])
print("  sample_count/win_rate census:")
for r in q("""SELECT COUNT(*) n, SUM(sample_count=0) zero_sample, MIN(sample_count) mn, MAX(sample_count) mx,
                     COUNT(DISTINCT win_rate) dwr, COUNT(DISTINCT avg_return) dar, COUNT(DISTINCT max_drawdown) dmd
              FROM learning_backtests"""):
    print("   ", dict(r))
for r in q("SELECT id,strategy_name,sample_count,win_rate,avg_return,profit_loss_ratio,max_drawdown,pending_count,created_at FROM learning_backtests ORDER BY id DESC LIMIT 6"):
    print("   ", dict(r))
print()
print("### Q. other 'evidence' tables the claim's sweeping clause would have to cover")
for t in ("historical_backtest_trades","historical_backtest_closed_trades","simulation_fills","simulation_positions",
          "trade_records","trade_cases","strategy_performance_snapshots","main_force_phase_replays",
          "agent_paper_simulation_actions","forecast_outcomes"):
    try: print(f"   {t:38s} {q(f'SELECT COUNT(*) FROM {t}')[0][0]}")
    except Exception as e: print(f"   {t:38s} ERR {e}")
