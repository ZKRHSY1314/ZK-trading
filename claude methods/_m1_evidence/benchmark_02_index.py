import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

mh = ro(MH); op = ro(OP)

print("### Q1  market_history.instruments by exchange / asset_type")
q="SELECT exchange, asset_type, COUNT(*) FROM instruments GROUP BY exchange, asset_type ORDER BY 3 DESC"
print("SQL:", q)
for r in mh.execute(q): print("   ", r)

print("\n### Q2  every INDEX / index-asset_type instrument, with daily_bars row counts")
q="""SELECT i.symbol, i.name, i.exchange, i.asset_type, i.board, i.list_date, i.delist_date, i.status,
       i.provider, i.fetched_at,
       (SELECT COUNT(*) FROM daily_bars b WHERE b.symbol=i.symbol) AS bars,
       (SELECT MIN(trade_date) FROM daily_bars b WHERE b.symbol=i.symbol) AS d0,
       (SELECT MAX(trade_date) FROM daily_bars b WHERE b.symbol=i.symbol) AS d1
FROM instruments i
WHERE i.exchange='INDEX' OR lower(i.asset_type) LIKE '%index%'
ORDER BY i.symbol"""
print("SQL:", q)
for r in mh.execute(q): print("   ", r)

print("\n### Q3  market_history.daily_bars distinct symbol prefixes (len + first3)")
q="SELECT length(symbol) AS L, substr(symbol,1,3) AS p3, COUNT(DISTINCT symbol) AS syms, COUNT(*) AS rows FROM daily_bars GROUP BY L,p3 ORDER BY rows DESC LIMIT 40"
print("SQL:", q)
for r in mh.execute(q): print("   ", r)

print("\n### Q4  trading_local.daily_bar_cache symbol shape")
q="SELECT length(symbol) AS L, substr(symbol,1,3) AS p3, COUNT(DISTINCT symbol) AS syms, COUNT(*) AS rows FROM daily_bar_cache GROUP BY L,p3 ORDER BY rows DESC LIMIT 40"
print("SQL:", q)
for r in op.execute(q): print("   ", r)

CAND = ['000300','000001','399006','399001','399300','000905','000016','000852','399005','899050',
        'sh000300','sh000001','sz399006','sz399001','000688','000010','SH000300','SH000001']
print("\n### Q5  candidate benchmark symbols in each bar store")
for s in CAND:
    a = op.execute("SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM daily_bar_cache WHERE symbol=?", (s,)).fetchone()
    b = mh.execute("SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM daily_bars WHERE symbol=?", (s,)).fetchone()
    if a[0] or b[0]:
        print(f"   {s:10s} daily_bar_cache={a}   market_history.daily_bars={b}")
    else:
        print(f"   {s:10s} ABSENT from both")
op.close(); mh.close()
