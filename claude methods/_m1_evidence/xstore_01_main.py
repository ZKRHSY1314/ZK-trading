import sqlite3
OPS = r"D:/codex-A股交易/trading_local.sqlite3"
HIST= r"D:/codex-A股交易/market_history.sqlite3"
con = sqlite3.connect(f"file:{OPS}?mode=ro", uri=True)
con.execute(f"ATTACH DATABASE 'file:{HIST}?mode=ro' AS mh")
def q(label, sql, args=()):
    print("="*100); print(label); print("SQL:", " ".join(sql.split()))
    cur=con.execute(sql,args); cols=[d[0] for d in cur.description]; rows=cur.fetchall()
    print(" | ".join(cols))
    for r in rows[:80]: print(" | ".join("" if v is None else str(v) for v in r))
    if len(rows)>80: print(f"... ({len(rows)} rows total)")
    print()

# B1: exact size of the shared set, distinct symbols in it, and rows on each side that DON'T match
q("B1 shared-set size and true symbol denominator",
  """SELECT COUNT(*) shared_rows, COUNT(DISTINCT d.symbol) shared_symbols,
            MIN(d.trade_date) mn, MAX(d.trade_date) mx
     FROM daily_bar_cache d JOIN mh.daily_bars b
       ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
     WHERE d.quality_status='ready' AND d.adjustment_mode='qfq'""")

# B2: decimal precision actually stored, per store  (rounding-artifact probe)
q("B2 stored decimal precision of close, ops vs hist",
  """WITH j AS (SELECT d.close dc, b.close bc FROM daily_bar_cache d JOIN mh.daily_bars b
       ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
       WHERE d.quality_status='ready' AND d.adjustment_mode='qfq')
     SELECT SUM(CASE WHEN ABS(dc-ROUND(dc,2))<1e-9 THEN 1 ELSE 0 END) ops_2dp,
            SUM(CASE WHEN ABS(dc-ROUND(dc,3))<1e-9 THEN 1 ELSE 0 END) ops_3dp,
            SUM(CASE WHEN ABS(bc-ROUND(bc,2))<1e-9 THEN 1 ELSE 0 END) hist_2dp,
            SUM(CASE WHEN ABS(bc-ROUND(bc,3))<1e-9 THEN 1 ELSE 0 END) hist_3dp,
            COUNT(*) n FROM j""")

# B3: MY measure -- relative difference bands (not their absolute 0.005 cent rule)
q("B3 relative close-difference distribution over the shared set",
  """WITH j AS (SELECT d.symbol s, d.trade_date td, d.close dc, b.close bc,
                      ABS(d.close-b.close)/NULLIF(b.close,0) rel
       FROM daily_bar_cache d JOIN mh.daily_bars b
         ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
       WHERE d.quality_status='ready' AND d.adjustment_mode='qfq')
     SELECT COUNT(*) n,
       SUM(CASE WHEN dc=bc THEN 1 ELSE 0 END) bitwise_equal,
       SUM(CASE WHEN rel<=1e-9 THEN 1 ELSE 0 END) rel_le_1e9,
       SUM(CASE WHEN rel>1e-9  AND rel<=1e-4 THEN 1 ELSE 0 END) b_1e9_1bp,
       SUM(CASE WHEN rel>1e-4  AND rel<=1e-3 THEN 1 ELSE 0 END) b_1bp_10bp,
       SUM(CASE WHEN rel>1e-3  AND rel<=1e-2 THEN 1 ELSE 0 END) b_10bp_1pct,
       SUM(CASE WHEN rel>1e-2  AND rel<=5e-2 THEN 1 ELSE 0 END) b_1pct_5pct,
       SUM(CASE WHEN rel>5e-2  AND rel<=2e-1 THEN 1 ELSE 0 END) b_5pct_20pct,
       SUM(CASE WHEN rel>2e-1 THEN 1 ELSE 0 END) b_gt20pct
     FROM j""")

# B4: their exact absolute-cent rule reproduced AND a like-for-like tick-aware rule
q("B4 their 0.005 abs rule vs a tick-aware rule (A-share tick = 0.01)",
  """WITH j AS (SELECT d.close dc, b.close bc, d.symbol s FROM daily_bar_cache d JOIN mh.daily_bars b
       ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
       WHERE d.quality_status='ready' AND d.adjustment_mode='qfq')
     SELECT COUNT(*) n,
       SUM(CASE WHEN ABS(dc-bc)>0.005 THEN 1 ELSE 0 END) their_gt_half_cent,
       ROUND(100.0*SUM(CASE WHEN ABS(dc-bc)>0.005 THEN 1 ELSE 0 END)/COUNT(*),2) pct_theirs,
       SUM(CASE WHEN ABS(dc-bc)>0.011 THEN 1 ELSE 0 END) gt_one_tick,
       ROUND(100.0*SUM(CASE WHEN ABS(dc-bc)>0.011 THEN 1 ELSE 0 END)/COUNT(*),2) pct_one_tick,
       SUM(CASE WHEN ABS(dc-bc)/NULLIF(bc,0)>0.01 THEN 1 ELSE 0 END) gt_1pct,
       ROUND(100.0*SUM(CASE WHEN ABS(dc-bc)/NULLIF(bc,0)>0.01 THEN 1 ELSE 0 END)/COUNT(*),2) pct_gt_1pct,
       COUNT(DISTINCT CASE WHEN ABS(dc-bc)>0.005 THEN s END) syms_theirs,
       COUNT(DISTINCT CASE WHEN ABS(dc-bc)/NULLIF(bc,0)>0.01 THEN s END) syms_gt1pct
     FROM j""")

# B5: is it prices only, or the whole bar?  volume tells us same-vs-different underlying data
q("B5 do volume and amount agree on rows where close disagrees >1%?",
  """WITH j AS (SELECT d.close dc,b.close bc,d.volume dv,b.volume bv,d.amount da,b.amount ba,
                      d.volume_unit dvu,b.volume_unit bvu
       FROM daily_bar_cache d JOIN mh.daily_bars b
         ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
       WHERE d.quality_status='ready' AND d.adjustment_mode='qfq')
     SELECT SUM(CASE WHEN ABS(dc-bc)/NULLIF(bc,0)>0.01 THEN 1 ELSE 0 END) n_close_gt1pct,
            SUM(CASE WHEN ABS(dc-bc)/NULLIF(bc,0)>0.01 AND dv=bv THEN 1 ELSE 0 END) vol_identical,
            SUM(CASE WHEN ABS(dc-bc)/NULLIF(bc,0)>0.01 AND da=ba THEN 1 ELSE 0 END) amt_identical,
            SUM(CASE WHEN ABS(dc-bc)/NULLIF(bc,0)>0.01 AND da IS NULL THEN 1 ELSE 0 END) ops_amt_null,
            SUM(CASE WHEN ABS(dc-bc)/NULLIF(bc,0)>0.01 AND ba IS NULL THEN 1 ELSE 0 END) hist_amt_null
     FROM j""")
con.close()
