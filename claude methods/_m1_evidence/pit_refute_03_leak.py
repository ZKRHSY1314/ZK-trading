import sqlite3
OP=r"D:/codex-A股交易/trading_local.sqlite3"
c=sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
q=lambda s,*a: c.execute(s,a).fetchall()
def one(l,s,*a):
    v=c.execute(s,a).fetchone(); print(f"{l:70s} {v}"); return v

print("### H. TIMESTAMP FORMAT COLLISION (the comparison they rely on) ###")
print("H1 decision_cutoff sample:", q("SELECT DISTINCT decision_cutoff FROM forecast_decisions LIMIT 3"))
print("H2 bar updated_at distinct formats (sep char at pos 11):")
for r in q("SELECT substr(updated_at,11,1) sep, COUNT(*) FROM daily_bar_cache GROUP BY sep"):
    print("   ",r)
for r in q("SELECT substr(created_at,11,1) sep, COUNT(*) FROM daily_bar_cache GROUP BY sep"):
    print("    created sep:",r)
one("H3 bars where created/updated identical except separator (phantom 'update')",
    "SELECT COUNT(*) FROM daily_bar_cache WHERE replace(created_at,' ','T')=replace(updated_at,' ','T')")

print("\n### I. MY OWN LEAKAGE PROBE — stock scope, pair level ###")
# cutoff date only (day granularity) to avoid tz/format skew
BASE = """
FROM (SELECT DISTINCT decision_id, subject, substr(decision_cutoff,1,10) cd
      FROM forecast_decisions WHERE scope='stock') d
"""
one("I0 total stock (decision_id,subject) pairs", "SELECT COUNT(*) "+BASE)

one("I1 pairs with >=1 bar trade_date<=cutoff_day whose updated_at DAY > cutoff_day  [their metric]",
 "SELECT COUNT(*) "+BASE+"""
 WHERE EXISTS (SELECT 1 FROM daily_bar_cache b
   WHERE b.symbol=d.subject AND b.trade_date<=d.cd
     AND substr(b.updated_at,1,10) > d.cd)""")

one("I2 ... AND bar already existed at cutoff (created_at day <= cutoff) = TRUE restatement",
 "SELECT COUNT(*) "+BASE+"""
 WHERE EXISTS (SELECT 1 FROM daily_bar_cache b
   WHERE b.symbol=d.subject AND b.trade_date<=d.cd
     AND substr(b.updated_at,1,10) > d.cd
     AND substr(b.created_at,1,10) <= d.cd)""")

one("I3 ... AND bar was CREATED after cutoff = bar absent at decision time (different defect)",
 "SELECT COUNT(*) "+BASE+"""
 WHERE EXISTS (SELECT 1 FROM daily_bar_cache b
   WHERE b.symbol=d.subject AND b.trade_date<=d.cd
     AND substr(b.created_at,1,10) > d.cd)""")

one("I4 pairs with ZERO pre-cutoff bars at all (no data to leak)",
 "SELECT COUNT(*) "+BASE+"""
 WHERE NOT EXISTS (SELECT 1 FROM daily_bar_cache b WHERE b.symbol=d.subject AND b.trade_date<=d.cd)""")

print("\n### J. WHY ARE 27% 'CLEAN'? breakdown by cutoff day ###")
for r in q("""
SELECT d.cd,
       COUNT(*) pairs,
       SUM(CASE WHEN EXISTS (SELECT 1 FROM daily_bar_cache b
             WHERE b.symbol=d.subject AND b.trade_date<=d.cd
               AND substr(b.updated_at,1,10) > d.cd) THEN 1 ELSE 0 END) affected
FROM (SELECT DISTINCT decision_id, subject, substr(decision_cutoff,1,10) cd
      FROM forecast_decisions WHERE scope='stock') d
GROUP BY d.cd ORDER BY d.cd"""):
    print("   ", r, f"{(r[2]/r[1]*100):.1f}%")

print("\n### K. SAME PROBE AT DECISION-ROW LEVEL (the unit the headline implies) ###")
one("K1 stock decision ROWS total", "SELECT COUNT(*) FROM forecast_decisions WHERE scope='stock'")
one("K2 stock decision ROWS affected",
 """SELECT COUNT(*) FROM forecast_decisions f WHERE f.scope='stock'
    AND EXISTS (SELECT 1 FROM daily_bar_cache b
      WHERE b.symbol=f.subject AND b.trade_date<=substr(f.decision_cutoff,1,10)
        AND substr(b.updated_at,1,10) > substr(f.decision_cutoff,1,10))""")
one("K3 ALL decision ROWS total (incl sector/system)", "SELECT COUNT(*) FROM forecast_decisions")
c.close()
