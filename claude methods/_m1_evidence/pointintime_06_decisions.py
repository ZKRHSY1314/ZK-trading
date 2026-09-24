import sqlite3, sys, time
sys.stdout.reconfigure(encoding='utf-8')
TL = r"D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
def q(sql, params=(), label=None, lim=200):
    t=time.time(); rows=c.execute(sql,params).fetchall()
    print(f"\n### {label}"); print("SQL:", " ".join(sql.split()))
    for r in rows[:lim]: print("   ", r)
    if len(rows)>lim: print(f"    ...({len(rows)} rows)")
    print(f"    [{time.time()-t:.1f}s]"); return rows

q("SELECT COUNT(*) n, COUNT(DISTINCT decision_id) dids, COUNT(DISTINCT subject) subs, MIN(decision_cutoff), MAX(decision_cutoff) FROM forecast_decisions", label="E1 forecast_decisions totals")
q("SELECT scope, COUNT(*) n, COUNT(DISTINCT decision_id) dids, COUNT(DISTINCT decision_cutoff) cutoffs, MIN(decision_cutoff), MAX(decision_cutoff) FROM forecast_decisions GROUP BY scope", label="E2 by scope")
q("SELECT decision_cutoff, COUNT(*) n, COUNT(DISTINCT subject) subs, COUNT(DISTINCT decision_id) dids, MIN(created_at) first_row_created, MAX(created_at) last_row_created FROM forecast_decisions GROUP BY decision_cutoff ORDER BY decision_cutoff", label="E3 every distinct decision_cutoff (the true decision calendar)")
q("SELECT COUNT(*) FROM forecast_decisions WHERE available_at <> decision_cutoff", label="E4 decisions where available_at differs from decision_cutoff")
q("SELECT data_version, COUNT(*) n, MIN(decision_cutoff), MAX(decision_cutoff) FROM forecast_decisions GROUP BY data_version ORDER BY MIN(decision_cutoff)", label="E5 data_version")
q("SELECT model_version, COUNT(*) FROM forecast_decisions GROUP BY model_version", label="E6 model_version")
q("SELECT status, COUNT(*) FROM forecast_decisions GROUP BY status", label="E7 status")
q("SELECT MIN(observed_at), MAX(observed_at), COUNT(*) FROM forecast_outcomes", label="E8 outcomes observed_at range")
q("SELECT horizon_days, COUNT(*) n, MIN(observed_at), MAX(observed_at) FROM forecast_outcomes GROUP BY horizon_days", label="E9 outcomes by horizon")
q("SELECT COUNT(*) FROM forecast_decisions d LEFT JOIN forecast_outcomes o USING(decision_id,scope,subject,horizon_days) WHERE o.id IS NULL", label="E10 decisions with NO matured outcome")
q("SELECT substr(created_at,1,10) d, COUNT(*) FROM forecast_decisions GROUP BY d ORDER BY d", label="E11 when decision rows were physically written")
c.close()
