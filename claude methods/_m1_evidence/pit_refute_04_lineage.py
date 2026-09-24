import sqlite3
MH='D:/codex-A股交易/market_history.sqlite3'; TL='D:/codex-A股交易/trading_local.sqlite3'
c=sqlite3.connect(f'file:{MH}?mode=ro',uri=True); c.row_factory=sqlite3.Row
c.execute("ATTACH DATABASE ? AS tl", (f'file:{TL}?mode=ro',))
print('D1 LINEAGE: does market_history.daily_bars.available_at equal the operational cache row-update clock?')
print("""SQL: SELECT COUNT(*) matched, SUM(b.available_at = k.updated_at) avail_eq_cache_updated,
       SUM(b.available_at = k.created_at) avail_eq_cache_created
     FROM daily_bars b JOIN tl.daily_bar_cache k
       ON k.symbol=b.symbol AND k.trade_date=b.trade_date""")
r=c.execute("""SELECT COUNT(*) matched,
       SUM(CASE WHEN b.available_at = k.updated_at THEN 1 ELSE 0 END) avail_eq_cache_updated,
       SUM(CASE WHEN b.available_at = k.created_at THEN 1 ELSE 0 END) avail_eq_cache_created,
       SUM(CASE WHEN b.available_at = substr(k.trade_date,1,10) THEN 1 ELSE 0 END) avail_eq_tradedate_fallback
FROM daily_bars b JOIN tl.daily_bar_cache k ON k.symbol=b.symbol AND k.trade_date=b.trade_date""").fetchone()
print(dict(r)); print()

print('D2 Is available_at a *market* fact or an *operator* fact? Distinct available_at per trade_date')
print("SQL: SELECT trade_date, COUNT(DISTINCT available_at) FROM daily_bars GROUP BY trade_date -> summarize")
r=c.execute("""SELECT MIN(k) mn, MAX(k) mx, AVG(k) avg, COUNT(*) trade_dates,
       SUM(CASE WHEN k=1 THEN 1 ELSE 0 END) tds_with_single_ts
FROM (SELECT trade_date, COUNT(DISTINCT available_at) k FROM daily_bars GROUP BY trade_date)""").fetchone()
print(dict(r)); print()

print('D3 Converse: does one available_at timestamp span many unrelated trade_dates? (proves it is an ingest clock)')
print("SQL: SELECT available_at, COUNT(DISTINCT trade_date) FROM daily_bars GROUP BY available_at ORDER BY 2 DESC LIMIT 5")
for r in c.execute("""SELECT available_at, COUNT(DISTINCT trade_date) td_span, COUNT(DISTINCT symbol) syms, COUNT(*) n,
       MIN(trade_date) lo, MAX(trade_date) hi
FROM daily_bars GROUP BY available_at ORDER BY td_span DESC LIMIT 5"""): print(dict(r))
print()

print('D4 Other PIT surfaces in market_history: universe_members / universe_snapshots')
for (n,s) in c.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name IN ('universe_members','universe_snapshots','ingest_runs')"):
    print('---',n); print(s)
c.close()
