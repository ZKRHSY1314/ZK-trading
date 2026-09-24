# -*- coding: utf-8 -*-
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
TL = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
t = ro(TL)
W0, W1 = "2023-09-04", "2026-09-04"

print("### M. Index bar coverage vs the REAL trading calendar in the research window")
q = f"SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN '{W0}' AND '{W1}' AND symbol LIKE 'SH6%'"
cal = t.execute(q).fetchone()[0]
print("  SQL:", q, "-> trading days on SH-main stocks =", cal)
for sym in ("SH000001","SH000300"):
    q2 = (f"SELECT COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date) FROM daily_bar_cache "
          f"WHERE symbol='{sym}' AND trade_date BETWEEN '{W0}' AND '{W1}'")
    n,mn,mx = t.execute(q2).fetchone()
    print(f"      {sym}: days={n}  span={mn}..{mx}  window_coverage={n/cal:.1%} of {cal} trading days")
    # gap at the front
    q3 = (f"SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE symbol LIKE 'SH6%' "
          f"AND trade_date BETWEEN '{W0}' AND (SELECT MIN(trade_date) FROM daily_bar_cache WHERE symbol='{sym}')")
    print(f"        uncovered leading trading days {W0}..first index bar:", t.execute(q3).fetchone()[0])

print("\n### N. Do the index rows carry usable OHLC, or are they degenerate?")
q = ("SELECT symbol, COUNT(*), SUM(close IS NULL), SUM(open IS NULL), SUM(volume IS NULL), SUM(amount IS NULL),"
     " MIN(close), MAX(close), adjustment_mode, source, quality_status "
     "FROM daily_bar_cache WHERE symbol IN ('SH000001','SH000300') GROUP BY symbol, adjustment_mode, source, quality_status")
print("  SQL:", q)
for r in t.execute(q).fetchall(): print("      ", r)

print("\n### O. historical_backtest_runs.benchmark_symbol — is a benchmark actually wired in?")
q = "SELECT benchmark_symbol, COUNT(*), SUM(benchmark_json IS NOT NULL AND benchmark_json NOT IN ('','{}','null')) FROM historical_backtest_runs GROUP BY benchmark_symbol"
print("  SQL:", q)
for r in t.execute(q).fetchall(): print("      ", r)

print("\n### P. forecast_outcomes.benchmark_return — populated or dead column?")
q = ("SELECT COUNT(*) total, COUNT(benchmark_return) nonnull_bench, COUNT(benchmark_neutral_return) nonnull_neutral, "
     "SUM(benchmark_return=0) zero_bench FROM forecast_outcomes")
print("  SQL:", q, "->", t.execute(q).fetchone())
q = ("SELECT COUNT(*) , COUNT(benchmark_return) FROM forecast_outcomes o JOIN forecast_decisions d ON d.id=o.decision_id "
     "WHERE substr(d.created_at,1,10) BETWEEN '2023-09-04' AND '2026-09-04'")
try:
    print("  SQL(window join):", q, "->", t.execute(q).fetchone())
except Exception as e:
    print("      join failed:", e)
t.close()
