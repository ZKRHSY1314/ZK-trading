import sqlite3, pandas as pd, numpy as np
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
OP = r"D:/codex-A股交易/trading_local.sqlite3"
op = sqlite3.connect(f"file:{OP}?mode=ro", uri=True)

print("=== 1. implied universe size of each stored run ===")
print("SQL: SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE quality_status='ready' AND trade_date BETWEEN ? AND ?")
aud_ev = {1:1760, 13:4810, 19:3220}
for rid,(a,b) in {1:("2025-10-12","2026-06-09"),13:("2025-06-17","2026-06-12"),19:("2025-10-15","2026-06-12")}.items():
    d = op.execute("SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE quality_status='ready' AND trade_date BETWEEN ? AND ?",(a,b)).fetchone()[0]
    stored = op.execute("SELECT json_extract(metrics_json,'$.rejected_by_risk_count') FROM historical_backtest_runs WHERE id=?", (rid,)).fetchone()[0]
    print(f"  run {rid}: {a}..{b} trading_days={d}  auditor_evals={aud_ev[rid]}  -> implied universe ~= {aud_ev[rid]/d:.1f} symbols"
          f"   | stored rejected_by_risk={stored}  auditor_replay_blocked={ {1:1626,13:4644,19:3082}[rid] }  delta={ {1:1626,13:4644,19:3082}[rid]-stored:+d}")

print("\n=== 2. point-in-time visibility of the single fundamentals snapshot ===")
print("SQL: SELECT DISTINCT as_of, available_at FROM symbol_fundamental_snapshot")
r = op.execute("SELECT DISTINCT as_of, available_at FROM symbol_fundamental_snapshot").fetchall()
print("  ", r)
as_of, avail = r[0]
av = datetime.fromisoformat(avail.replace("Z","+00:00")).astimezone(timezone.utc)
SH = ZoneInfo("Asia/Shanghai")
def visible(td):
    cutoff = datetime.combine(datetime.fromisoformat(td).date(), time(15,0), tzinfo=SH).astimezone(timezone.utc)
    return (as_of <= td) and (av <= cutoff)
for td in ("2026-06-09","2026-06-12","2026-06-29","2026-08-31","2026-09-01","2026-09-02","2026-09-04"):
    print(f"   trade_date {td}: strict point-in-time visible = {visible(td)}")
n = op.execute("SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE quality_status='ready' AND trade_date>='2026-09-01'").fetchone()[0]
print(f"  -> snapshot IS visible strictly point-in-time on {n} trading days in the research window (>=2026-09-01)")

print("\n=== 3. spot-check strong bars against raw daily_bar_cache rows ===")
s = pd.read_csv(r"D:/codex-A股交易/claude methods/_m1_evidence/benchmark_v4_strong_bars.csv")
print(f"  total STRONG same-bar rows (market-wide, projected fundamentals): {len(s)} over {s.symbol.nunique()} symbols")
print(s.sort_values("trade_date").head(12).to_string(index=False))
for _,row in s.sort_values("trade_date").head(3).iterrows():
    sym, td = row["symbol"], row["trade_date"]
    print(f"\n  SQL: SELECT trade_date,high,close,volume FROM daily_bar_cache WHERE symbol='{sym}' AND trade_date<='{td}' ORDER BY trade_date DESC LIMIT 7")
    raw = op.execute("SELECT trade_date,high,close,volume FROM daily_bar_cache WHERE symbol=? AND quality_status='ready' AND trade_date<=? ORDER BY trade_date DESC LIMIT 7",(sym,td)).fetchall()
    for x in raw: print("      ", x)
    pc = (raw[0][2]-raw[1][2])/raw[1][2]*100
    vm = np.mean([x[3] for x in raw[1:6]])
    hi = op.execute("SELECT MAX(high) FROM (SELECT high FROM daily_bar_cache WHERE symbol=? AND quality_status='ready' AND trade_date<=? ORDER BY trade_date DESC LIMIT 250)",(sym,td)).fetchone()[0]
    print(f"      hand-check: pct_change={pc:.2f}% (script {row["pct_change"]:.2f}) | vol_ratio={raw[0][3]/vm:.2f} (script {row["vol_ratio"]:.2f}) | high250={hi} (script {row["high250"]}) | close/high250={raw[0][2]/hi:.4f} (script {row["ratio_hi"]:.4f})")
