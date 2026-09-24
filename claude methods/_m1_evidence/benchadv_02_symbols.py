# -*- coding: utf-8 -*-
import sqlite3, sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
def q(c,s,a=()): return c.execute(s,a).fetchall()

mh = ro(MH); tl = ro(TL)

print("="*100)
print("A. INDEPENDENT SYMBOL CENSUS of market_history.daily_bars -- by NUMERIC CODE, not by prefix")
print("   SQL: SELECT substr(symbol,1,2) mkt, substr(symbol,3) code, ... grouped on code's leading 3 digits")
print("="*100)
rows = q(mh, """
SELECT substr(symbol,1,2) AS mkt,
       substr(symbol,3,3) AS code3,
       COUNT(DISTINCT symbol) AS n_sym,
       COUNT(*) AS n_rows,
       MIN(trade_date), MAX(trade_date)
FROM daily_bars
GROUP BY mkt, code3
ORDER BY mkt, code3
""")
tot_sym=0; tot_rows=0
for mkt,c3,ns,nr,d0,d1 in rows:
    tot_sym+=ns; tot_rows+=nr
    print(f"  {mkt}{c3}*  distinct_symbols={ns:5d}  rows={nr:9d}  {d0}..{d1}")
print(f"  TOTAL distinct_symbols={tot_sym}  rows={tot_rows}")

print()
print("B. EXPLICIT hunt for the actual A-share benchmark codes, ANY market prefix, ANY separator,")
print("   in market_history.daily_bars AND market_history.instruments AND trading_local.daily_bar_cache")
print("-"*100)
BENCH = {
 "000001":"SSE Composite 上证指数", "000300":"CSI300 沪深300", "000905":"CSI500 中证500",
 "000852":"CSI1000 中证1000", "000016":"SSE50 上证50", "000688":"STAR50 科创50",
 "399001":"SZ Component 深证成指", "399006":"ChiNext 创业板指", "399005":"中小板指",
 "399300":"沪深300(深)", "399905":"中证500(深)", "899050":"BSE50 北证50",
 "000010":"上证180", "000009":"上证380", "000903":"中证100",
}
for code, nm in BENCH.items():
    a = q(mh, "SELECT COUNT(DISTINCT symbol), COUNT(*) FROM daily_bars WHERE symbol LIKE ?", (f"%{code}%",))[0]
    syms_a = [r[0] for r in q(mh, "SELECT DISTINCT symbol FROM daily_bars WHERE symbol LIKE ? LIMIT 8", (f"%{code}%",))]
    b = q(mh, "SELECT COUNT(*) FROM instruments WHERE symbol LIKE ?", (f"%{code}%",))[0][0]
    c = q(tl, "SELECT COUNT(DISTINCT symbol), COUNT(*) FROM daily_bar_cache WHERE symbol LIKE ?", (f"%{code}%",))[0]
    syms_c = [r[0] for r in q(tl, "SELECT DISTINCT symbol FROM daily_bar_cache WHERE symbol LIKE ? LIMIT 8", (f"%{code}%",))]
    print(f"  {code} {nm}")
    print(f"      MH.daily_bars   syms={a[0]} rows={a[1]}  {syms_a}")
    print(f"      MH.instruments  rows={b}")
    print(f"      TL.daily_bar_cache syms={c[0]} rows={c[1]}  {syms_c}")

print()
print("C. market_history.instruments -- FULL distinct asset_type / status / board / exchange")
print("-"*100)
for col in ("asset_type","exchange","board","status"):
    try:
        rr = q(mh, f"SELECT {col}, COUNT(*) FROM instruments GROUP BY {col} ORDER BY 2 DESC")
        print(f"  {col}: {rr}")
    except Exception as e:
        print(f"  {col}: ERR {e}")

print()
print("D. Is ANY market_history symbol not a plain stock? Symbols whose 3rd char is not a digit,")
print("   or whose length != 8, or containing '.'/'^'/'IDX'")
print("-"*100)
print("  len distribution:", q(mh,"SELECT length(symbol), COUNT(DISTINCT symbol) FROM daily_bars GROUP BY 1"))
print("  non-8-len instruments:", q(mh,"SELECT COUNT(*) FROM instruments WHERE length(symbol)<>8"))
print("  symbols with dot/caret in bars:", q(mh,"SELECT COUNT(*) FROM daily_bars WHERE symbol LIKE '%.%' OR symbol LIKE '%^%'"))
print("  instruments symbol prefixes:", q(mh,"SELECT substr(symbol,1,3), COUNT(*) FROM instruments GROUP BY 1 ORDER BY 2 DESC"))
mh.close(); tl.close()
