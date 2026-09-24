import sqlite3, json
P_OPS = r"D:/codex-A股交易/trading_local.sqlite3"
P_HIST = r"D:/codex-A股交易/market_history.sqlite3"

def ro(p):
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

for label, p in (("trading_local", P_OPS), ("market_history", P_HIST)):
    c = ro(p)
    print("="*100)
    print("DB:", label, p)
    rows = c.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view') ORDER BY name").fetchall()
    print("  objects:", len(rows))
    # find any table with a trade_date-ish or date-ish column
    for name, typ in rows:
        try:
            cols = [r[1] for r in c.execute(f'PRAGMA table_info("{name}")').fetchall()]
        except Exception as e:
            print("   ! pragma fail", name, e); continue
        datecols = [x for x in cols if any(k in x.lower() for k in ("trade_date","date","dt","day","timestamp","ts"))]
        if datecols:
            print(f"  [{typ}] {name}: datecols={datecols}")
    c.close()
