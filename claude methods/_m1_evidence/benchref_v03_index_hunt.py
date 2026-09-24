import sqlite3
TL = "D:/codex-A股交易/trading_local.sqlite3"
MH = "D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
tl, mh = ro(TL), ro(MH)

print("=== A. global_market_bars by symbol ===")
for r in tl.execute("""SELECT symbol, asset_class, source, COUNT(*) n,
                              MIN(substr(bar_time,1,10)), MAX(substr(bar_time,1,10))
                       FROM global_market_bars GROUP BY symbol, asset_class, source ORDER BY n DESC LIMIT 40"""):
    print("   ", r)
print("   TOTAL rows:", tl.execute("SELECT COUNT(*) FROM global_market_bars").fetchone()[0])

print("\n=== B. trading_local.daily_bar_cache : ALL non-6-digit-stock-looking symbols ===")
# every distinct symbol whose numeric part starts with 000/399/899/950 (index ranges) OR that is not a plain stock
for r in tl.execute("""SELECT symbol, COUNT(*) n, MIN(trade_date), MAX(trade_date), COUNT(DISTINCT source)
                       FROM daily_bar_cache
                       WHERE symbol LIKE 'SH000%' OR symbol LIKE 'SZ399%' OR symbol LIKE 'BJ899%'
                          OR symbol LIKE '%INDEX%' OR symbol LIKE 'HSI%' OR symbol LIKE '%.%'
                       GROUP BY symbol ORDER BY n DESC LIMIT 60"""):
    print("   ", r)

print("\n=== C. distinct symbol PREFIX/shape census in daily_bar_cache ===")
for r in tl.execute("""SELECT substr(symbol,1,2) pfx, length(symbol) len, COUNT(DISTINCT symbol) nsym, COUNT(*) nrows
                       FROM daily_bar_cache GROUP BY pfx, len ORDER BY nrows DESC LIMIT 30"""):
    print("   ", r)

print("\n=== D. market_history.instruments where exchange='INDEX' or asset_type index-like ===")
for r in mh.execute("""SELECT exchange, asset_type, COUNT(*) FROM instruments
                       GROUP BY exchange, asset_type ORDER BY 3 DESC"""):
    print("   ", r)
print("   -- INDEX rows sample:")
for r in mh.execute("""SELECT symbol, name, exchange, asset_type, board, list_date, delist_date, status
                       FROM instruments WHERE exchange='INDEX' OR asset_type LIKE '%index%' LIMIT 25"""):
    print("   ", r)

print("\n=== E. Do INDEX instruments have ANY bars in market_history.daily_bars? ===")
r = mh.execute("""SELECT COUNT(DISTINCT b.symbol), COUNT(*), MIN(b.trade_date), MAX(b.trade_date)
                  FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
                  WHERE i.exchange='INDEX'""").fetchone()
print("   INDEX-instrument bars in market_history.daily_bars:", r)

print("\n=== F. market_history.daily_bars symbol-shape census ===")
for r in mh.execute("""SELECT substr(symbol,1,2) pfx, length(symbol) len, COUNT(DISTINCT symbol) nsym, COUNT(*) nrows
                       FROM daily_bars GROUP BY pfx, len ORDER BY nrows DESC LIMIT 30"""):
    print("   ", r)

print("\n=== G. market_history.daily_bars: any SH000xxx / SZ399xxx? ===")
for r in mh.execute("""SELECT symbol, adjustment_mode, COUNT(*) n, MIN(trade_date), MAX(trade_date)
                       FROM daily_bars WHERE symbol LIKE 'SH000%' OR symbol LIKE 'SZ399%'
                       GROUP BY symbol, adjustment_mode ORDER BY n DESC LIMIT 40"""):
    print("   ", r)
