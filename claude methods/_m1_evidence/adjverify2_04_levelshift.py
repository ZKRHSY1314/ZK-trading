import sqlite3
LOCAL = r"D:/codex-A股交易/trading_local.sqlite3"
MH    = r"D:/codex-A股交易/market_history.sqlite3"
SCR   = r"D:/codex-A股交易/claude methods/_m1_evidence/adjverify2_scratch.sqlite3"
c = sqlite3.connect(f"file:{LOCAL}?mode=ro", uri=True)
c.execute("ATTACH DATABASE ? AS mh", (f"file:{MH}?mode=ro",))
c.execute("ATTACH DATABASE ? AS scr", (SCR,))
def q(l,s,p=()):
    print("="*100); print(l); print("SQL:", " ".join(s.split()))
    for r in c.execute(s,p).fetchall()[:40]: print("   ",r)

q("E0 is mh an INDEPENDENT source? mh.daily_bars provider values",
  "SELECT provider, COUNT(*), COUNT(DISTINCT symbol) FROM mh.daily_bars GROUP BY 1 ORDER BY 2 DESC")

q("E1 *** LEVEL-SHIFT TEST *** does cache/mh price RATIO jump across the boundary? (scale change = splice)",
  """SELECT src_change, COUNT(*) n,
       ROUND(100.0*AVG(CASE WHEN abs((close/mh_now)/(prev_close/mh_prev)-1.0)>0.02 THEN 1 ELSE 0 END),3) pct_scale_shift_gt2pct,
       ROUND(100.0*AVG(CASE WHEN abs((close/mh_now)/(prev_close/mh_prev)-1.0)>0.005 THEN 1 ELSE 0 END),3) pct_scale_shift_gt05pct
     FROM scr.chk WHERE mh_now>0 AND mh_prev>0 GROUP BY 1""")

q("E2 *** SCALE OF THE REAL DEFECT *** boundaries disagreeing with mh qfq, by threshold, w/ DISTINCT SYMBOLS",
  """SELECT thr, COUNT(*) boundaries, COUNT(DISTINCT symbol) symbols FROM (
       SELECT symbol, abs(ret-mh_ret) d FROM scr.chk WHERE src_change=1 AND mh_ret IS NOT NULL
     ) JOIN (SELECT 0.005 thr UNION SELECT 0.01 UNION SELECT 0.02 UNION SELECT 0.05 UNION SELECT 0.10)
     ON d>thr GROUP BY thr ORDER BY thr""")

q("E3 same thresholds for NON-boundary (the honest control denominator)",
  """SELECT thr, COUNT(*) pairs, COUNT(DISTINCT symbol) symbols FROM (
       SELECT symbol, abs(ret-mh_ret) d FROM scr.chk WHERE src_change=0 AND mh_ret IS NOT NULL
     ) JOIN (SELECT 0.005 thr UNION SELECT 0.01 UNION SELECT 0.02 UNION SELECT 0.05 UNION SELECT 0.10)
     ON d>thr GROUP BY thr ORDER BY thr""")

q("E4 date clustering of the bad tencent->akshare boundaries",
  """SELECT substr(trade_date,1,7) ym, COUNT(*) n_bad
     FROM scr.chk WHERE src_change=1 AND mh_ret IS NOT NULL AND abs(ret-mh_ret)>0.02
     GROUP BY 1 ORDER BY 2 DESC""")

q("E5 worst 12 examples: cache return vs mh qfq return",
  """SELECT symbol, prev_date, trade_date, ROUND(prev_close,3), ROUND(close,3),
            ROUND(100*ret,2) cache_ret_pct, ROUND(100*mh_ret,2) mh_ret_pct,
            ROUND(mh_prev,3), ROUND(mh_now,3), prev_source||' -> '||source
     FROM scr.chk WHERE src_change=1 AND mh_ret IS NOT NULL
     ORDER BY abs(ret-mh_ret) DESC LIMIT 12""")

q("E6 how many DISTINCT SYMBOLS have >=1 proven artifact (>2pp), vs total tradable symbols",
  """SELECT (SELECT COUNT(DISTINCT symbol) FROM scr.chk WHERE src_change=1 AND mh_ret IS NOT NULL AND abs(ret-mh_ret)>0.02) affected,
            (SELECT COUNT(DISTINCT symbol) FROM scr.pairs) universe""")
