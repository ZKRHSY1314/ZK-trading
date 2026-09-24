import sqlite3, json
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True); c.row_factory=sqlite3.Row; return c
mh=ro(MH); tl=ro(TL)
def q(c,s,a=()): return [dict(r) for r in c.execute(s,a).fetchall()]
def one(c,s,a=()):
    r=c.execute(s,a).fetchone(); return r[0] if r else None
W0,W1 = '2023-09-04','2026-09-04'

print("="*78); print("E. NO DB CONFLATION: does trading_local.daily_bar_cache even have available_at?"); print("="*78)
cols=[r['name'] for r in q(tl,"PRAGMA table_info(daily_bar_cache)")]
print("trading_local.daily_bar_cache columns:", cols)
print("has available_at ->", 'available_at' in cols, " (claim is about market_history.daily_bars only)")

print("\n"+"="*78); print("F. COUNT SECURITIES, NOT ROWS — and EXCLUDE INDICES"); print("="*78)
print("SQL: JOIN instruments USING(symbol); classify by exchange<>'INDEX' and asset_type")
print(q(mh,"SELECT exchange, COUNT(*) n FROM instruments GROUP BY exchange ORDER BY n DESC"))
print("\nSQL: SELECT COUNT(DISTINCT b.symbol) FROM daily_bars b JOIN instruments i USING(symbol)")
print("     WHERE i.exchange NOT IN ('INDEX','OTHER')  [stocks only]")
tot_sym = one(mh,"""SELECT COUNT(DISTINCT b.symbol) FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
                    WHERE i.exchange NOT IN ('INDEX','OTHER')""")
print("   stock symbols with any bar =", f"{tot_sym:,}")
# symbols where EVERY bar is PIT-plausible (lag<=1), and where ANY bar is
row=q(mh,"""WITH lag AS (
  SELECT b.symbol, julianday(substr(b.available_at,1,10))-julianday(b.trade_date) d
  FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
  WHERE i.exchange NOT IN ('INDEX','OTHER'))
SELECT COUNT(*) nsym,
  SUM(CASE WHEN mx<=1 THEN 1 ELSE 0 END) all_bars_pit,
  SUM(CASE WHEN mn<=1 THEN 1 ELSE 0 END) any_bar_pit
FROM (SELECT symbol, MIN(d) mn, MAX(d) mx FROM lag GROUP BY symbol)""")[0]
print("   SQL: per-symbol MIN/MAX of (available_at - trade_date), stocks only")
print("   stock symbols total                        :", f"{row['nsym']:,}")
print("   stock symbols where EVERY bar has lag<=1d  :", f"{row['all_bars_pit']:,}")
print("   stock symbols where ANY  bar has lag<=1d   :", f"{row['any_bar_pit']:,}")

print("\n-- same >30d test restricted to STOCKS ONLY (indices removed) --")
print("SQL: SELECT COUNT(*) FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol")
print("     WHERE i.exchange NOT IN ('INDEX','OTHER') AND julianday(substr(available_at,1,10))-julianday(trade_date)>30")
st_tot=one(mh,"""SELECT COUNT(*) FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
                 WHERE i.exchange NOT IN ('INDEX','OTHER')""")
st_bad=one(mh,"""SELECT COUNT(*) FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
                 WHERE i.exchange NOT IN ('INDEX','OTHER')
                   AND julianday(substr(b.available_at,1,10))-julianday(b.trade_date)>30""")
print(f"   stocks-only: {st_bad:,} / {st_tot:,} = {100.0*st_bad/st_tot:.2f}% have lag>30d")

print("\n-- restricted to RESEARCH WINDOW 2023-09-04..2026-09-04, stocks only --")
w_tot=one(mh,"""SELECT COUNT(*) FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
                WHERE i.exchange NOT IN ('INDEX','OTHER') AND b.trade_date BETWEEN ? AND ?""",(W0,W1))
w_bad=one(mh,"""SELECT COUNT(*) FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
                WHERE i.exchange NOT IN ('INDEX','OTHER') AND b.trade_date BETWEEN ? AND ?
                  AND julianday(substr(b.available_at,1,10))-julianday(b.trade_date)>30""",(W0,W1))
print(f"   window+stocks: {w_bad:,} / {w_tot:,} = {100.0*w_bad/w_tot:.2f}% have lag>30d")

print("\n"+"="*78); print("G. STEELMAN: are the lag<=1 rows genuine daily PIT capture, or batch edge?"); print("="*78)
print("If available_at were a real PIT stamp, lag<=1 rows would be spread over MANY")
print("ingest days. If they are just the leading edge of the 4 bulk batches, their")
print("available_at day will be one of the same 4 batch days.")
print("SQL: SELECT substr(available_at,1,10) d, COUNT(*), MIN(trade_date), MAX(trade_date)")
print("     FROM daily_bars WHERE julianday(substr(available_at,1,10))-julianday(trade_date)<=1 GROUP BY d")
for r in q(mh,"""SELECT substr(available_at,1,10) d, COUNT(*) n, MIN(trade_date) mn, MAX(trade_date) mx
   FROM daily_bars WHERE julianday(substr(available_at,1,10))-julianday(trade_date) BETWEEN 0 AND 1
   GROUP BY d ORDER BY n DESC"""):
    print(f"   {r['d']}  n={r['n']:>7,}  trade_date {r['mn']} .. {r['mx']}")

print("\n"+"="*78); print("H. OPERATIONAL TEST: can you actually reconstruct an as-of view?"); print("="*78)
print("SQL: SELECT COUNT(*), COUNT(DISTINCT symbol), MAX(trade_date) FROM daily_bars WHERE available_at <= <asof>")
for asof in ('2023-12-31','2024-06-30','2025-01-02','2025-06-30','2026-01-05','2026-07-14','2026-07-16','2026-09-04'):
    r=q(mh,"""SELECT COUNT(*) n, COUNT(DISTINCT symbol) s, MAX(trade_date) mx
              FROM daily_bars WHERE substr(available_at,1,10) <= ?""",(asof,))[0]
    print(f"   as-of {asof} : visible_bars={r['n']:>9,}  symbols={r['s'] or 0:>5}  max_trade_date={r['mx']}")

print("\n"+"="*78); print("I. universe_snapshots — do snapshots give PIT where bars don't?"); print("="*78)
print("SQL: SELECT id, universe_name, snapshot_date, fetched_at FROM universe_snapshots")
for r in q(mh,"SELECT * FROM universe_snapshots ORDER BY snapshot_date"):
    print("  ", {k:r[k] for k in list(r)[:8]})
mh.close(); tl.close()
