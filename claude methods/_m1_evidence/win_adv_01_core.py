# -*- coding: utf-8 -*-
import sqlite3
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
def hdr(t): print("\n"+"="*74+"\n"+t+"\n"+"="*74)

mh = ro(MH); tl = ro(TL)

hdr("A. instruments -- my own independent census (NOT their query)")
# their claim: 5561 total, all asset_type='stock', 0 delist, 5 inactive
q = """
SELECT asset_type, exchange, status,
       COUNT(*) n,
       SUM(CASE WHEN list_date IS NULL OR trim(list_date)='' THEN 1 ELSE 0 END) no_list,
       SUM(CASE WHEN delist_date IS NULL OR trim(delist_date)='' THEN 1 ELSE 0 END) no_delist,
       MIN(NULLIF(trim(list_date),'')) min_list, MAX(NULLIF(trim(list_date),'')) max_list
FROM instruments GROUP BY 1,2,3 ORDER BY n DESC
"""
print("SQL:", q.strip())
for r in mh.execute(q): print("   ", r)

hdr("B. Is delist_date empty-string vs NULL vs literal 'None'/'nan'? typeof census")
q = """
SELECT typeof(delist_date) t, COUNT(*) n,
       COUNT(DISTINCT COALESCE(delist_date,'<NULL>')) distinct_vals
FROM instruments GROUP BY 1
"""
print("SQL:", q.strip())
for r in mh.execute(q): print("   ", r)
q2 = "SELECT DISTINCT COALESCE(delist_date,'<NULL>') FROM instruments LIMIT 20"
print("SQL:", q2)
print("   ", [r[0] for r in mh.execute(q2)])
q3 = "SELECT DISTINCT COALESCE(status,'<NULL>') s, COUNT(*) FROM instruments GROUP BY 1"
print("SQL:", q3)
for r in mh.execute(q3): print("   ", r)
q4 = "SELECT symbol,name,exchange,status,list_date,delist_date,provider,fetched_at FROM instruments WHERE status<>'active'"
print("SQL:", q4)
for r in mh.execute(q4): print("   ", r)

hdr("C. THE REAL TEST: securities present in BAR data but ABSENT from instruments")
# If delisted names were captured in bars, evidence of the historical universe EXISTS on disk
q = """
SELECT COUNT(DISTINCT b.symbol)
FROM daily_bars b LEFT JOIN instruments i ON i.symbol=b.symbol
WHERE i.symbol IS NULL
"""
print("SQL(market_history):", q.strip())
print("   bars-symbols-not-in-instruments =", mh.execute(q).fetchone()[0])
print("   total distinct symbols in daily_bars =", mh.execute("SELECT COUNT(DISTINCT symbol) FROM daily_bars").fetchone()[0])
print("   total distinct symbols in instruments =", mh.execute("SELECT COUNT(DISTINCT symbol) FROM instruments").fetchone()[0])

hdr("D. Same test on trading_local.daily_bar_cache (the store that ACTUALLY feeds backtest)")
print("   distinct symbols in daily_bar_cache =",
      tl.execute("SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache").fetchone()[0])
q = "SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'"
print("SQL:", q)
print("   distinct symbols with >=1 bar inside window =", tl.execute(q).fetchone()[0])

hdr("E. Cross-DB: symbols in daily_bar_cache NOT in market_history.instruments")
cache_syms = {r[0] for r in tl.execute("SELECT DISTINCT symbol FROM daily_bar_cache")}
mh_syms    = {r[0] for r in mh.execute("SELECT DISTINCT symbol FROM daily_bars")}
inst       = {r[0] for r in mh.execute("SELECT symbol FROM instruments")}
inst_stock = {r[0] for r in mh.execute("SELECT symbol FROM instruments WHERE asset_type='stock' AND exchange IN ('SH','SZ','BJ')")}
print("   |daily_bar_cache| =", len(cache_syms))
print("   |daily_bars|      =", len(mh_syms))
print("   |instruments|     =", len(inst))
print("   |instruments stock@SH/SZ/BJ| =", len(inst_stock))
print("   cache - instruments =", len(cache_syms - inst))
print("   bars  - instruments =", len(mh_syms - inst))
print("   instruments - cache =", len(inst - cache_syms))
extra = sorted(cache_syms - inst)
print("   sample cache-only symbols:", extra[:40])

hdr("F. De-facto DELISTING evidence: symbols whose LAST bar is long before window end")
# a stock that stops trading permanently inside the window IS listing-history evidence
q = """
SELECT last_d, COUNT(*) FROM (
  SELECT symbol, MAX(trade_date) last_d
  FROM daily_bar_cache
  WHERE trade_date <= '2026-09-04'
  GROUP BY symbol
) GROUP BY 1 ORDER BY 1
"""
rows = tl.execute(q).fetchall()
print("SQL:", q.strip())
print("   distinct last-bar dates:", len(rows))
print("   earliest 25 last-bar dates (symbol counts):", rows[:25])
print("   latest 10:", rows[-10:])
tot = sum(n for _,n in rows)
dead = sum(n for d,n in rows if d < '2026-06-01')
print(f"   symbols whose last bar < 2026-06-01 (candidate dead/suspended/delisted) = {dead} of {tot}")

hdr("G. First-bar distribution: NEW LISTING evidence inside the window")
q = """
SELECT substr(first_d,1,7) ym, COUNT(*) FROM (
  SELECT symbol, MIN(trade_date) first_d FROM daily_bar_cache GROUP BY symbol
) WHERE first_d >= '2023-09-04' GROUP BY 1 ORDER BY 1
"""
print("SQL:", q.strip())
rr = tl.execute(q).fetchall()
print("   months with new first-bars:", len(rr), " total symbols first appearing in-window:", sum(n for _,n in rr))
print("  ", rr[:12], "...", rr[-6:])
mh.close(); tl.close()
