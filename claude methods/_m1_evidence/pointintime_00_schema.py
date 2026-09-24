import sqlite3, json, sys
sys.stdout.reconfigure(encoding='utf-8')

MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"

def ro(p):
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

for label, path, tables in [
    ("market_history", MH, ["daily_bars","ingest_runs","instruments","universe_snapshots","universe_members"]),
    ("trading_local", TL, ["daily_bar_cache","forecast_decisions","forecast_outcomes","forecast_evaluations","forecast_decision_days"]),
]:
    c = ro(path)
    print("="*100)
    print("DB:", label, path)
    print("="*100)
    rows = c.execute("SELECT name,type FROM sqlite_master WHERE type IN ('table','view') ORDER BY name").fetchall()
    print("ALL OBJECTS:", ", ".join(f"{n}" for n,t in rows))
    print()
    for t in tables:
        r = c.execute("SELECT sql FROM sqlite_master WHERE name=?", (t,)).fetchone()
        print("-"*90)
        print(f"[{label}.{t}]")
        print(r[0] if r else "  (missing)")
        print()
    # indexes on key tables
    for t in tables:
        idx = c.execute("SELECT name,sql FROM sqlite_master WHERE type='index' AND tbl_name=?", (t,)).fetchall()
        if idx:
            print(f"INDEXES on {t}:")
            for n,s in idx:
                print("   ", n, "|", (s or "(auto)"))
    c.close()
    print()
