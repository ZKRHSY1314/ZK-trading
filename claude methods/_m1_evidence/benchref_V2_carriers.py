import sqlite3
TL = "D:/codex-A股交易/trading_local.sqlite3"
MH = "D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

tl, mh = ro(TL), ro(MH)

print("### 1. global_market_bars DDL + content")
print(tl.execute("SELECT sql FROM sqlite_master WHERE name='global_market_bars'").fetchone()[0])
cols=[r[1] for r in tl.execute("PRAGMA table_info(global_market_bars)")]
print("cols:", cols)
for r in tl.execute("SELECT symbol, asset_class, COUNT(*) n, MIN(bar_time), MAX(bar_time) FROM global_market_bars GROUP BY symbol ORDER BY n DESC").fetchall():
    print("   ", r)

print()
print("### 2. market_regime_snapshots DDL (0 rows but shows intent)")
r=tl.execute("SELECT sql FROM sqlite_master WHERE name='market_regime_snapshots'").fetchone()
print(r[0] if r else None)

print()
print("### 3. ALL index-looking symbols in trading_local.daily_bar_cache")
q = """
SELECT symbol, COUNT(*) n, COUNT(DISTINCT trade_date) d, MIN(trade_date), MAX(trade_date)
FROM daily_bar_cache
WHERE symbol LIKE 'SH000%' OR symbol LIKE 'SZ399%' OR symbol LIKE 'BJ899%'
   OR symbol LIKE '%INDEX%' OR symbol LIKE 'SH950%' OR symbol LIKE 'SZ39%'
GROUP BY symbol ORDER BY n DESC
"""
for r in tl.execute(q).fetchall(): print("   ", r)

print()
print("### 4. market_history.daily_bars — any index symbols at all?")
q2 = """
SELECT symbol, adjustment_mode, COUNT(*) n, MIN(trade_date), MAX(trade_date)
FROM daily_bars
WHERE symbol LIKE 'SH000%' OR symbol LIKE 'SZ399%' OR symbol LIKE 'BJ899%'
GROUP BY symbol, adjustment_mode ORDER BY n DESC LIMIT 40
"""
for r in mh.execute(q2).fetchall(): print("   ", r)

print()
print("### 5. instruments with exchange='INDEX' — do any have bars?")
print("count INDEX instruments:", mh.execute("SELECT COUNT(*) FROM instruments WHERE exchange='INDEX'").fetchone()[0])
for r in mh.execute("SELECT symbol,name,asset_type,list_date,status FROM instruments WHERE exchange='INDEX' LIMIT 30").fetchall():
    print("   ", r)
print("asset_type distribution:", mh.execute("SELECT asset_type, COUNT(*) FROM instruments GROUP BY asset_type").fetchall())
print("exchange distribution:", mh.execute("SELECT exchange, COUNT(*) FROM instruments GROUP BY exchange").fetchall())

print()
print("### 6. Join: do INDEX instruments appear in daily_bars?")
q3 = """
SELECT i.symbol, i.name, COUNT(b.trade_date) nbars, MIN(b.trade_date), MAX(b.trade_date)
FROM instruments i LEFT JOIN daily_bars b ON b.symbol=i.symbol
WHERE i.exchange='INDEX' GROUP BY i.symbol ORDER BY nbars DESC LIMIT 30
"""
for r in mh.execute(q3).fetchall(): print("   ", r)
tl.close(); mh.close()
