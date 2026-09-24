import sqlite3, json, os
OP = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"

def ro(p):
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

for label, path in (("trading_local", OP), ("market_history", MH)):
    print("="*70)
    print(label, path, os.path.getsize(path))
    c = ro(path); c.row_factory = sqlite3.Row
    tabs = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    hits = [t for t in tabs if 'forecast' in t or 'decision' in t or 'eval' in t or 'calib' in t]
    print("forecast-ish tables:", hits)
    for t in hits:
        cols = [(r[1], r[2]) for r in c.execute(f"PRAGMA table_info({t})")]
        n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}  rows={n}")
        print(f"    cols={[x[0] for x in cols]}")
    c.close()
