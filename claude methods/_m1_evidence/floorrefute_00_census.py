import sqlite3, os, sys

TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"

def ro(p):
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

for label, path in (("trading_local", TL), ("market_history", MH)):
    c = ro(path)
    print("="*90)
    print(f"DB={label}  {path}")
    rows = c.execute("SELECT name,type FROM sqlite_master WHERE type IN ('table','view') ORDER BY name").fetchall()
    print(f"  {len(rows)} tables/views")
    # find any table with a column that smells like a date
    for name, typ in rows:
        try:
            cols = c.execute(f'PRAGMA table_info("{name}")').fetchall()
        except Exception as e:
            print(f"  !! {name}: {e}")
            continue
        datecols = [x[1] for x in cols if any(k in x[1].lower() for k in ("date","day","dt","time","ts","period"))]
        if not datecols:
            continue
        try:
            n = c.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        except Exception as e:
            print(f"  !! count {name}: {e}")
            continue
        if n == 0:
            continue
        print(f"  -- {typ} {name}: {n} rows; datecols={datecols}")
    c.close()
