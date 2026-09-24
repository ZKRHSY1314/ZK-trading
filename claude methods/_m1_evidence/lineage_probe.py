import sqlite3, os
CACHE = r"D:/codex-A股交易/trading_local.sqlite3"
HIST  = r"D:/codex-A股交易/market_history.sqlite3"

def ro(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    c.execute("PRAGMA query_only=ON")
    c.row_factory = sqlite3.Row
    return c

for label, p in (("cache", CACHE), ("hist", HIST)):
    print("="*70); print(label, p, os.path.getsize(p))
    c = ro(p)
    print("journal_mode:", c.execute("PRAGMA journal_mode").fetchone()[0])
    print("query_only:", c.execute("PRAGMA query_only").fetchone()[0])
    c.close()

c = ro(CACHE)
print("\n--- cache daily_bar_cache sample symbols ---")
for r in c.execute("SELECT symbol, trade_date, close, source, adjustment_mode, volume_unit, quality_status FROM daily_bar_cache LIMIT 5"):
    print(dict(r))
print("distinct symbol format probe:")
for r in c.execute("SELECT symbol, COUNT(*) n FROM daily_bar_cache GROUP BY symbol ORDER BY symbol LIMIT 5"):
    print(dict(r))
c.close()

h = ro(HIST)
print("\n--- hist daily_bars sample ---")
for r in h.execute("SELECT symbol, trade_date, adjustment_mode, close, provider, available_at, fetched_at, quality_status FROM daily_bars LIMIT 5"):
    print(dict(r))
print("--- instruments sample ---")
for r in h.execute("SELECT symbol, name, exchange, asset_type, board, list_date, delist_date, status FROM instruments LIMIT 5"):
    print(dict(r))
h.close()
