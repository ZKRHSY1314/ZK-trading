import sqlite3, json, collections

OPS = r"D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{OPS}?mode=ro", uri=True)

SQL = "SELECT id, evaluation_id, as_of, scope, horizon_days, status, fold_count, created_at, metrics_json FROM forecast_evaluations"
print("SQL:", SQL)
rows = c.execute(SQL).fetchall()
print("rows fetched =", len(rows))

# ---- key universe at EVERY nesting level, not just ['metrics'] ----
paths = collections.Counter()
def walk(o, pfx=""):
    if isinstance(o, dict):
        for k, v in o.items():
            p = f"{pfx}.{k}" if pfx else k
            paths[p] += 1
            walk(v, p)
    elif isinstance(o, list):
        for v in o[:3]:
            walk(v, pfx + "[]")

bad = 0
for r in rows:
    try:
        walk(json.loads(r[8]))
    except Exception:
        bad += 1
print("unparseable metrics_json payloads =", bad)

print("\n--- EVERY json path present in any of the 746 payloads (count of payloads containing it) ---")
for p, n in sorted(paths.items()):
    print(f"   {n:5d}/746  {p}")

# ---- targeted hunt for provenance-ish tokens ANYWHERE in the raw text ----
print("\n--- raw substring hunt across the full metrics_json TEXT (case-insensitive) ---")
needles = ["canonical", "policy_version", "policy", "evidence_quality", "evidence",
           "confirmed_fold", "provenance", "version", "schema", "lineage",
           "run_id", "ingest", "source", "adjustment", "generator", "code_version",
           "git", "commit", "build"]
SQL2 = "SELECT COUNT(*) FROM forecast_evaluations WHERE lower(metrics_json) LIKE ?"
for nd in needles:
    n = c.execute(SQL2, (f"%{nd}%",)).fetchone()[0]
    print(f"   {n:5d}/746  LIKE '%{nd}%'   -- SQL: {SQL2} with '%{nd}%'")

# ---- also hunt tokens in evaluation_id / as_of / status ----
print("\n--- status distribution ---")
SQL3 = "SELECT status, COUNT(*) FROM forecast_evaluations GROUP BY status ORDER BY 2 DESC"
print("SQL:", SQL3)
for s, n in c.execute(SQL3):
    print(f"   {s:22s} {n}")

print("\n--- created_at min/max (string) and as_of min/max ---")
SQL4 = "SELECT MIN(created_at), MAX(created_at), MIN(as_of), MAX(as_of) FROM forecast_evaluations"
print("SQL:", SQL4)
print("   ", c.execute(SQL4).fetchone())

print("\n--- created_at by day ---")
SQL5 = "SELECT substr(created_at,1,10) d, COUNT(*) n, SUM(status='ready') ready FROM forecast_evaluations GROUP BY d ORDER BY d"
print("SQL:", SQL5)
for d, n, rdy in c.execute(SQL5):
    print(f"   {d}  n={n:4d}  ready={rdy}")

print("\n--- as_of by day (as_of is an ISO timestamp, not a trade date) ---")
SQL6 = "SELECT substr(as_of,1,10) d, COUNT(*) n FROM forecast_evaluations GROUP BY d ORDER BY d"
print("SQL:", SQL6)
for d, n in c.execute(SQL6):
    print(f"   {d}  n={n}")
c.close()
