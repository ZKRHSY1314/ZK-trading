import sqlite3, json, collections
OP = r"D:/codex-A股交易/trading_local.sqlite3"
con = sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
cur = con.cursor()
def q(sql, args=()):
    return cur.execute(sql, args).fetchall()

print("### A. Does forecast_decision_days have run_kind?")
print([r["name"] for r in q("PRAGMA table_info(forecast_decision_days)")])
print("row:", [dict(r) for r in q("SELECT * FROM forecast_decision_days")])

print()
print("### B. Ledger cardinality (my own SQL)")
r = q("""SELECT COUNT(*) rows_total,
                COUNT(DISTINCT decision_id) distinct_decision_ids,
                COUNT(DISTINCT scope||'|'||data_version) distinct_scope_vintages,
                COUNT(DISTINCT data_version) distinct_data_versions
         FROM forecast_decisions""")[0]
print(dict(r))

print()
print("### C. per scope")
for r in q("""SELECT scope, COUNT(*) rows, COUNT(DISTINCT decision_id) dids,
                     COUNT(DISTINCT data_version) vintages,
                     COUNT(DISTINCT subject) subjects
              FROM forecast_decisions GROUP BY scope ORDER BY scope"""):
    print(dict(r))

print()
print("### D. date/timestamp FORMATS -- string comparison hazard check")
for r in q("""SELECT 'decision_cutoff' col, MIN(decision_cutoff) lo, MAX(decision_cutoff) hi,
                     COUNT(DISTINCT length(decision_cutoff)) lens FROM forecast_decisions
              UNION ALL SELECT 'available_at', MIN(available_at), MAX(available_at),
                     COUNT(DISTINCT length(available_at)) FROM forecast_decisions
              UNION ALL SELECT 'data_version', MIN(data_version), MAX(data_version),
                     COUNT(DISTINCT length(data_version)) FROM forecast_decisions
              UNION ALL SELECT 'eval.as_of', MIN(as_of), MAX(as_of),
                     COUNT(DISTINCT length(as_of)) FROM forecast_evaluations
              UNION ALL SELECT 'outcome.observed_at', MIN(observed_at), MAX(observed_at),
                     COUNT(DISTINCT length(observed_at)) FROM forecast_outcomes"""):
    print(dict(r))
print("distinct lengths decision_cutoff:", [dict(x) for x in q("SELECT length(decision_cutoff) L, COUNT(*) c FROM forecast_decisions GROUP BY 1")])
print("distinct lengths as_of:", [dict(x) for x in q("SELECT length(as_of) L, COUNT(*) c FROM forecast_evaluations GROUP BY 1")])

print()
print("### E. worst vintage: snapshots per (scope,data_version)")
for r in q("""SELECT scope, data_version,
                     COUNT(DISTINCT decision_id) snapshots,
                     COUNT(*) rows,
                     COUNT(DISTINCT subject) subjects,
                     MIN(decision_cutoff) first_cut, MAX(decision_cutoff) last_cut
              FROM forecast_decisions GROUP BY scope, data_version
              ORDER BY snapshots DESC LIMIT 12"""):
    print(dict(r))

print()
print("### F. evaluations: status distribution")
for r in q("SELECT status, scope, COUNT(*) c FROM forecast_evaluations GROUP BY status, scope ORDER BY status, scope"):
    print(dict(r))
print("TOTAL ready:", q("SELECT COUNT(*) c FROM forecast_evaluations WHERE status='ready'")[0]["c"])
print("ready by scope:", [dict(x) for x in q("SELECT scope, COUNT(*) c FROM forecast_evaluations WHERE status='ready' GROUP BY scope")])

print()
print("### G. the specific row they cite: stock h=1 as_of 2026-09-04T04:43:08Z")
for r in q("""SELECT evaluation_id, as_of, scope, horizon_days, status, sample_count, fold_count, coverage
              FROM forecast_evaluations
              WHERE scope='stock' AND horizon_days=1 AND as_of='2026-09-04T04:43:08Z'"""):
    print(dict(r))
print(" -- any as_of LIKE 2026-09-04T04:43% :")
for r in q("""SELECT evaluation_id, as_of, scope, horizon_days, status, sample_count, fold_count
              FROM forecast_evaluations WHERE as_of LIKE '2026-09-04T04:43%' ORDER BY scope, horizon_days"""):
    print(dict(r))

print()
print("### H. duplicate (sample_count, fold_count) signatures for ready rows")
for r in q("""SELECT scope, horizon_days, sample_count, fold_count, COUNT(*) n_rows,
                     MIN(as_of) first_as_of, MAX(as_of) last_as_of
              FROM forecast_evaluations WHERE status='ready'
              GROUP BY scope, horizon_days, sample_count, fold_count
              ORDER BY n_rows DESC, scope, horizon_days LIMIT 30"""):
    print(dict(r))
print(" -- collapsed across horizons (their '45 rows / 9 per horizon' claim):")
for r in q("""SELECT sample_count, fold_count, COUNT(*) n_rows, COUNT(DISTINCT horizon_days) horizons,
                     COUNT(DISTINCT as_of) distinct_as_of
              FROM forecast_evaluations WHERE status='ready' AND scope='stock'
              GROUP BY sample_count, fold_count ORDER BY n_rows DESC LIMIT 15"""):
    print(dict(r))
con.close()
