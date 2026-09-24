import sqlite3, sys
OP = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"

def ro(p):
    import pathlib
    uri = "file:" + pathlib.Path(p).as_posix() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)

for name, path in (("trading_local", OP), ("market_history", MH)):
    c = ro(path)
    print("="*70)
    print(name)
    print("="*70)
    for (n, sql) in c.execute("select name, sql from sqlite_master where type='table' and name in ('daily_bar_cache','daily_bars','instruments','universe_snapshots','universe_members') order by name"):
        print("--", n)
        print(sql)
        print()
    # index list for the relevant tables
    for t in ('daily_bar_cache','daily_bars','instruments'):
        try:
            idx = list(c.execute(f"pragma index_list('{t}')"))
        except Exception as e:
            continue
        if idx:
            print(f"indexes on {t}: {idx}")
    c.close()
