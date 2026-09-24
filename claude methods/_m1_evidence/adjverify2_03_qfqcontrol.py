import sqlite3
LOCAL = r"D:/codex-A股交易/trading_local.sqlite3"
MH    = r"D:/codex-A股交易/market_history.sqlite3"
SCR   = r"D:/codex-A股交易/claude methods/_m1_evidence/adjverify2_scratch.sqlite3"
c = sqlite3.connect(f"file:{LOCAL}?mode=ro", uri=True)
c.execute("ATTACH DATABASE ? AS mh", (f"file:{MH}?mode=ro",))
c.execute("ATTACH DATABASE ? AS scr", (SCR,))
c.execute("PRAGMA scr.journal_mode=OFF")

# Attach mh qfq closes for BOTH legs of every pair -> discrepancy between the
# cache return and the continuous research-grade qfq return.
c.execute("DROP TABLE IF EXISTS scr.chk")
c.execute("""
CREATE TABLE scr.chk AS
SELECT p.symbol, p.prev_date, p.trade_date, p.ret, p.src_change,
       p.prev_source, p.source,
       a.close AS mh_prev, b.close AS mh_now,
       CASE WHEN a.close>0 AND b.close>0 THEN (b.close/a.close - 1.0) END AS mh_ret
FROM scr.pairs p
LEFT JOIN mh.daily_bars a ON a.symbol=p.symbol AND a.trade_date=p.prev_date  AND a.adjustment_mode='qfq'
LEFT JOIN mh.daily_bars b ON b.symbol=p.symbol AND b.trade_date=p.trade_date AND b.adjustment_mode='qfq'
""")
c.commit()
c.execute("CREATE INDEX scr.ix3 ON chk(src_change)")

def q(l,s,p=()):
    print("="*100); print(l); print("SQL:", " ".join(s.split()))
    for r in c.execute(s,p).fetchall()[:60]: print("   ",r)

q("D1 mh join coverage (verifiable pairs) by src_change",
  """SELECT src_change, COUNT(*) n, SUM(mh_ret IS NOT NULL) verifiable,
            ROUND(100.0*SUM(mh_ret IS NOT NULL)/COUNT(*),2) pct_verifiable
     FROM scr.chk GROUP BY 1""")

q("D2 *** THE CONTROL *** among pairs with |cache ret|>2%, how often is mh qfq SMOOTH (|mh_ret|<=0.5%)?",
  """SELECT src_change, COUNT(*) checkable,
            SUM(CASE WHEN abs(mh_ret)<=0.005 THEN 1 ELSE 0 END) smooth_in_mh,
            ROUND(100.0*AVG(CASE WHEN abs(mh_ret)<=0.005 THEN 1 ELSE 0 END),2) pct_smooth,
            SUM(CASE WHEN abs(ret-mh_ret)>0.01 THEN 1 ELSE 0 END) differs_gt1pp,
            ROUND(100.0*AVG(CASE WHEN abs(ret-mh_ret)>0.01 THEN 1 ELSE 0 END),2) pct_differs
     FROM scr.chk WHERE abs(ret)>0.02 AND mh_ret IS NOT NULL GROUP BY 1""")

q("D3 *** THRESHOLD-FREE *** distribution of |cache_ret - mh_qfq_ret| over ALL verifiable pairs",
  """SELECT src_change, COUNT(*) n,
            ROUND(100.0*AVG(CASE WHEN abs(ret-mh_ret)<=0.0005 THEN 1 ELSE 0 END),2) pct_agree_5bp,
            ROUND(100.0*AVG(CASE WHEN abs(ret-mh_ret)>0.005  THEN 1 ELSE 0 END),2) pct_disagree_50bp,
            ROUND(100.0*AVG(CASE WHEN abs(ret-mh_ret)>0.02   THEN 1 ELSE 0 END),2) pct_disagree_2pct,
            ROUND(100.0*AVG(abs(ret-mh_ret)),5) mean_abs_diff
     FROM scr.chk WHERE mh_ret IS NOT NULL GROUP BY 1""")

q("D4 disagreement>2pp broken out by transition (which vendor pair is actually broken?)",
  """SELECT CASE WHEN src_change=1 THEN prev_source||' -> '||source ELSE 'NON-BOUNDARY ('||source||')' END k,
            COUNT(*) n, SUM(CASE WHEN abs(ret-mh_ret)>0.02 THEN 1 ELSE 0 END) bad,
            ROUND(100.0*AVG(CASE WHEN abs(ret-mh_ret)>0.02 THEN 1 ELSE 0 END),2) pct_bad
     FROM scr.chk WHERE mh_ret IS NOT NULL GROUP BY 1 ORDER BY n DESC""")

q("D5 absolute scale: total pairs where cache disagrees with mh qfq by >2pp, boundary vs not",
  """SELECT src_change, COUNT(*) FROM scr.chk
     WHERE mh_ret IS NOT NULL AND abs(ret-mh_ret)>0.02 GROUP BY 1""")
