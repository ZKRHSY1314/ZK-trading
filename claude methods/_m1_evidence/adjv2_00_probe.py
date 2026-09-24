import sqlite3
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
m = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)

print("=== cache symbol samples ===")
for r in c.execute("SELECT DISTINCT symbol FROM daily_bar_cache ORDER BY symbol LIMIT 15"): print(r)
print("...")
for r in c.execute("SELECT DISTINCT symbol FROM daily_bar_cache ORDER BY symbol DESC LIMIT 15"): print(r)

print("\n=== cache symbol prefix histogram (first 3 chars) ===")
for r in c.execute("""SELECT substr(symbol,1,3) p, COUNT(DISTINCT symbol) nsym, COUNT(*) nrow
                      FROM daily_bar_cache GROUP BY p ORDER BY nsym DESC LIMIT 60"""):
    print(r)

print("\n=== cache adjustment_mode / volume_unit / source ===")
for r in c.execute("SELECT adjustment_mode, COUNT(*) FROM daily_bar_cache GROUP BY 1"): print(r)
for r in c.execute("SELECT source, COUNT(*), COUNT(DISTINCT symbol) FROM daily_bar_cache GROUP BY 1 ORDER BY 2 DESC"): print(r)

print("\n=== mh adjustment_mode ===")
for r in m.execute("SELECT adjustment_mode, COUNT(*), COUNT(DISTINCT symbol) FROM daily_bars GROUP BY 1"): print(r)
print("\n=== mh symbol samples ===")
for r in m.execute("SELECT DISTINCT symbol FROM daily_bars ORDER BY symbol LIMIT 10"): print(r)
print("\n=== mh instruments asset_type/exchange ===")
for r in m.execute("SELECT exchange, asset_type, COUNT(*) FROM instruments GROUP BY 1,2 ORDER BY 3 DESC LIMIT 40"): print(r)
print("\n=== mh instruments sample ===")
for r in m.execute("SELECT * FROM instruments LIMIT 3"): print(r)
print([d[0] for d in m.execute("SELECT * FROM instruments LIMIT 1").description])
