import sqlite3, sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
MH = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{MH}?mode=ro", uri=True); c.row_factory=sqlite3.Row

print("### B0 ingest_runs count")
print(c.execute("SELECT COUNT(*) FROM ingest_runs").fetchone()[0])

print("\n### B1 ingest_runs grouped by dataset/provider/status/day")
sql=("SELECT dataset_name, provider, adjustment_mode, status, substr(requested_at,1,10) day, COUNT(*) runs, "
     "SUM(requested_symbol_count) req_syms, SUM(processed_symbol_count) proc_syms, SUM(inserted_row_count) ins, "
     "SUM(updated_row_count) upd, SUM(rejected_row_count) rej, MIN(started_at) first_start, MAX(completed_at) last_done "
     "FROM ingest_runs GROUP BY dataset_name, provider, adjustment_mode, status, day ORDER BY day, dataset_name")
print("SQL:", sql)
for r in c.execute(sql):
    print("   ", tuple(r))

print("\n### B2 ALL 100 ingest_runs, key fields")
sql2=("SELECT id, dataset_name, provider, adjustment_mode, status, requested_at, started_at, completed_at, "
      "requested_symbol_count, processed_symbol_count, inserted_row_count, updated_row_count, rejected_row_count, "
      "research_only, live_trading_enabled FROM ingest_runs ORDER BY id")
print("SQL:", sql2)
for r in c.execute(sql2):
    print("   ", tuple(r))

print("\n### B3 distinct parameters_json shapes (keys only) + a few samples")
seen={}
for (p,) in c.execute("SELECT parameters_json FROM ingest_runs"):
    try: k=tuple(sorted(json.loads(p).keys()))
    except Exception: k=("<unparseable>",)
    seen.setdefault(k,[0,p]); seen[k][0]+=1
for k,(n,sample) in seen.items():
    print("   keys=",k," count=",n)
    print("     sample:", sample[:700])

print("\n### B4 non-empty error_json")
for r in c.execute("SELECT id, status, error_json FROM ingest_runs WHERE error_json <> '{}'"):
    print("   ", r[0], r[1], r[2][:400])

print("\n### B5 schema_metadata")
for r in c.execute("SELECT * FROM schema_metadata"):
    print("   ", tuple(r))

print("\n### B6 universe_snapshots (all 12)")
for r in c.execute("SELECT id, universe_name, snapshot_date, provider, fetched_at, member_count, substr(metadata_json,1,200), created_at FROM universe_snapshots ORDER BY snapshot_date"):
    print("   ", tuple(r))

print("\n### B7 instruments fetched_at range (listing-history vintage)")
for r in c.execute("SELECT provider, substr(fetched_at,1,10) d, COUNT(*) n, SUM(list_date IS NOT NULL) with_list, SUM(delist_date IS NOT NULL) with_delist FROM instruments GROUP BY provider, d ORDER BY d"):
    print("   ", tuple(r))
c.close()
