import sqlite3
OP = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
c = ro(OP); q=lambda s,*a: c.execute(s,a).fetchall()
def one(s,*a):
    r=c.execute(s,a).fetchone(); return r[0] if r else None

print("C. WRITE-EPOCH BUCKETS (my own grouping, normalising the T/space separator)")
rows = q("""
 SELECT substr(created_at,1,10) cd, substr(replace(updated_at,'T',' '),1,10) ud, COUNT(*) n,
        COUNT(DISTINCT symbol) nsym
 FROM daily_bar_cache
 WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
 GROUP BY 1,2 ORDER BY n DESC LIMIT 25""")
tot=0
for cd,ud,n,ns in rows:
    delta = (None)
    import datetime as dt
    d0=dt.date.fromisoformat(cd); d1=dt.date.fromisoformat(ud)
    delta=(d1-d0).days
    tot+=n
    print(f"   created {cd}  updated {ud}  delta={delta:>5}d  rows={n:>9,}  syms={ns:>6,}")
print(f"   (top-25 covers {tot:,})")
print()

print("D. RE-WRITE COUNT UNDER DIFFERENT (correct) COMPARISONS")
base = one("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'")
print("   base valid rows:", f"{base:,}")
naive = one("""SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
   AND updated_at IS NOT NULL AND substr(updated_at,1,10) <> substr(created_at,1,10)""")
print(f"   their naive day-string diff        : {naive:,}  ({naive/base*100:.2f}%)")
# created_at is UTC (CURRENT_TIMESTAMP); updated_at is local Asia/Shanghai (datetime.now()). Shift created_at +8h.
tzfix = one("""SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
   AND date(created_at,'+8 hours') <> date(replace(updated_at,'T',' '))""")
print(f"   tz-corrected (created_at +8h, UTC->CST): {tzfix:,}  ({tzfix/base*100:.2f}%)")
gt1h = one("""SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
   AND julianday(replace(updated_at,'T',' ')) - julianday(created_at,'+8 hours') > 1.0/24""")
print(f"   >1 hour after its own insert           : {gt1h:,}  ({gt1h/base*100:.2f}%)")
gt1d = one("""SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
   AND julianday(replace(updated_at,'T',' ')) - julianday(created_at,'+8 hours') > 1.0""")
print(f"   >24 hours after its own insert         : {gt1d:,}  ({gt1d/base*100:.2f}%)")
neg = one("""SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
   AND julianday(replace(updated_at,'T',' ')) < julianday(created_at,'+8 hours')""")
print(f"   updated_at BEFORE created_at (+8h)     : {neg:,}   <- clock/vintage incoherence")
print()

print("E. DID THE 2026-09-03 PASS CHANGE PROVENANCE FIELDS?")
for r in q("""SELECT substr(replace(updated_at,'T',' '),1,10) ud, source, adjustment_mode, volume_unit, quality_status, COUNT(*) n
              FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
              GROUP BY 1,2,3,4,5 ORDER BY n DESC LIMIT 20"""):
    print("   ", r)
print()
print("   source census overall:")
for r in q("SELECT source,adjustment_mode,COUNT(*) FROM daily_bar_cache GROUP BY 1,2 ORDER BY 3 DESC LIMIT 15"):
    print("   ", r)
print()

print("F. DECISION UNIVERSE — what is the real denominator?")
print("   forecast_decisions rows                :", one("SELECT COUNT(*) FROM forecast_decisions"))
print("   distinct decision_id                   :", one("SELECT COUNT(DISTINCT decision_id) FROM forecast_decisions"))
print("   distinct (decision_id,scope,subject)   :", one("SELECT COUNT(*) FROM (SELECT DISTINCT decision_id,scope,subject FROM forecast_decisions)"))
print("   distinct (decision_id,subject)         :", one("SELECT COUNT(*) FROM (SELECT DISTINCT decision_id,subject FROM forecast_decisions)"))
print("   scope census:")
for r in q("SELECT scope,COUNT(*) n,COUNT(DISTINCT subject) nsub,COUNT(DISTINCT decision_id) nid FROM forecast_decisions GROUP BY 1"):
    print("     ", r)
print("   decision_cutoff range:", q("SELECT MIN(decision_cutoff),MAX(decision_cutoff) FROM forecast_decisions"))
print("   available_at range   :", q("SELECT MIN(available_at),MAX(available_at) FROM forecast_decisions"))
print("   created_at range     :", q("SELECT MIN(created_at),MAX(created_at) FROM forecast_decisions"))
print("   distinct (cutoff,subject) stock-scope :", one("SELECT COUNT(*) FROM (SELECT DISTINCT decision_cutoff,subject FROM forecast_decisions WHERE scope='stock')"))
print("   distinct (cutoff,subject) all scopes  :", one("SELECT COUNT(*) FROM (SELECT DISTINCT decision_cutoff,subject FROM forecast_decisions)"))
print("   distinct (decision_id,subject) stock  :", one("SELECT COUNT(*) FROM (SELECT DISTINCT decision_id,subject FROM forecast_decisions WHERE scope='stock')"))
c.close()
