import sqlite3, json, collections

OPS = r"D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{OPS}?mode=ro", uri=True)

SQL = ("SELECT id, evaluation_id, status, scope, horizon_days, created_at, metrics_json "
       "FROM forecast_evaluations")
print("SQL:", SQL)
rows = c.execute(SQL).fetchall()

empty = 0
per_eval = {}
all_dids = set()
for eid, evid, status, scope, hz, created, mj in rows:
    o = json.loads(mj)
    dids = [d.get("decision_id") for d in o.get("metrics", {}).get("by_decision", []) or []]
    dids = [d for d in dids if d]
    per_eval[eid] = (status, scope, hz, created, dids)
    all_dids.update(dids)
    if not dids:
        empty += 1

print(f"\nQ7  by_decision decision_id extraction")
print(f"   evaluations with ZERO decision_ids in payload : {empty}/746")
print(f"   evaluations with >=1 decision_id              : {746-empty}/746")
print(f"   distinct decision_ids referenced              : {len(all_dids)}")

# split by status
for st in ("ready", "insufficient_data"):
    tot = sum(1 for v in per_eval.values() if v[0] == st)
    withd = sum(1 for v in per_eval.values() if v[0] == st and v[4])
    print(f"   status={st:18s} total={tot:4d}  with decision_ids={withd}")

# ---- do those decision_ids resolve in forecast_decisions? ----
print("\nQ8  Do the referenced decision_ids resolve in forecast_decisions?")
lst = sorted(all_dids)
found = set()
CH = 500
for i in range(0, len(lst), CH):
    ch = lst[i:i+CH]
    q = ("SELECT DISTINCT decision_id FROM forecast_decisions WHERE decision_id IN (%s)"
         % ",".join("?"*len(ch)))
    found.update(r[0] for r in c.execute(q, ch))
print("   SQL: SELECT DISTINCT decision_id FROM forecast_decisions WHERE decision_id IN (<batch>)")
print(f"   referenced={len(all_dids)}  resolved={len(found)}  unresolved={len(all_dids)-len(found)}")

# ---- what provenance does the join recover? ----
print("\nQ9  Provenance recovered via join (model_version/prompt_version/data_version)")
prov = {}
for i in range(0, len(lst), CH):
    ch = lst[i:i+CH]
    q = ("SELECT decision_id, model_version, prompt_version, data_version, MIN(created_at) "
         "FROM forecast_decisions WHERE decision_id IN (%s) "
         "GROUP BY decision_id, model_version, prompt_version, data_version"
         % ",".join("?"*len(ch)))
    for did, mv, pv, dv, ca in c.execute(q, ch):
        prov.setdefault(did, []).append((mv, pv, dv, ca))
print("   SQL: SELECT decision_id, model_version, prompt_version, data_version, MIN(created_at)")
print("        FROM forecast_decisions WHERE decision_id IN (<batch>) GROUP BY 1,2,3,4")

mv_c, pv_c, dv_c = collections.Counter(), collections.Counter(), collections.Counter()
for v in prov.values():
    for mv, pv, dv, _ in v:
        mv_c[mv] += 1; pv_c[pv] += 1; dv_c[dv] += 1
print("   model_version distribution :", dict(mv_c))
print("   prompt_version distribution:", dict(pv_c))
print("   data_version distinct count:", len(dv_c), "sample:", list(dv_c)[:4])

# ---- coverage: how many of the 746 evals get FULL provenance ----
full = part = none = 0
ready_full = 0
for eid, (status, scope, hz, created, dids) in per_eval.items():
    if not dids:
        none += 1; continue
    res = sum(1 for d in dids if d in prov)
    if res == len(dids):
        full += 1
        if status == "ready":
            ready_full += 1
    elif res:
        part += 1
    else:
        none += 1
print(f"\nQ10 Evaluations whose FULL decision set resolves to provenance rows: {full}/746")
print(f"    partial: {part}   none/no-ids: {none}")
print(f"    of the 113 'ready' rows, fully resolvable: {ready_full}/113")

# ---- can we distinguish the 2026-09-04 batch by joined provenance? ----
print("\nQ11 Joined model/prompt/data version by evaluation created_at epoch")
ep = collections.defaultdict(lambda: [collections.Counter(), collections.Counter()])
for eid, (status, scope, hz, created, dids) in per_eval.items():
    e = "2026-09-04" if created.startswith("2026-09-04") else "2026-07-xx"
    for d in dids:
        for mv, pv, dv, _ in prov.get(d, []):
            ep[e][0][mv] += 1
            ep[e][1][pv] += 1
for e in sorted(ep):
    print(f"   {e}: model_version={dict(ep[e][0])}  prompt_version={dict(ep[e][1])}")
c.close()
