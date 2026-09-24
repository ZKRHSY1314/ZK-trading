import sqlite3
for tag, p in [("LOCAL", r"D:/codex-A股交易/trading_local.sqlite3"),
               ("HIST",  r"D:/codex-A股交易/market_history.sqlite3")]:
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    rows = c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    print(f"=== {tag} ({len(rows)} tables) ===")
    print(", ".join(r[0] for r in rows))
    print()
    c.close()
