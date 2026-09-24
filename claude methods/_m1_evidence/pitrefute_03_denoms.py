import sqlite3
OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
c = ro(OP)
c.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")

print("=== E. Are indices inflating the denominator? classify window rows by instruments.exchange ===")
q="""SELECT COALESCE(i.exchange,'<no_instrument_row>') exch, COALESCE(i.asset_type,'?') atype,
       COUNT(*) rows_, COUNT(DISTINCT d.symbol) syms,
       SUM(CASE WHEN julianday(substr(d.created_at,1,10))-julianday(d.trade_date) <= 3 THEN 1 ELSE 0 END) live_le3
FROM daily_bar_cache d LEFT JOIN mh.instruments i ON i.symbol = d.symbol
WHERE d.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
  AND d.trade_date BETWEEN '2023-09-04' AND '2026-09-04'
GROUP BY 1,2 ORDER BY rows_ DESC"""
print("SQL:", q)
tot=live=0; stot=slive=0
for exch,atype,rows_,syms,l in c.execute(q):
    print(f"  {exch:22s} {atype:10s} rows={rows_:>9,} syms={syms:>5} live<=3d={l:>7,}")
    tot+=rows_; live+=l
    if exch!='INDEX': stot+=rows_; slive+=l
print(f"  ALL      : rows={tot:,} live<=3d={live:,} ({100*live/tot:.2f}%) backfilled={100*(tot-live)/tot:.2f}%")
print(f"  EX-INDEX : rows={stot:,} live<=3d={slive:,} ({100*slive/stot:.2f}%) backfilled={100*(stot-slive)/stot:.2f}%")

print("\n=== F. DISTINCT-SECURITY denominator: how many symbols have ANY same-day row, and how many same-day DATES each has ===")
q2="""SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache
WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
  AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'"""
print("SQL:", q2); allsym=list(c.execute(q2))[0][0]; print("  symbols in window:", allsym)
q3="""SELECT n_same_day, COUNT(*) n_symbols FROM (
  SELECT symbol, SUM(CASE WHEN substr(created_at,1,10)=trade_date THEN 1 ELSE 0 END) n_same_day
  FROM daily_bar_cache
  WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
    AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'
  GROUP BY symbol) GROUP BY 1 ORDER BY 1"""
print("SQL:", q3)
for r in c.execute(q3): print("   same_day_bars_per_symbol=%s -> %s symbols" % r)

print("\n=== G. Per-symbol share of its own history captured <=3d (median-ish distribution) ===")
q4="""SELECT bucket, COUNT(*) FROM (
 SELECT symbol, CAST(100.0*SUM(CASE WHEN julianday(substr(created_at,1,10))-julianday(trade_date)<=3 THEN 1 ELSE 0 END)/COUNT(*) AS INT)/10*10 AS bucket
 FROM daily_bar_cache
 WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
   AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'
 GROUP BY symbol) GROUP BY 1 ORDER BY 1"""
print("SQL:", q4)
for r in c.execute(q4): print("   pct_live_bucket=%s%%-  -> %s symbols" % r)

print("\n=== H. Does market_history offer REAL point-in-time (available_at)? ===")
q5="""SELECT COUNT(*) n, SUM(available_at IS NULL) null_avail,
       MIN(available_at), MAX(available_at), MIN(fetched_at), MAX(fetched_at)
FROM mh.daily_bars WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'"""
print("SQL:", q5); print("  ", list(c.execute(q5))[0])
q6="""SELECT COUNT(DISTINCT available_at) FROM mh.daily_bars"""
print("SQL:", q6); print("  distinct available_at values:", list(c.execute(q6))[0][0])
q7="""SELECT available_at, COUNT(*) FROM mh.daily_bars GROUP BY 1 ORDER BY 2 DESC LIMIT 5"""
print("SQL:", q7)
for r in c.execute(q7): print("   ", r)
c.close()
