import sqlite3

DB = r"D:\codex-A股交易\trading_local.sqlite3"
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row


def show(title, sql):
    print("\n## " + title)
    print("SQL: " + " ".join(sql.split()))
    rows = con.execute(sql).fetchall()
    if not rows:
        print("   (no rows)")
        return
    print("   " + " | ".join(str(k) for k in rows[0].keys()))
    for r in rows:
        print("   " + " | ".join(str(r[k]) for k in r.keys()))


show(
    "F1 available_at vs decision_cutoff (is there any point-in-time lag recorded?)",
    "SELECT COUNT(*) AS rows, SUM(CASE WHEN available_at = decision_cutoff THEN 1 ELSE 0 END) AS equal_rows, "
    "SUM(CASE WHEN available_at <> decision_cutoff THEN 1 ELSE 0 END) AS differing_rows FROM forecast_decisions",
)
show(
    "F2 ready evaluations by scope",
    "SELECT scope, COUNT(*) AS ready_rows FROM forecast_evaluations WHERE status='ready' GROUP BY scope",
)
show(
    "F3 evaluations whose stored metrics claim a positive Rank IC",
    "SELECT scope, horizon_days, COUNT(*) AS rows, MIN(spearman_rank_ic) AS min_ic, MAX(spearman_rank_ic) AS max_ic "
    "FROM forecast_evaluations WHERE status='ready' AND spearman_rank_ic > 0 GROUP BY scope, horizon_days",
)
show(
    "F4 brier_score / probability coverage in the evaluations",
    "SELECT COUNT(*) AS rows, COUNT(brier_score) AS non_null_brier, COUNT(precision_at_k) AS non_null_precision, "
    "COUNT(spearman_rank_ic) AS non_null_rank_ic FROM forecast_evaluations",
)
show(
    "F5 subjects per scope in the ledger (are these stocks or indices?)",
    "SELECT scope, COUNT(DISTINCT subject) AS subjects, MIN(subject) AS min_subject, MAX(subject) AS max_subject "
    "FROM forecast_decisions GROUP BY scope",
)
show(
    "F6 the 20 stock subjects most often decided",
    "SELECT subject, COUNT(DISTINCT decision_id) AS snapshots, COUNT(*) AS rows FROM forecast_decisions "
    "WHERE scope='stock' GROUP BY subject ORDER BY snapshots DESC LIMIT 10",
)
show(
    "F7 rank/score/probability nullability in forecast_decisions",
    "SELECT scope, COUNT(*) AS rows, COUNT(rank) AS non_null_rank, COUNT(score) AS non_null_score, "
    "COUNT(probability) AS non_null_probability FROM forecast_decisions GROUP BY scope",
)
show(
    "F8 forecast_decision_days: is there any evidence of a second claim ever existing?",
    "SELECT COUNT(*) AS claims, MIN(claimed_at) AS first_claim, MAX(claimed_at) AS last_claim "
    "FROM forecast_decision_days",
)
show(
    "F9 decision snapshots recorded on a date LATER than their bar vintage (stock)",
    "SELECT data_version AS bar_vintage, substr(decision_cutoff,1,10) AS recorded_date, "
    "COUNT(DISTINCT decision_id) AS snapshots FROM forecast_decisions WHERE scope='stock' "
    "GROUP BY bar_vintage, recorded_date ORDER BY bar_vintage, recorded_date",
)
con.close()
