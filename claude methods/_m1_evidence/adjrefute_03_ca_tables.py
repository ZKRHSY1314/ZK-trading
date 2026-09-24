import sqlite3
TL=r"D:/codex-A股交易/trading_local.sqlite3"
MH=r"D:/codex-A股交易/market_history.sqlite3"
c=sqlite3.connect(f"file:{TL}?mode=ro",uri=True)
c.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")
print("--- mh.training_dataset_manifests DDL"); print(c.execute("SELECT sql FROM mh.sqlite_master WHERE name='training_dataset_manifests'").fetchone()[0])
print("rows:",c.execute("SELECT COUNT(*) FROM mh.training_dataset_manifests").fetchone())
print("--- trading_local.dataset2_staging_records DDL"); print(c.execute("SELECT sql FROM sqlite_master WHERE name='dataset2_staging_records'").fetchone()[0])
print("rows:",c.execute("SELECT COUNT(*) FROM dataset2_staging_records").fetchone())
# broader: ANY column named like a corporate action across trading_local
print("\n--- broad column scan across ALL trading_local tables")
hits=[]
for (n,) in c.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    for row in c.execute(f'PRAGMA table_info("{n}")'):
        col=row[1].lower()
        if any(k in col for k in ('divid','split','adj_fac','factor','corp','ex_div','bonus','rights')):
            hits.append((n,row[1]))
for h in hits: print("   ",h)
print("\n--- broad column scan across market_history")
hits=[]
for (n,) in c.execute("SELECT name FROM mh.sqlite_master WHERE type='table'"):
    for row in c.execute(f'PRAGMA mh.table_info("{n}")'):
        col=row[1].lower()
        if any(k in col for k in ('divid','split','adj_fac','factor','corp','ex_div','bonus','rights')):
            hits.append((n,row[1]))
for h in hits: print("   ",h)
c.close()
