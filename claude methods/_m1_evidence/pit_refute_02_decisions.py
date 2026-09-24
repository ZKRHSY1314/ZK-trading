import sqlite3
OP=r"D:/codex-A股交易/trading_local.sqlite3"
c=sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
q=lambda s,*a: c.execute(s,a).fetchall()
def one(l,s,*a):
    v=c.execute(s,a).fetchone(); print(f"{l:64s} {v}"); return v

print("### E. forecast_decisions SHAPE — WHERE DOES 3,900 COME FROM? ###")
one("E1 total decision rows", "SELECT COUNT(*) FROM forecast_decisions")
print("E2 by scope:")
for r in q("SELECT scope, COUNT(*) rows, COUNT(DISTINCT subject) subj, COUNT(DISTINCT decision_id) did FROM forecast_decisions GROUP BY scope"):
    print("   ",r)
one("E3 distinct (decision_id,subject)", "SELECT COUNT(*) FROM (SELECT DISTINCT decision_id,subject FROM forecast_decisions)")
one("E4 distinct (decision_id,subject) scope=stock", "SELECT COUNT(*) FROM (SELECT DISTINCT decision_id,subject FROM forecast_decisions WHERE scope='stock')")
one("E5 distinct (decision_cutoff,subject)", "SELECT COUNT(*) FROM (SELECT DISTINCT decision_cutoff,subject FROM forecast_decisions)")
one("E6 distinct (decision_cutoff,subject) scope=stock", "SELECT COUNT(*) FROM (SELECT DISTINCT decision_cutoff,subject FROM forecast_decisions WHERE scope='stock')")
one("E7 distinct decision_id", "SELECT COUNT(DISTINCT decision_id) FROM forecast_decisions")
one("E8 distinct decision_cutoff", "SELECT COUNT(DISTINCT decision_cutoff) FROM forecast_decisions")
one("E9 min/max decision_cutoff", "SELECT MIN(decision_cutoff),MAX(decision_cutoff) FROM forecast_decisions")
one("E10 min/max created_at", "SELECT MIN(created_at),MAX(created_at) FROM forecast_decisions")

print("\n### F. WHEN WERE DECISIONS ACTUALLY WRITTEN vs THE 2026-09-03 REWRITE? ###")
print("F1 decision rows by created_at DAY:")
for r in q("SELECT substr(created_at,1,10) d, COUNT(*) n, MIN(decision_cutoff), MAX(decision_cutoff) FROM forecast_decisions GROUP BY d ORDER BY d"):
    print("   ",r)
one("F2 rows whose created_at day >= 2026-09-03 (bars already restated BEFORE decision)",
    "SELECT COUNT(*) FROM forecast_decisions WHERE substr(created_at,1,10) >= '2026-09-03'")
one("F3 rows whose created_at day < 2026-09-03",
    "SELECT COUNT(*) FROM forecast_decisions WHERE substr(created_at,1,10) < '2026-09-03'")

print("\n### G. SUBJECT -> SYMBOL JOINABILITY (does subject even match daily_bar_cache.symbol?) ###")
print("G1 sample stock subjects:", [r[0] for r in q("SELECT DISTINCT subject FROM forecast_decisions WHERE scope='stock' LIMIT 12")])
print("G2 sample sector subjects:", [r[0] for r in q("SELECT DISTINCT subject FROM forecast_decisions WHERE scope='sector' LIMIT 8")])
one("G3 stock subjects that EXIST in daily_bar_cache.symbol",
    "SELECT COUNT(*) FROM (SELECT DISTINCT subject s FROM forecast_decisions WHERE scope='stock') WHERE s IN (SELECT DISTINCT symbol FROM daily_bar_cache)")
one("G4 distinct stock subjects total", "SELECT COUNT(DISTINCT subject) FROM forecast_decisions WHERE scope='stock'")
c.close()
