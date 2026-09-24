import sqlite3, json
OP = r"D:\codex-A股交易\trading_local.sqlite3"
c = sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
cur = c.cursor()
for t in ("forecast_decisions","daily_bar_cache"):
    print("="*70); print("SCHEMA", t)
    r = cur.execute("SELECT sql FROM sqlite_master WHERE name=?", (t,)).fetchone()
    print(r[0] if r else "MISSING")
print("="*70)
print("indexes on daily_bar_cache:")
for row in cur.execute("SELECT name,sql FROM sqlite_master WHERE type='index' AND tbl_name='daily_bar_cache'"):
    print(" ", row)
print("="*70)
print("forecast_decisions scope distribution:")
for row in cur.execute("SELECT scope, COUNT(*) n, COUNT(DISTINCT decision_id) nd, COUNT(DISTINCT subject) ns FROM forecast_decisions GROUP BY scope ORDER BY n DESC"):
    print("  ", row)
print("="*70)
print("sample forecast_decisions rows (scope=stock):")
cols = [d[1] for d in cur.execute("PRAGMA table_info(forecast_decisions)")]
print("cols:", cols)
for row in cur.execute("SELECT * FROM forecast_decisions WHERE scope='stock' LIMIT 3"):
    print(json.dumps(dict(zip(cols,row)), ensure_ascii=False, default=str)[:1200])
print("="*70)
print("distinct created_at FORMAT samples in daily_bar_cache:")
for row in cur.execute("SELECT created_at, updated_at, COUNT(*) FROM daily_bar_cache GROUP BY length(created_at), substr(created_at,11,1) LIMIT 20"):
    print("  ", row)
print("="*70)
print("distinct cutoff FORMAT samples:")
for row in cur.execute("SELECT decision_cutoff, COUNT(*) FROM forecast_decisions GROUP BY length(decision_cutoff), substr(decision_cutoff,11,1), substr(decision_cutoff,-1) LIMIT 20"):
    print("  ", row)
c.close()
