import sqlite3
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
for name, p in (("trading_local", TL), ("market_history", MH)):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    print("="*70); print(name)
    for (n, s) in c.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name IN ('daily_bar_cache','instruments','daily_bars','universe_snapshots','universe_members')"):
        print("---", n); print(s)
    c.close()
