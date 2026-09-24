import sqlite3, os
LOCAL = r"D:/codex-A股交易/trading_local.sqlite3"
MH    = r"D:/codex-A股交易/market_history.sqlite3"
SCR   = r"D:/codex-A股交易/claude methods/_m1_evidence/adjverify2_scratch.sqlite3"
W0, W1 = "2023-09-04", "2026-09-04"
if os.path.exists(SCR): os.remove(SCR)

c = sqlite3.connect(f"file:{LOCAL}?mode=ro", uri=True)
c.execute("ATTACH DATABASE ? AS mh", (f"file:{MH}?mode=ro",))
c.execute("ATTACH DATABASE ? AS scr", (SCR,))
c.execute("PRAGMA scr.journal_mode=OFF")

PAIR_SQL = f"""
CREATE TABLE scr.pairs AS
WITH src AS (
  SELECT symbol, trade_date, close, source
  FROM daily_bar_cache
  WHERE quality_status = 'ready'
    AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
    AND trade_date BETWEEN '{W0}' AND '{W1}'
    AND close IS NOT NULL AND close > 0
    AND symbol NOT IN ('SH000001','SH000300')          -- drop the 2 indices
), lagged AS (
  SELECT symbol, trade_date, close, source,
         LAG(close)      OVER w AS prev_close,
         LAG(trade_date) OVER w AS prev_date,
         LAG(source)     OVER w AS prev_source
  FROM src
  WINDOW w AS (PARTITION BY symbol ORDER BY trade_date)
)
SELECT symbol, prev_date, trade_date, prev_close, close, prev_source, source,
       (close/prev_close - 1.0) AS ret,
       CASE WHEN source <> prev_source THEN 1 ELSE 0 END AS src_change,
       CAST(julianday(trade_date) - julianday(prev_date) AS INT) AS gap_days
FROM lagged
WHERE prev_close IS NOT NULL AND prev_close > 0;
"""
print("building pairs..."); c.execute(PAIR_SQL); c.commit()
c.execute("CREATE INDEX scr.ix1 ON pairs(src_change)")
c.execute("CREATE INDEX scr.ix2 ON pairs(symbol, trade_date)")

def q(l,s,p=()):
    print("="*100); print(l); print("SQL:", " ".join(s.split()))
    for r in c.execute(s,p).fetchall()[:60]: print("   ",r)

q("C1 population: pairs, symbols, boundaries (MY count)",
  """SELECT COUNT(*) pairs, COUNT(DISTINCT symbol) syms,
            SUM(src_change) boundaries,
            COUNT(DISTINCT CASE WHEN src_change=1 THEN symbol END) syms_with_boundary
     FROM scr.pairs""")

q("C2 *** BASE RATE CONTROL *** |ret| distribution: boundary vs NON-boundary",
  """SELECT src_change,
            COUNT(*) n,
            ROUND(100.0*AVG(CASE WHEN abs(ret)>0.02 THEN 1 ELSE 0 END),2) pct_gt2,
            ROUND(100.0*AVG(CASE WHEN abs(ret)>0.05 THEN 1 ELSE 0 END),2) pct_gt5,
            ROUND(100.0*AVG(CASE WHEN abs(ret)>0.10 THEN 1 ELSE 0 END),2) pct_gt10
     FROM scr.pairs GROUP BY src_change""")

for sc in (0,1):
    rows=c.execute("""SELECT abs(ret) FROM scr.pairs WHERE src_change=? ORDER BY abs(ret)""",(sc,)).fetchall()
    n=len(rows)
    def pct(p): return round(100*rows[min(n-1,int(p*n))][0],3)
    print(f"C3 percentiles of |ret| src_change={sc}: n={n} p50={pct(.5)}% p90={pct(.9)}% p99={pct(.99)}% max={round(100*rows[-1][0],2)}%")

q("C4 boundary transitions: which source->source pairs, and their >2% rate vs base",
  """SELECT prev_source||' -> '||source AS transition, COUNT(*) n,
            ROUND(100.0*AVG(CASE WHEN abs(ret)>0.02 THEN 1 ELSE 0 END),1) pct_gt2,
            ROUND(100.0*AVG(abs(ret)),3) mean_abs_ret_pct100
     FROM scr.pairs WHERE src_change=1 GROUP BY 1 ORDER BY n DESC""")

q("C5 *** GAP CONFOUND *** boundaries vs non-boundaries by calendar gap bucket",
  """SELECT src_change,
            CASE WHEN gap_days<=4 THEN 'a_normal(<=4d)'
                 WHEN gap_days<=10 THEN 'b_holiday(5-10d)'
                 WHEN gap_days<=40 THEN 'c_gap(11-40d)'
                 ELSE 'd_longgap(>40d)' END bucket,
            COUNT(*) n, ROUND(100.0*AVG(CASE WHEN abs(ret)>0.02 THEN 1 ELSE 0 END),2) pct_gt2
     FROM scr.pairs GROUP BY 1,2 ORDER BY 2,1""")

q("C6 *** RUN STRUCTURE *** how many source runs per symbol (is it a splice or a patch?)",
  """SELECT n_boundaries, COUNT(*) symbols FROM (
        SELECT symbol, SUM(src_change) n_boundaries FROM scr.pairs GROUP BY symbol
     ) GROUP BY 1 ORDER BY 1""")
