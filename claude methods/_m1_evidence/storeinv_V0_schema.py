import sqlite3, re, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
DBS = {
 "trading_local": r"D:/codex-A股交易/trading_local.sqlite3",
 "market_history": r"D:/codex-A股交易/market_history.sqlite3",
}
DATECOLS = re.compile(r"(date|day|dt|time|ts|available_at|as_of|asof)", re.I)
for name, path in DBS.items():
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    cur = con.cursor()
    print("="*90)
    print("DB:", name)
    rows = cur.execute("SELECT name,type FROM sqlite_master WHERE type IN ('table','view') ORDER BY name").fetchall()
    print("n_objects:", len(rows))
    for tname, ttype in rows:
        if tname.startswith("sqlite_"): continue
        cols = cur.execute(f'PRAGMA table_info("{tname}")').fetchall()
        colnames = [c[1] for c in cols]
        dcols = [c for c in colnames if DATECOLS.search(c)]
        if not dcols: continue
        try:
            n = cur.execute(f'SELECT COUNT(*) FROM "{tname}"').fetchone()[0]
        except Exception as e:
            print(f"  {tname}: COUNT failed {e}"); continue
        if n == 0: continue
        print(f"  [{ttype}] {tname}  rows={n}  datecols={dcols}")
    con.close()
