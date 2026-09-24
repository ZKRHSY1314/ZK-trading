import sqlite3
TL = "D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
tl = ro(TL)

print("=== bare 6-digit symbols in daily_bar_cache (auditor's filter length(symbol)=8 DROPS these) ===")
for r in tl.execute("""SELECT symbol, COUNT(*) n, MIN(trade_date), MAX(trade_date), source, quality_status,
                              adjustment_mode, volume_unit
                       FROM daily_bar_cache WHERE length(symbol)=6
                       GROUP BY symbol, source, quality_status, adjustment_mode, volume_unit"""):
    print("   ", r)

print("\n=== every distinct symbol NOT matching ^(SH|SZ|BJ)\d{6}$ ===")
for r in tl.execute("""SELECT symbol, COUNT(*) FROM daily_bar_cache
                       WHERE symbol NOT GLOB '[SB][HZJ][0-9][0-9][0-9][0-9][0-9][0-9]'
                       GROUP BY symbol ORDER BY 2 DESC LIMIT 50"""):
    print("   ", r)

print("\n=== all SH00* symbols (check auditor's 'symbol NOT LIKE SH00%' calendar exclusion is safe) ===")
for r in tl.execute("""SELECT symbol, COUNT(*) FROM daily_bar_cache WHERE symbol LIKE 'SH00%'
                       GROUP BY symbol ORDER BY 2 DESC"""):
    print("   ", r)

print("\n=== sample rows of the 6-digit symbols ===")
for r in tl.execute("""SELECT symbol, trade_date, open, high, low, close, volume, amount, source
                       FROM daily_bar_cache WHERE length(symbol)=6 ORDER BY symbol, trade_date LIMIT 12"""):
    print("   ", r)
