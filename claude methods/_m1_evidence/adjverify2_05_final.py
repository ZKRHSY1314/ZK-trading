import sqlite3
LOCAL = r"D:/codex-A股交易/trading_local.sqlite3"
MH    = r"D:/codex-A股交易/market_history.sqlite3"
SCR   = r"D:/codex-A股交易/claude methods/_m1_evidence/adjverify2_scratch.sqlite3"
c = sqlite3.connect(f"file:{LOCAL}?mode=ro", uri=True)
c.execute("ATTACH DATABASE ? AS mh", (f"file:{MH}?mode=ro",))
c.execute("ATTACH DATABASE ? AS scr", (SCR,))
c.execute("PRAGMA scr.journal_mode=OFF")
c.execute("DROP TABLE IF EXISTS scr.chk2")
c.execute("""
CREATE TABLE scr.chk2 AS
SELECT p.symbol,p.prev_date,p.trade_date,p.prev_close,p.close,p.ret,p.src_change,
       p.prev_source,p.source,
       a.close AS mh_prev, b.close AS mh_now, a.provider AS mh_prov_prev, b.provider AS mh_prov_now,
       CASE WHEN a.close>0 AND b.close>0 THEN (b.close/a.close-1.0) END AS mh_ret
FROM scr.pairs p
LEFT JOIN mh.daily_bars a ON a.symbol=p.symbol AND a.trade_date=p.prev_date  AND a.adjustment_mode='qfq'
LEFT JOIN mh.daily_bars b ON b.symbol=p.symbol AND b.trade_date=p.trade_date AND b.adjustment_mode='qfq'
""")
c.commit(); c.execute("CREATE INDEX scr.ix4 ON chk2(src_change)")
def q(l,s,p=()):
    print("="*100); print(l); print("SQL:"," ".join(s.split()))
    for r in c.execute(s,p).fetchall()[:40]: print("   ",r)

q("F1 is mh ALSO spliced at the same pairs? (mh provider change across the same two dates)",
  """SELECT src_change, COUNT(*) n,
            SUM(CASE WHEN mh_prov_prev<>mh_prov_now THEN 1 ELSE 0 END) mh_also_switches,
            ROUND(100.0*AVG(CASE WHEN mh_prov_prev<>mh_prov_now THEN 1 ELSE 0 END),2) pct
     FROM scr.chk2 WHERE mh_ret IS NOT NULL GROUP BY 1""")

q("F2 *** CLEANEST TEST *** restrict to pairs where mh is provider-CONTINUOUS: cache vs mh return disagreement",
  """SELECT src_change, COUNT(*) n,
            SUM(CASE WHEN abs(ret-mh_ret)>0.02 THEN 1 ELSE 0 END) bad_gt2pp,
            ROUND(100.0*AVG(CASE WHEN abs(ret-mh_ret)>0.02 THEN 1 ELSE 0 END),3) pct_bad,
            COUNT(DISTINCT CASE WHEN abs(ret-mh_ret)>0.02 THEN symbol END) sym_bad
     FROM scr.chk2 WHERE mh_ret IS NOT NULL AND mh_prov_prev=mh_prov_now GROUP BY 1""")

q("F3 *** LEVEL-SHIFT *** cache/mh scale ratio jump across the pair (splice signature), mh-continuous only",
  """SELECT src_change, COUNT(*) n,
            ROUND(100.0*AVG(CASE WHEN abs((close/mh_now)/(prev_close/mh_prev)-1.0)>0.02 THEN 1 ELSE 0 END),3) pct_scale_shift_2pct
     FROM scr.chk2 WHERE mh_now>0 AND mh_prev>0 AND mh_prov_prev=mh_prov_now GROUP BY 1""")

q("F4 SCALE by threshold (mh-continuous boundaries only): boundaries + DISTINCT SYMBOLS",
  """SELECT thr, COUNT(*) boundaries, COUNT(DISTINCT symbol) symbols FROM
     (SELECT symbol, abs(ret-mh_ret) d FROM scr.chk2
        WHERE src_change=1 AND mh_ret IS NOT NULL AND mh_prov_prev=mh_prov_now)
     JOIN (SELECT 0.005 thr UNION SELECT 0.01 UNION SELECT 0.02 UNION SELECT 0.05 UNION SELECT 0.10)
     ON d>thr GROUP BY thr ORDER BY thr""")

q("F5 worst 10 examples (mh-continuous)",
  """SELECT symbol,prev_date,trade_date,ROUND(prev_close,2),ROUND(close,2),ROUND(100*ret,1) cache_pct,
            ROUND(mh_prev,2),ROUND(mh_now,2),ROUND(100*mh_ret,1) mh_pct, prev_source||'->'||source
     FROM scr.chk2 WHERE src_change=1 AND mh_ret IS NOT NULL AND mh_prov_prev=mh_prov_now
     ORDER BY abs(ret-mh_ret) DESC LIMIT 10""")

q("F6 universe + affected symbol counts (final denominators)",
  """SELECT (SELECT COUNT(DISTINCT symbol) FROM scr.pairs) universe_syms,
            (SELECT COUNT(DISTINCT symbol) FROM scr.pairs WHERE src_change=1) syms_multi_source,
            (SELECT COUNT(DISTINCT symbol) FROM scr.chk2 WHERE src_change=1 AND mh_ret IS NOT NULL
               AND mh_prov_prev=mh_prov_now AND abs(ret-mh_ret)>0.02) syms_proven_artifact""")
