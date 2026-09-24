import sqlite3, sys, time
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8')
TL = r"D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True); c.row_factory = sqlite3.Row

def norm(ts):
    # 'YYYY-MM-DDTHH:MM:SS.ffffffZ' or 'YYYY-MM-DD HH:MM:SS' -> comparable 'YYYY-MM-DD HH:MM:SS'
    if ts is None: return None
    s = str(ts).replace('T',' ').replace('Z','').strip()
    if '+' in s: s = s.split('+')[0]
    return s[:19]

print("### F0 SQL used to pull decisions")
DEC_SQL = ("SELECT DISTINCT decision_id, subject, decision_cutoff FROM forecast_decisions "
           "WHERE scope='stock'")
print(DEC_SQL)
dec = c.execute(DEC_SQL).fetchall()
print("distinct (decision_id,subject,cutoff) triples:", len(dec))
symbols = sorted({r["subject"] for r in dec})
print("distinct subjects:", len(symbols))

print("\n### F1 SQL used to pull bars for those subjects")
ph = ",".join("?"*len(symbols))
BAR_SQL = (f"SELECT symbol, trade_date, created_at, updated_at, source FROM daily_bar_cache "
           f"WHERE symbol IN ({ph}) AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'")
print(BAR_SQL.replace(ph, "<105 subject placeholders>"))
t=time.time()
bars = defaultdict(list)
n=0
for r in c.execute(BAR_SQL, symbols):
    bars[r["symbol"]].append((r["trade_date"], norm(r["created_at"]), norm(r["updated_at"])))
    n+=1
for s in bars: bars[s].sort()
print(f"bars pulled: {n} for {len(bars)} symbols [{time.time()-t:.1f}s]")

A=B=C=0; A_rows=B_rows=C_rows=0; total=0; nobars=0
exA=[]; exB=[]; exC=[]
maxlag_examples=[]
for r in dec:
    total+=1
    sub=r["subject"]; cut=norm(r["decision_cutoff"]); cutd=cut[:10]
    bl = bars.get(sub)
    if not bl:
        nobars+=1; continue
    a=b=cc=0
    for td, cr, up in bl:
        if td <= cutd:
            if cr > cut:
                a+=1
                if len(exA)<8: exA.append((r["decision_id"],sub,r["decision_cutoff"],td,cr))
            elif up and up > cut:
                cc+=1
                if len(exC)<8: exC.append((r["decision_id"],sub,r["decision_cutoff"],td,cr,up))
        else:  # trade_date AFTER the decision cutoff date
            if cr <= cut:
                b+=1
                if len(exB)<8: exB.append((r["decision_id"],sub,r["decision_cutoff"],td,cr))
    if a: A+=1; A_rows+=a
    if b: B+=1; B_rows+=b
    if cc: C+=1; C_rows+=cc

print("\n### F2 LEAKAGE PROBE RESULTS (scope='stock' decisions vs daily_bar_cache)")
print(f"decision x subject pairs examined         : {total}")
print(f"pairs whose subject has NO bars at all    : {nobars}")
print(f"A) pairs where >=1 bar with trade_date<=cutoff_date was CREATED AFTER the cutoff : {A}  ({A_rows} bar-rows)")
print(f"B) pairs where >=1 bar with trade_date> cutoff_date already existed at cutoff    : {B}  ({B_rows} bar-rows)")
print(f"C) pairs where >=1 pre-cutoff bar was UPDATED (restated) after the cutoff        : {C}  ({C_rows} bar-rows)")
print("\nExamples A (bar not yet in DB at decision time -> replay today would use it):")
for e in exA: print("   ", e)
print("Examples B (future-dated bar already in DB at decision time -> look-ahead reachable):")
for e in exB: print("   ", e)
print("Examples C (bar value restated after the decision -> decision not reproducible):")
for e in exC: print("   ", e)

print("\n### F3 forecast_outcomes: when written vs when observable")
for r in c.execute("SELECT horizon_days, COUNT(*) n, MIN(observed_at) min_obs, MAX(observed_at) max_obs, MIN(created_at) min_created, MAX(created_at) max_created FROM forecast_outcomes GROUP BY horizon_days"):
    print("   ", tuple(r))
print("SQL: SELECT horizon_days, COUNT(*) n, MIN(observed_at), MAX(observed_at), MIN(created_at), MAX(created_at) FROM forecast_outcomes GROUP BY horizon_days")

print("\n### F4 outcomes whose row was WRITTEN BEFORE the outcome date it claims to observe")
sql=("SELECT COUNT(*) FROM forecast_outcomes "
     "WHERE replace(replace(substr(created_at,1,19),'T',' '),'Z','') < replace(replace(substr(observed_at,1,19),'T',' '),'Z','')")
print("SQL:", sql); print("   ", c.execute(sql).fetchone()[0])
sql2=("SELECT decision_id, subject, horizon_days, observed_at, created_at FROM forecast_outcomes "
      "WHERE replace(replace(substr(created_at,1,19),'T',' '),'Z','') < replace(replace(substr(observed_at,1,19),'T',' '),'Z','') "
      "ORDER BY horizon_days DESC LIMIT 10")
for r in c.execute(sql2): print("   ", tuple(r))

print("\n### F5 outcome maturation lag: observed_at minus decision_cutoff, per horizon")
sql3=("""SELECT o.horizon_days,
   COUNT(*) n,
   MIN(CAST(julianday(substr(o.observed_at,1,10)) - julianday(substr(d.decision_cutoff,1,10)) AS INT)) min_cal_days,
   MAX(CAST(julianday(substr(o.observed_at,1,10)) - julianday(substr(d.decision_cutoff,1,10)) AS INT)) max_cal_days
 FROM forecast_outcomes o JOIN forecast_decisions d
   ON d.decision_id=o.decision_id AND d.scope=o.scope AND d.subject=o.subject AND d.horizon_days=o.horizon_days
 GROUP BY o.horizon_days""")
print("SQL:", " ".join(sql3.split()))
for r in c.execute(sql3): print("   ", tuple(r))
c.close()
