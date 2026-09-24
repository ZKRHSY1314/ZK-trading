import sqlite3, glob, os
def ro(p):
    c=sqlite3.connect(f"file:{p}?mode=ro",uri=True); c.execute("PRAGMA query_only=1"); return c
paths = sorted(glob.glob(r"D:/codex-A股交易/logs/backups/*.sqlite3")+glob.glob(r"D:/codex-A股交易/output/backups/*.sqlite3")+[r"D:/codex-A股交易/backend/trading_local.sqlite3"])
for p in paths:
    try:
        c=ro(p)
        tabs={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        t = 'daily_bar_cache' if 'daily_bar_cache' in tabs else ('daily_bars' if 'daily_bars' in tabs else None)
        if t is None:
            print(f"{os.path.basename(p):62s} no bar table; tables={len(tabs)}"); continue
        n,mn,mx,amt_null,amt_ok = c.execute(f"SELECT COUNT(*),MIN(trade_date),MAX(trade_date),SUM(amount IS NULL),SUM(amount IS NOT NULL) FROM {t} WHERE length(trade_date)=10").fetchone()
        print(f"{os.path.basename(p):62s} {t:16s} rows={n:>9} {mn}..{mx} amtNULL={amt_null} amtOK={amt_ok}")
    except Exception as e:
        print(f"{os.path.basename(p):62s} ERR {e}")
