import sqlite3
TL = "D:/codex-A股交易/trading_local.sqlite3"
MH = "D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

tl, mh = ro(TL), ro(MH)

def ddl(c, t):
    r = c.execute("SELECT sql FROM sqlite_master WHERE name=?", (t,)).fetchone()
    return r[0] if r else None

print("### global_market_bars DDL");  print(ddl(tl,"global_market_bars"))
print("\n### market_regime_snapshots DDL"); print(ddl(tl,"market_regime_snapshots"))
print("\n### technical_indicators DDL"); print(ddl(tl,"technical_indicators"))

print("\n=== global_market_bars content ===")
q = """SELECT symbol, COUNT(*) n, COUNT(DISTINCT trade_date) d, MIN(trade_date), MAX(trade_date)
       FROM global_market_bars GROUP BY symbol ORDER BY n DESC"""
try:
    for r in tl.execute(q): print("   ", r)
except Exception as e:
    print("   ERR", e)
    print("   cols:", [x[1] for x in tl.execute("PRAGMA table_info(global_market_bars)")])

print("\n=== market_regime_snapshots sample ===")
cols=[x[1] for x in tl.execute("PRAGMA table_info(market_regime_snapshots)")]
print("   cols:", cols)
print("   count:", tl.execute("SELECT COUNT(*) FROM market_regime_snapshots").fetchone()[0])
