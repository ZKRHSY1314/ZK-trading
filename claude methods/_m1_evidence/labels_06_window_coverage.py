import sqlite3

WIN0, WIN1 = "2023-09-04", "2026-09-04"

mh = sqlite3.connect(r"file:D:\codex-A股交易\market_history.sqlite3?mode=ro", uri=True)
mh.row_factory = sqlite3.Row
row = mh.execute(
    "SELECT COUNT(DISTINCT trade_date) AS sessions, MIN(trade_date) AS first_date, "
    "MAX(trade_date) AS last_date FROM daily_bars WHERE trade_date BETWEEN ? AND ?",
    (WIN0, WIN1),
).fetchone()
print("## W1 trading sessions present in market_history.daily_bars inside the research window")
print("SQL: SELECT COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date) FROM daily_bars "
      f"WHERE trade_date BETWEEN '{WIN0}' AND '{WIN1}'")
print("   " + str(dict(row)))
mh.close()

tl = sqlite3.connect(r"file:D:\codex-A股交易\trading_local.sqlite3?mode=ro", uri=True)
tl.row_factory = sqlite3.Row
print("\n## W2 forecast ledger coverage inside the same window")
for sql, label in (
    ("SELECT COUNT(DISTINCT substr(decision_cutoff,1,10)) AS decision_dates, "
     "MIN(substr(decision_cutoff,1,10)) AS first_date, MAX(substr(decision_cutoff,1,10)) AS last_date "
     f"FROM forecast_decisions WHERE substr(decision_cutoff,1,10) BETWEEN '{WIN0}' AND '{WIN1}'",
     "all scopes"),
    ("SELECT scope, COUNT(DISTINCT substr(decision_cutoff,1,10)) AS decision_dates, "
     "COUNT(DISTINCT data_version) AS vintages, COUNT(DISTINCT decision_id) AS snapshots "
     f"FROM forecast_decisions WHERE substr(decision_cutoff,1,10) BETWEEN '{WIN0}' AND '{WIN1}' GROUP BY scope",
     "by scope"),
):
    print("   [" + label + "] SQL: " + " ".join(sql.split()))
    for r in tl.execute(sql):
        print("      " + str(dict(r)))

print("\n## W3 forecast rows dated OUTSIDE the research window")
print("SQL: SELECT COUNT(*) FROM forecast_decisions WHERE substr(decision_cutoff,1,10) NOT BETWEEN "
      f"'{WIN0}' AND '{WIN1}'")
print("   " + str(tl.execute(
    "SELECT COUNT(*) AS rows FROM forecast_decisions WHERE substr(decision_cutoff,1,10) "
    f"NOT BETWEEN '{WIN0}' AND '{WIN1}'").fetchone()["rows"]))

print("\n## W4 forecast_outcomes observed_at inside the window")
print("SQL: SELECT COUNT(DISTINCT substr(observed_at,1,10)) FROM forecast_outcomes WHERE "
      f"substr(observed_at,1,10) BETWEEN '{WIN0}' AND '{WIN1}'")
print("   " + str(dict(tl.execute(
    "SELECT COUNT(*) AS rows, COUNT(DISTINCT substr(observed_at,1,10)) AS observed_dates "
    f"FROM forecast_outcomes WHERE substr(observed_at,1,10) BETWEEN '{WIN0}' AND '{WIN1}'").fetchone())))
tl.close()
