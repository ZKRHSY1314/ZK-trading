import sqlite3
OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
op = sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
mh = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)
print("SQL: SELECT symbol,COUNT(*) FROM daily_bar_cache GROUP BY symbol ORDER BY 2 DESC LIMIT 8")
for r in op.execute("SELECT symbol,COUNT(*) c FROM daily_bar_cache GROUP BY symbol ORDER BY c DESC LIMIT 8"): print("  ",r)
print("SQL: distinct symbol length / prefix census")
for r in op.execute("SELECT length(symbol) L, substr(symbol,1,1) p, COUNT(DISTINCT symbol) s, COUNT(*) n FROM daily_bar_cache GROUP BY L,p ORDER BY n DESC"): print("  ",r)
print("SQL: quality_status census")
for r in op.execute("SELECT quality_status, COUNT(*) n, COUNT(DISTINCT symbol) s FROM daily_bar_cache GROUP BY 1"): print("  ",r)
print("SQL: window row/symbol count 2023-09-04..2026-09-04, quality_status='ready'")
print("  ", op.execute("SELECT COUNT(*),COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE quality_status='ready' AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'").fetchone())
print("SQL: instruments exchange census (market_history)")
for r in mh.execute("SELECT exchange, asset_type, COUNT(*) FROM instruments GROUP BY 1,2 ORDER BY 3 DESC LIMIT 15"): print("  ",r)
print("SQL: sample INDEX symbols")
for r in mh.execute("SELECT symbol FROM instruments WHERE exchange='INDEX' LIMIT 10"): print("  ",r)
print("SQL: how many daily_bar_cache symbols are INDEX per instruments")
print("  ", op.execute("SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache").fetchone())
idx = {r[0] for r in mh.execute("SELECT symbol FROM instruments WHERE exchange='INDEX'")}
syms = {r[0] for r in op.execute("SELECT DISTINCT symbol FROM daily_bar_cache")}
print("  index symbols present in cache:", len(syms & idx), "sample:", sorted(syms & idx)[:10])
print("  cache symbols NOT in instruments at all:", len(syms - {r[0] for r in mh.execute('SELECT symbol FROM instruments')}))
