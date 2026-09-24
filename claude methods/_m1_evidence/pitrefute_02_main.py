# -*- coding: utf-8 -*-
import sqlite3, json, random
OP = r"D:\codex-A股交易\trading_local.sqlite3"
c = sqlite3.connect(f"file:{OP}?mode=ro", uri=True); cur=c.cursor()
q=lambda s,*a: cur.execute(s,a).fetchall()

# NORMALIZE: created_at 'YYYY-MM-DD HH:MM:SS' (UTC, sqlite CURRENT_TIMESTAMP)
#            decision_cutoff 'YYYY-MM-DDTHH:MM:SS.ffffffZ' (UTC)
# canonical key = 'YYYY-MM-DDTHH:MM:SS'
NORM_CA = "replace(substr(b.created_at,1,19),' ','T')"
NORM_CO = "substr(d.decision_cutoff,1,19)"

trip = q("SELECT DISTINCT decision_id, subject, decision_cutoff FROM forecast_decisions WHERE scope='stock'")
print("triples:", len(trip))

# ---- MY OWN QUERY: correlated, with FIXED normalization (theirs used raw string compare) ----
sql_pairs = f"""
SELECT COUNT(*) FROM (
  SELECT DISTINCT d.decision_id, d.subject
  FROM forecast_decisions d
  JOIN daily_bar_cache b ON b.symbol = d.subject
  WHERE d.scope='stock'
    AND b.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
    AND b.trade_date <= substr(d.decision_cutoff,1,10)
    AND {NORM_CA} > {NORM_CO}
)"""
print("\n=== 1. PAIRS with >=1 late-created bar, NORMALIZED compare ===")
print("  n_pairs:", q(sql_pairs)[0][0], "of 3900")

sql_pairs_raw = """
SELECT COUNT(*) FROM (
  SELECT DISTINCT d.decision_id, d.subject
  FROM forecast_decisions d JOIN daily_bar_cache b ON b.symbol=d.subject
  WHERE d.scope='stock' AND b.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
    AND b.trade_date <= substr(d.decision_cutoff,1,10)
    AND b.created_at > d.decision_cutoff
)"""
print("  n_pairs (their RAW string compare, reproduced):", q(sql_pairs_raw)[0][0])

# ---- 2. DISTINCT physical bar rows implicated vs their 580,097 ----
print("\n=== 2. BAR-ROW accounting ===")
print("  total cache rows for the 90 subjects:",
      q("SELECT COUNT(*) FROM daily_bar_cache WHERE symbol IN (SELECT DISTINCT subject FROM forecast_decisions WHERE scope='stock')")[0][0])
sql_distinct_rows = f"""
SELECT COUNT(*) FROM (
  SELECT DISTINCT b.symbol, b.trade_date
  FROM forecast_decisions d JOIN daily_bar_cache b ON b.symbol=d.subject
  WHERE d.scope='stock' AND b.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
    AND b.trade_date <= substr(d.decision_cutoff,1,10)
    AND {NORM_CA} > {NORM_CO}
)"""
print("  DISTINCT (symbol,trade_date) rows implicated:", q(sql_distinct_rows)[0][0])
sql_sum = f"""
SELECT COUNT(*) FROM (
  SELECT d.decision_id, d.subject, b.symbol, b.trade_date
  FROM forecast_decisions d JOIN daily_bar_cache b ON b.symbol=d.subject
  WHERE d.scope='stock' AND b.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
    AND b.trade_date <= substr(d.decision_cutoff,1,10)
    AND {NORM_CA} > {NORM_CO}
  GROUP BY d.decision_id, d.subject, b.symbol, b.trade_date
)"""
print("  SUM over pairs (pair x bar incidences, normalized):", q(sql_sum)[0][0])

# ---- 3. Per cutoff-day breakdown ----
print("\n=== 3. Violating pairs by decision cutoff day ===")
for r in q(f"""
 SELECT substr(d.decision_cutoff,1,10) day,
        COUNT(DISTINCT d.decision_id||'|'||d.subject) viol,
        (SELECT COUNT(*) FROM (SELECT DISTINCT decision_id,subject FROM forecast_decisions f
             WHERE f.scope='stock' AND substr(f.decision_cutoff,1,10)=substr(d.decision_cutoff,1,10))) tot
 FROM forecast_decisions d JOIN daily_bar_cache b ON b.symbol=d.subject
 WHERE d.scope='stock' AND b.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
   AND b.trade_date <= substr(d.decision_cutoff,1,10) AND {NORM_CA} > {NORM_CO}
 GROUP BY day ORDER BY day"""):
    print(f"   {r[0]}  violating={r[1]:5d}  total={r[2]:5d}  {100.0*r[1]/r[2]:6.2f}%")

# ---- 4. CONTROL: same test on symbols NEVER used in any decision ----
print("\n=== 4. CONTROL GROUP (symbols never referenced by any decision) ===")
allsym = [r[0] for r in q("SELECT DISTINCT symbol FROM daily_bar_cache WHERE symbol GLOB 'S[HZ][0-9]*'")]
subj = set(r[0] for r in q("SELECT DISTINCT subject FROM forecast_decisions WHERE scope='stock'"))
pool = [s for s in allsym if s not in subj]
random.seed(20260905); ctrl = random.sample(pool, 90)
cutoffs = [r[0] for r in q("SELECT DISTINCT decision_cutoff FROM forecast_decisions WHERE scope='stock'")]
ph=",".join("?"*len(ctrl))
tot=viol=0
for co in cutoffs:
    n = q(f"""SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache
              WHERE symbol IN ({ph}) AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
                AND trade_date <= ? AND replace(substr(created_at,1,19),' ','T') > ?""",
            *ctrl, co[:10], co[:19])[0][0]
    present = q(f"SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE symbol IN ({ph})",*ctrl)[0][0]
    tot += present; viol += n
print(f"   control violating pairs: {viol} / {tot} = {100.0*viol/tot:.2f}%")
c.close()
