import sqlite3

OPS = r"D:/codex-A股交易/trading_local.sqlite3"
RES = r"D:/codex-A股交易/market_history.sqlite3"
TOKENS = ["canonical", "policy", "evidence", "confirmed_fold", "provenance", "legacy"]

for label, p in (("trading_local", OPS), ("market_history", RES)):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    print("="*78)
    print(f"Q4  Does ANY table/column in {label} carry a canonical/policy/evidence marker?")
    print("SQL: SELECT name FROM sqlite_master WHERE type='table'  -> PRAGMA table_info(<t>) for each")
    print("="*78)
    tabs = [r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    print(f"   {len(tabs)} tables scanned")
    hits = 0
    for t in tabs:
        for _, cn, *_ in c.execute(f'PRAGMA table_info("{t}")'):
            low = cn.lower()
            if any(tok in low for tok in TOKENS):
                n = c.execute(f'SELECT COUNT(*), COUNT("{cn}") FROM "{t}"').fetchone()
                print(f"   HIT  {t}.{cn}   rows={n[0]} non_null={n[1]}")
                hits += 1
    if hits == 0:
        print("   NO column in ANY table matches", TOKENS)
    c.close()
    print()

# forecast_decision_days + forecast_decisions schema, since a marker might live there
c = sqlite3.connect(f"file:{OPS}?mode=ro", uri=True)
for t in ("forecast_decision_days", "forecast_decisions", "forecast_outcomes"):
    print("="*78)
    print(f"Q5  DDL of {t}   SQL: SELECT sql FROM sqlite_master WHERE name='{t}'")
    print("="*78)
    print(c.execute("SELECT sql FROM sqlite_master WHERE name=?", (t,)).fetchone()[0])
    print()

print("="*78)
print("Q6  Can the 50 newest evaluations be distinguished from the 696 older ones by")
print("    ANY stored field other than created_at/as_of/id?  (payload schema fingerprint)")
print("="*78)
import json, hashlib, collections
SQL = ("SELECT created_at, metrics_json FROM forecast_evaluations")
print("SQL:", SQL)
fp = collections.Counter()
by_epoch = collections.defaultdict(collections.Counter)
for created, mj in c.execute(SQL):
    o = json.loads(mj)
    keys = tuple(sorted(o.keys())) + tuple(sorted(o.get("metrics", {}).keys()))
    h = hashlib.md5(str(keys).encode()).hexdigest()[:8]
    fp[h] += 1
    epoch = "2026-09-04" if created.startswith("2026-09-04") else "2026-07-xx"
    by_epoch[epoch][h] += 1
print("   distinct payload key-set fingerprints across all 746 rows:", len(fp), dict(fp))
for e, cc in by_epoch.items():
    print(f"   {e}: {dict(cc)}")
c.close()
