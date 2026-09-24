import os, json, sqlite3
os.environ["ENABLE_LIVE_TRADING"] = "false"
os.environ["DATABASE_PATH"] = r"D:\codex-A股交易\trading_local.sqlite3"
from app.backtest.engine import BacktestEngine

con = sqlite3.connect(r"file:D:\codex-A股交易\trading_local.sqlite3?mode=ro", uri=True)
allsyms = [r[0] for r in con.execute(
    "select symbol from daily_bar_cache where quality_status='ready' "
    "group by symbol having count(*) > 450 order by symbol")]
step = max(1, len(allsyms) // 250)
syms = allsyms[::step][:250]
print(f"universe={len(allsyms)} sampled={len(syms)} "
      f"SH={sum(s.startswith('SH') for s in syms)} SZ={sum(s.startswith('SZ') for s in syms)}")

r = BacktestEngine().run("2025-09-01", "2026-07-17", syms, 100000.0, 5, 0.2, persist=False, allow_projected_fundamentals=True)
m = r["metrics"]
print("status:", r["status"], "| trades:", r["trades"], "| days:", r["days"], "| PIT:", m["fundamental_point_in_time"]); print("warnings:", [w[:70] for w in r["execution_warnings"] if "fundamental" in w or "no_entry" in w])
print("evaluated_bars:", m["signal_evaluated_bars"], "| input_coverage:", m["signal_input_coverage"])
print("missing_inputs:", m["signal_missing_inputs"])
print("\n--- per-rule outcomes ---")
for rid, o in m["signal_rule_outcomes"].items():
    tot = sum(o.values())
    print(f"{rid:34s} " + "  ".join(f"{k}={v}({v/tot:.1%})" for k, v in sorted(o.items())))
print("\n--- top rejection reasons ---")
for rid, rs in m["signal_top_rejections"].items():
    print(f"{rid}:")
    for reason, n in rs.items():
        print(f"    {n:6d}  {reason}")
print("\n--- entry funnel ---")
for k in ("entry_signal_count","entry_attempt_count","entry_fill_count","rejected_execution_count","partial_fill_count","trade_count"):
    print(f"{k:26s}: {m.get(k)}")
print("\n--- execution rejections ---")
for w in r["execution_warnings"]:
    if "blocked" in w or "reject" in w: print("  ", w[:160])
print("\n--- liquidity basis of fills ---", m.get("liquidity_basis_counts"))
print("total_return:", m["total_return"], "| closed:", r["closed_trades"], "| win_rate:", m["win_rate"], "| expectancy:", m["expectancy"])
