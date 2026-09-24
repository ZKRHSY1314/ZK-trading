import sqlite3, json
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
print("=== forecast_decisions DDL ===")
for (s,) in c.execute("SELECT sql FROM sqlite_master WHERE name='forecast_decisions'"):
    print(s)
print("\n=== daily_bar_cache DDL ===")
for (s,) in c.execute("SELECT sql FROM sqlite_master WHERE name LIKE 'daily_bar_cache%'"):
    print(s)
print("\n=== forecast_decisions scope distribution ===")
for r in c.execute("SELECT scope, COUNT(*) n, COUNT(DISTINCT decision_id) dids, COUNT(DISTINCT subject) subs FROM forecast_decisions GROUP BY scope ORDER BY n DESC"):
    print(r)
print("\n=== distinct (decision_id,subject) pairs by scope ===")
for r in c.execute("SELECT scope, COUNT(*) FROM (SELECT DISTINCT scope,decision_id,subject FROM forecast_decisions) GROUP BY scope"):
    print(r)
print("\n=== sample forecast_decisions rows (stock) ===")
cur = c.execute("SELECT * FROM forecast_decisions WHERE scope='stock' LIMIT 3")
cols=[d[0] for d in cur.description]
for row in cur:
    print(json.dumps(dict(zip(cols,row)), ensure_ascii=False)[:1200])
print("\n=== decision_cutoff format census (stock) ===")
for r in c.execute("""SELECT length(decision_cutoff) L, substr(decision_cutoff,11,1) sep,
  substr(decision_cutoff,-1) tail, COUNT(*) n, MIN(decision_cutoff), MAX(decision_cutoff)
  FROM forecast_decisions WHERE scope='stock' GROUP BY 1,2,3"""):
    print(r)
print("\n=== daily_bar_cache created_at format census ===")
for r in c.execute("""SELECT length(created_at) L, substr(created_at,11,1) sep, typeof(created_at) t,
  COUNT(*) n, MIN(created_at), MAX(created_at) FROM daily_bar_cache GROUP BY 1,2,3 ORDER BY n DESC LIMIT 10"""):
    print(r)
print("\n=== daily_bar_cache created_at NULLs ===")
print(list(c.execute("SELECT SUM(created_at IS NULL), SUM(updated_at IS NULL), COUNT(*) FROM daily_bar_cache")))
c.close()
