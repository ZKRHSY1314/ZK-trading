import sqlite3, json, hashlib, collections

OPS = r"D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{OPS}?mode=ro", uri=True)

SQL = "SELECT evaluation_id, scope, horizon_days, status, created_at, metrics_json FROM forecast_evaluations"
print("SQL:", SQL)
rows = c.execute(SQL).fetchall()

def h(obj):
    s = json.dumps(obj, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":"), default=str)
    return "forecast-eval-" + hashlib.sha256(s.encode("utf-8")).hexdigest()[:24]

res = collections.Counter()
per_status = collections.defaultdict(collections.Counter)
for evid, scope, hz, status, created, mj in rows:
    o = json.loads(mj)
    metrics = o["metrics"]
    # A) CURRENT code shape: includes canonical_policy_version key (None for legacy)
    cur = h({"scope": scope, "horizon_days": int(hz), "metrics": metrics,
             "canonical_policy_version": None})
    # B) LEGACY shape: no policy key at all
    leg = h({"scope": scope, "horizon_days": int(hz), "metrics": metrics})
    if evid == cur and evid == leg:
        tag = "AMBIGUOUS_both_match"
    elif evid == cur:
        tag = "matches_CURRENT_shape(policy_key_present,None)"
    elif evid == leg:
        tag = "matches_LEGACY_shape(no_policy_key)"
    else:
        tag = "matches_NEITHER"
    res[tag] += 1
    per_status[status][tag] += 1

print("\nQ12  Recompute evaluation_id from stored metrics_json under both code shapes")
print("     hash = 'forecast-eval-' + sha256(json.dumps(obj,sort_keys,separators))[:24]")
for k, v in res.most_common():
    print(f"   {v:4d}/746  {k}")
print("\n   by status:")
for st in sorted(per_status):
    print(f"   {st:20s} {dict(per_status[st])}")

# how many pooled decision snapshots share a vintage -> duplicate pooling harm
print("\nQ13  Duplicate-snapshot pooling: do 'ready' evaluations pool >1 decision_id")
print("     per (scope, data_version)?  -- this is the harm the canonical policy fixes")
SQLD = ("SELECT decision_id, scope, data_version, COUNT(*) FROM forecast_decisions "
        "GROUP BY decision_id, scope, data_version")
print("     SQL:", SQLD)
dmeta = {}
for did, scope, dv, n in c.execute(SQLD):
    dmeta[did] = (scope, dv, n)

SQLE = "SELECT status, scope, fold_count, sample_count, metrics_json FROM forecast_evaluations WHERE status='ready'"
print("     SQL:", SQLE)
multi = single = 0
vint_dup = collections.Counter()
for status, scope, fold, samp, mj in c.execute(SQLE):
    o = json.loads(mj)
    dids = [d.get("decision_id") for d in o["metrics"].get("by_decision", []) or []]
    byv = collections.Counter()
    for d in dids:
        m = dmeta.get(d)
        if m:
            byv[(m[0], m[1])] += 1
    worst = max(byv.values()) if byv else 0
    vint_dup[worst] += 1
    if worst > 1:
        multi += 1
    else:
        single += 1
print(f"   ready evaluations pooling >1 decision snapshot for the SAME (scope,data_version): {multi}/113")
print(f"   ready evaluations with at most 1 snapshot per vintage                           : {single}/113")
print(f"   distribution of max snapshots-per-vintage: {dict(sorted(vint_dup.items()))}")

# decision row inflation per decision_id
print("\nQ14  Row inflation behind those 155 decision ids")
SQLI = ("SELECT COUNT(*) rows, COUNT(DISTINCT decision_id) dids, "
        "COUNT(DISTINCT data_version) dvs FROM forecast_decisions")
print("     SQL:", SQLI)
print("   ", c.execute(SQLI).fetchone())
SQLI2 = ("SELECT scope, data_version, COUNT(DISTINCT decision_id) snaps FROM forecast_decisions "
         "GROUP BY scope, data_version HAVING snaps > 1 ORDER BY snaps DESC LIMIT 8")
print("     SQL:", SQLI2)
for r in c.execute(SQLI2):
    print("   ", r)
SQLI3 = ("SELECT COUNT(*) FROM (SELECT scope, data_version, COUNT(DISTINCT decision_id) s "
         "FROM forecast_decisions GROUP BY scope, data_version HAVING s > 1)")
print("     SQL:", SQLI3)
print("    vintages with >1 snapshot:", c.execute(SQLI3).fetchone()[0])

print("\nQ15  forecast_decision_days content (the claim table canonical.py reads)")
SQLDD = "SELECT * FROM forecast_decision_days"
print("     SQL:", SQLDD)
for r in c.execute(SQLDD):
    print("   ", r)
c.close()
