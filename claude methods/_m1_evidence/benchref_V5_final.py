import sqlite3
TL="D:/codex-A股交易/trading_local.sqlite3"; MH="D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
tl,mh=ro(TL),ro(MH)

print("### K. Every symbol shape in daily_bar_cache that is NOT a plain 8-char SH/SZ/BJ stock")
q="""SELECT symbol, COUNT(*) n, MIN(trade_date), MAX(trade_date) FROM daily_bar_cache
WHERE NOT (length(symbol)=8 AND ((substr(symbol,1,2)='SH' AND substr(symbol,3,1)='6')
   OR (substr(symbol,1,2)='SZ' AND substr(symbol,3,1) IN ('0','3')) OR substr(symbol,1,2)='BJ'))
GROUP BY symbol ORDER BY n DESC LIMIT 40"""
for r in tl.execute(q).fetchall(): print("   ",r)

print()
print("### L. The 'ERROR' trade_date row (data corruption spotted en route)")
for r in tl.execute("SELECT symbol,trade_date,open,high,low,close,volume,source,quality_status FROM daily_bar_cache WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'").fetchall():
    print("   ",r)

print()
print("### M. Same scan on market_history.daily_bars")
q2="""SELECT symbol, COUNT(*) n FROM daily_bars
WHERE NOT (length(symbol)=8 AND ((substr(symbol,1,2)='SH' AND substr(symbol,3,1)='6')
   OR (substr(symbol,1,2)='SZ' AND substr(symbol,3,1) IN ('0','3')) OR substr(symbol,1,2)='BJ'))
GROUP BY symbol ORDER BY n DESC LIMIT 20"""
print("   non-stock symbols in research store:", mh.execute(q2).fetchall())

print()
print("### N. Does anything reference a benchmark in stored payloads? (backtests/learning)")
for tbl,col in (("historical_backtest_runs","*"),("learning_backtests","*")):
    cols=[r[1] for r in tl.execute(f"PRAGMA table_info({tbl})")]
    print(f"   {tbl} cols:", cols)
import re
hits={}
for tbl in ("historical_backtest_runs","learning_backtests","learning_reports"):
    cols=[r[1] for r in tl.execute(f"PRAGMA table_info({tbl})")]
    for c in cols:
        try:
            n=tl.execute(f"SELECT COUNT(*) FROM {tbl} WHERE CAST(\"{c}\" AS TEXT) LIKE '%000300%' OR CAST(\"{c}\" AS TEXT) LIKE '%benchmark%' OR CAST(\"{c}\" AS TEXT) LIKE '%hs300%'").fetchone()[0]
            if n: hits[f"{tbl}.{c}"]=n
        except Exception: pass
print("   columns mentioning benchmark/000300/hs300:", hits or "NONE")

print()
print("### O. FINAL COVERAGE TABLE — benchmark vs stock availability, by regime")
rows=[("full-breadth era 2024-06-24..2026-09-02", "'2024-06-24'","'2026-09-02'"),
      ("breadth>=100 era 2024-06-07..2026-09-04","'2024-06-07'","'2026-09-04'"),
      ("full window 2023-09-04..2026-09-04","'2023-09-04'","'2026-09-04'")]
for lbl,a,b in rows:
    cal=[r[0] for r in tl.execute(f"""SELECT trade_date FROM daily_bar_cache
      WHERE length(symbol)=8 AND ((substr(symbol,1,2)='SH' AND substr(symbol,3,1)='6')
      OR (substr(symbol,1,2)='SZ' AND substr(symbol,3,1) IN ('0','3')) OR substr(symbol,1,2)='BJ')
      AND trade_date BETWEEN {a} AND {b}
      GROUP BY trade_date HAVING COUNT(DISTINCT symbol)>=100""")]
    bench={r[0] for r in tl.execute(f"SELECT trade_date FROM daily_bar_cache WHERE symbol='SH000300' AND trade_date BETWEEN {a} AND {b}")}
    miss=sorted(set(cal)-bench)
    print(f"   {lbl:42} sessions={len(cal):4} bench={len(bench):4} missing={len(miss):3} pct={100*len(bench)/len(cal):6.2f}%  missing_dates={miss[:12]}")
tl.close(); mh.close()
