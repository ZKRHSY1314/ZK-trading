import sqlite3, json
OP = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"
def ro(p):
    return sqlite3.connect(f"file:{p.replace(chr(92),'/')}?mode=ro", uri=True)

for name, p in (("trading_local", OP), ("market_history", MH)):
    c = ro(p)
    print("="*90); print("DB:", name)
    rows = c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    print("TABLE COUNT:", len(rows))
    # find every table that has a trade_date-ish column
    cands = []
    for (t,) in rows:
        try:
            cols = [r[1] for r in c.execute(f'PRAGMA table_info("{t}")').fetchall()]
        except Exception:
            continue
        dcols = [x for x in cols if x.lower() in ("trade_date","date","bar_date","dt","trading_day","trade_day","session_date")]
        if dcols:
            cands.append((t, dcols, cols))
    print("TABLES WITH A DATE-LIKE COLUMN:", len(cands))
    for t, dcols, cols in cands:
        try:
            n = c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        except Exception as e:
            print(f"  {t}: ERR {e}"); continue
        if n == 0:
            print(f"  {t}: 0 rows"); continue
        d = dcols[0]
        mn, mx = c.execute(f'SELECT MIN("{d}"), MAX("{d}") FROM "{t}"').fetchone()
        print(f"  {t}: rows={n} {d} min={mn!r} max={mx!r}")
    c.close()
