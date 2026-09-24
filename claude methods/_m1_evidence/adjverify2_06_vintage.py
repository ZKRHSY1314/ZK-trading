import sqlite3
MH=r"D:\codex-A股交易\market_history.sqlite3"; OP=r"D:\codex-A股交易\trading_local.sqlite3"
def ro(p): return sqlite3.connect("file:"+p.replace("\\","/")+"?mode=ro",uri=True)
mh=ro(MH)
print("ingest_runs cols:", [r[1] for r in mh.execute("PRAGMA table_info(ingest_runs)")])
print("SQL: SELECT * FROM ingest_runs ORDER BY id LIMIT 5")
for r in mh.execute("SELECT * FROM ingest_runs ORDER BY id LIMIT 5"): print("   ",r)
print("SQL: SELECT COUNT(*) FROM ingest_runs / bar_quality_issues / training_dataset_manifests / universe_snapshots")
for t in ("ingest_runs","bar_quality_issues","training_dataset_manifests","universe_snapshots","universe_members","schema_metadata"):
    print("   ",t, mh.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
print("schema_metadata:", mh.execute("SELECT * FROM schema_metadata").fetchall())
# does row_hash preserve any prior vintage? one hash per key?
print("\nSQL: SELECT COUNT(*), COUNT(DISTINCT symbol||'|'||trade_date||'|'||adjustment_mode) FROM daily_bars")
print("   ", mh.execute("SELECT COUNT(*), COUNT(DISTINCT symbol||'|'||trade_date||'|'||adjustment_mode) FROM daily_bars").fetchone())
print("\nSQL: SELECT adjustment_mode, COUNT(*) FROM daily_bars GROUP BY 1  (confirm qfq-only)")
for r in mh.execute("SELECT adjustment_mode, COUNT(*) FROM daily_bars GROUP BY 1"): print("   ",r)
mh.close()
