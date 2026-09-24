import sqlite3, json

TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"

def ro(p):
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

for name, path in (("trading_local", TL), ("market_history", MH)):
    c = ro(path)
    print("="*80)
    print(name)
    print("="*80)
    rows = c.execute(
        "SELECT type,name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name"
    ).fetchall()
    # find any table having a date-like column
    for t, n in rows:
        try:
            cols = [r[1] for r in c.execute(f'PRAGMA table_info("{n}")').fetchall()]
        except Exception as e:
            print(n, "ERR", e); continue
        datecols = [x for x in cols if any(k in x.lower() for k in
                    ("trade_date","bar_date","date","day","dt"))]
        if datecols:
            print(f"  {t:5s} {n:45s} datecols={datecols}")
    c.close()
