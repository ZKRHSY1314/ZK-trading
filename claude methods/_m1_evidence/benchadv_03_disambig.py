# -*- coding: utf-8 -*-
import sqlite3, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
def q(c,s,a=()): return c.execute(s,a).fetchall()
mh=ro(MH); tl=ro(TL)

print("="*100)
print("A. TRAP CHECK: are SZ000905 / SZ000852 / SZ000016 ... indices, or Shenzhen STOCKS that merely")
print("   share a numeric code with a Shanghai/CSI index? (do NOT count indices as stocks -- or stocks as indices)")
print("="*100)
cols = [r[1] for r in q(mh,"PRAGMA table_info(instruments)")]
print("  instruments columns:", cols)
sel = ",".join(cols)
for s in ("SZ000001","SZ000905","SZ000852","SZ000016","SZ000688","SZ000010","SZ000009","SZ000903"):
    r = q(mh, f"SELECT {sel} FROM instruments WHERE symbol=?", (s,))
    print(f"  {s}: {r}")

print()
print("B. Does market_history contain ANY SH000*/SH999*/SZ399*/BJ899*/BJ950* symbol at all?")
print("   SQL: SELECT COUNT(*) FROM daily_bars WHERE substr(symbol,1,2)='SH' AND substr(symbol,3,1)='0' ...")
print("-"*100)
for lbl,cond in (("SH0**", "symbol LIKE 'SH0%'"), ("SH9**","symbol LIKE 'SH9%'"),
                 ("SZ39*","symbol LIKE 'SZ39%'"), ("BJ89*","symbol LIKE 'BJ89%'"),
                 ("BJ95*","symbol LIKE 'BJ95%'")):
    a=q(mh,f"SELECT COUNT(DISTINCT symbol),COUNT(*) FROM daily_bars WHERE {cond}")[0]
    b=q(mh,f"SELECT COUNT(*) FROM instruments WHERE {cond}")[0][0]
    print(f"  {lbl}: MH.daily_bars syms={a[0]} rows={a[1]} | MH.instruments={b}")

print()
print("="*100)
print("C. THE OTHER DATABASE: full index-symbol census of trading_local.daily_bar_cache")
print("   (this is the store the backtest engine + simulation actually read from)")
print("="*100)
rows = q(tl, """
SELECT symbol, COUNT(*) n, MIN(trade_date), MAX(trade_date),
       SUM(CASE WHEN volume IS NULL THEN 1 ELSE 0 END) nullvol,
       SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) nullamt,
       COUNT(DISTINCT source), MIN(source), MAX(source)
FROM daily_bar_cache
WHERE symbol LIKE 'SH000%' OR symbol LIKE 'SH999%' OR symbol LIKE 'SZ399%'
   OR symbol LIKE 'BJ899%' OR symbol LIKE 'BJ950%' OR length(symbol)<8
GROUP BY symbol ORDER BY n DESC
""")
print(f"  {'symbol':12s} {'rows':>6s}  {'first':10s} {'last':10s} nullvol nullamt  sources")
for r in rows:
    print(f"  {r[0]:12s} {r[1]:6d}  {r[2]} {r[3]}  {r[4]:6d} {r[5]:6d}  {r[6]} [{r[7]}..{r[8]}]")
print(f"  -> {len(rows)} index-shaped symbols in trading_local.daily_bar_cache")

print()
print("D. Coverage of those inside the RESEARCH WINDOW 2023-09-04..2026-09-04 (string dates, ISO, safe to compare)")
print("-"*100)
for r in rows:
    s=r[0]
    w=q(tl,"SELECT COUNT(*),MIN(trade_date),MAX(trade_date) FROM daily_bar_cache WHERE symbol=? AND trade_date>='2023-09-04' AND trade_date<='2026-09-04'",(s,))[0]
    pre=q(tl,"SELECT COUNT(*) FROM daily_bar_cache WHERE symbol=? AND trade_date<'2023-09-04'",(s,))[0][0]
    print(f"  {s:12s} in-window={w[0]:5d} ({w[1]}..{w[2]})  before-window(warm-up)={pre}")

print()
print("E. Is a benchmark actually USED downstream? historical_backtest_runs.benchmark_symbol + forecast_outcomes")
print("-"*100)
print("  benchmark_symbol values:", q(tl,"SELECT benchmark_symbol, COUNT(*) FROM historical_backtest_runs GROUP BY 1 ORDER BY 2 DESC"))
print("  benchmark_json non-null:", q(tl,"SELECT SUM(CASE WHEN benchmark_json IS NULL OR benchmark_json='' THEN 0 ELSE 1 END), COUNT(*) FROM historical_backtest_runs")[0])
print("  forecast_outcomes benchmark_return non-null / total:",
      q(tl,"SELECT SUM(CASE WHEN benchmark_return IS NULL THEN 0 ELSE 1 END), COUNT(*) FROM forecast_outcomes")[0])
print("  forecast_outcomes benchmark_neutral_return non-null / total:",
      q(tl,"SELECT SUM(CASE WHEN benchmark_neutral_return IS NULL THEN 0 ELSE 1 END), COUNT(*) FROM forecast_outcomes")[0])
mh.close(); tl.close()
