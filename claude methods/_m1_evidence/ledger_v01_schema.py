import sqlite3
DB = r"D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
c.row_factory = sqlite3.Row
print("== PRAGMA table_info(forecast_decision_days) ==")
for r in c.execute("PRAGMA table_info(forecast_decision_days)"):
    print(dict(r))
print()
print("== sqlite_master DDL forecast_decision_days ==")
for r in c.execute("SELECT sql FROM sqlite_master WHERE name='forecast_decision_days'"):
    print(r[0])
print()
print("== ALL ROWS forecast_decision_days ==")
cols = [d[0] for d in c.execute("SELECT * FROM forecast_decision_days LIMIT 0").description]
print(cols)
for r in c.execute("SELECT * FROM forecast_decision_days"):
    print(tuple(r))
print()
print("== tables named forecast% / decision% ==")
for r in c.execute("SELECT name,type FROM sqlite_master WHERE name LIKE 'forecast%' OR name LIKE '%decision%' ORDER BY name"):
    print(tuple(r))
print()
for t in ("forecast_decisions","forecast_outcomes","forecast_evaluations","forecast_decision_days"):
    n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"{t}: {n}")
print()
print("== forecast_decisions columns ==")
print([d[1] for d in c.execute("PRAGMA table_info(forecast_decisions)")])
print("== forecast_outcomes columns ==")
print([d[1] for d in c.execute("PRAGMA table_info(forecast_outcomes)")])
