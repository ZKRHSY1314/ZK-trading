import sqlite3
SCR = r"D:/codex-A股交易/claude methods/_m1_evidence/adjverify2_scratch.sqlite3"
MH  = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{SCR}?mode=ro", uri=True)
def q(l,s,p=()):
    print("="*100); print(l); print("SQL:"," ".join(s.split()))
    for r in c.execute(s,p).fetchall()[:25]: print("   ",r)

q("G1 *** DATE CLUSTERING *** proven artifacts (>2pp vs continuous mh qfq) by boundary date",
  """SELECT trade_date, COUNT(*) n_bad, COUNT(DISTINCT symbol) syms
     FROM chk2 WHERE src_change=1 AND mh_ret IS NOT NULL AND mh_prov_prev=mh_prov_now
       AND abs(ret-mh_ret)>0.02 GROUP BY 1 ORDER BY 2 DESC""")

q("G2 ALL 6243 boundaries by date (is the 'splicing' one ingest event?)",
  """SELECT trade_date, COUNT(*) n FROM pairs WHERE src_change=1 GROUP BY 1 ORDER BY 2 DESC""")

q("G3 which SIDE is wrong? does cache prev_close match mh_prev, and cache close match mh_now?",
  """SELECT src_change,
       COUNT(*) n,
       ROUND(100.0*AVG(CASE WHEN abs(prev_close/mh_prev-1)<0.001 THEN 1 ELSE 0 END),2) pct_prev_matches_mh,
       ROUND(100.0*AVG(CASE WHEN abs(close/mh_now-1)<0.001 THEN 1 ELSE 0 END),2) pct_now_matches_mh
     FROM chk2 WHERE mh_prev>0 AND mh_now>0 AND mh_prov_prev=mh_prov_now
       AND (src_change=0 OR abs(ret-mh_ret)>0.02) GROUP BY 1""")

q("G4 direction of the fake return at proven artifacts",
  """SELECT SUM(CASE WHEN ret-mh_ret<0 THEN 1 ELSE 0 END) fake_down,
            SUM(CASE WHEN ret-mh_ret>0 THEN 1 ELSE 0 END) fake_up,
            ROUND(100*MIN(ret-mh_ret),1) worst_down_pp, ROUND(100*MAX(ret-mh_ret),1) worst_up_pp
     FROM chk2 WHERE src_change=1 AND mh_ret IS NOT NULL AND mh_prov_prev=mh_prov_now AND abs(ret-mh_ret)>0.02""")

q("G5 sanity: the 2 tonghuasun transitions had the biggest raw jumps - are ANY of them artifacts?",
  """SELECT prev_source||'->'||source t, COUNT(*) n,
            SUM(CASE WHEN abs(ret-mh_ret)>0.02 THEN 1 ELSE 0 END) proven_bad,
            ROUND(100.0*AVG(abs(ret)),2) mean_abs_cache_ret_pct
     FROM chk2 WHERE src_change=1 AND mh_ret IS NOT NULL AND mh_prov_prev=mh_prov_now
       AND source LIKE '%tonghuasun%' OR (src_change=1 AND mh_ret IS NOT NULL AND prev_source LIKE '%tonghuasun%')
     GROUP BY 1""")
