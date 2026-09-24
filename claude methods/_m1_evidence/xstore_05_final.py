import sqlite3
OPS = r"D:/codex-A股交易/trading_local.sqlite3"
HIST= r"D:/codex-A股交易/market_history.sqlite3"
con = sqlite3.connect(f"file:{OPS}?mode=ro", uri=True)
con.execute(f"ATTACH DATABASE 'file:{HIST}?mode=ro' AS mh")
def q(label, sql, lim=30):
    print("="*100); print(label); print("SQL:", " ".join(sql.split()))
    cur=con.execute(sql); cols=[d[0] for d in cur.description]; rows=cur.fetchall()
    print(" | ".join(cols))
    for r in rows[:lim]: print(" | ".join("" if v is None else str(v) for v in r))
    if len(rows)>lim: print(f"... ({len(rows)} rows)")
    print()

q("F1 SAME-PROVIDER vs CROSS-PROVIDER concentration of the 1,059,740 diverging rows",
  """SELECT CASE WHEN d.source=b.provider THEN 'same_provider' ELSE 'cross_provider' END grp,
            COUNT(*) shared_rows,
            SUM(CASE WHEN ABS(d.close-b.close)>0.005 THEN 1 ELSE 0 END) diverging,
            ROUND(100.0*SUM(CASE WHEN ABS(d.close-b.close)>0.005 THEN 1 ELSE 0 END)/COUNT(*),2) pct_within_grp,
            ROUND(100.0*SUM(CASE WHEN ABS(d.close-b.close)>0.005 THEN 1 ELSE 0 END)/1059740.0,2) pct_of_all_divergence
     FROM daily_bar_cache d JOIN mh.daily_bars b
       ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
     WHERE d.quality_status='ready' AND d.adjustment_mode='qfq' GROUP BY 1""")

q("F2 where the claim's '5,566 symbols' cannot come from",
  """SELECT (SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache) all_ops_syms,
            (SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE quality_status='ready' AND adjustment_mode='qfq') ops_ready_qfq_syms,
            (SELECT COUNT(DISTINCT symbol) FROM mh.daily_bars WHERE adjustment_mode='qfq') hist_qfq_syms,
            (SELECT COUNT(DISTINCT d.symbol) FROM daily_bar_cache d JOIN mh.daily_bars b
               ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
             WHERE d.quality_status='ready' AND d.adjustment_mode='qfq') shared_syms,
            (SELECT COUNT(*) FROM mh.instruments) instruments""")

q("F3 research-window coverage of the shared set (window 2023-09-04..2026-09-04)",
  """SELECT COUNT(*) shared_rows_in_window,
            MIN(d.trade_date) first_shared, MAX(d.trade_date) last_shared,
            SUM(CASE WHEN d.trade_date<'2024-04-09' THEN 1 ELSE 0 END) shared_before_2024_04_09
     FROM daily_bar_cache d JOIN mh.daily_bars b
       ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
     WHERE d.quality_status='ready' AND d.adjustment_mode='qfq'
       AND d.trade_date BETWEEN '2023-09-04' AND '2026-09-04'""")

q("F4 HEADLINE RESTATEMENT: level disagreement vs RETURN disagreement, side by side",
  """WITH j AS (SELECT d.symbol s,d.trade_date td,d.close dc,b.close bc
       FROM daily_bar_cache d JOIN mh.daily_bars b
         ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
       WHERE d.quality_status='ready' AND d.adjustment_mode='qfq'),
     r AS (SELECT s,td,dc,bc,
             dc/NULLIF(LAG(dc) OVER (PARTITION BY s ORDER BY td),0)-1 orr,
             bc/NULLIF(LAG(bc) OVER (PARTITION BY s ORDER BY td),0)-1 hrr FROM j)
     SELECT COUNT(*) n_rows,
       ROUND(100.0*SUM(CASE WHEN ABS(dc-bc)>0.005 THEN 1 ELSE 0 END)/COUNT(*),2) pct_level_gt_halfcent,
       ROUND(100.0*SUM(CASE WHEN ABS(dc-bc)/NULLIF(bc,0)>0.01 THEN 1 ELSE 0 END)/COUNT(*),2) pct_level_gt_1pct,
       SUM(CASE WHEN orr IS NOT NULL THEN 1 ELSE 0 END) n_return_pairs,
       ROUND(100.0*SUM(CASE WHEN orr IS NOT NULL AND ABS(orr-hrr)>0.001 THEN 1 ELSE 0 END)
             /SUM(CASE WHEN orr IS NOT NULL THEN 1 ELSE 0 END),3) pct_return_gt_10bp,
       ROUND(100.0*SUM(CASE WHEN orr IS NOT NULL AND ABS(orr-hrr)>0.01 THEN 1 ELSE 0 END)
             /SUM(CASE WHEN orr IS NOT NULL THEN 1 ELSE 0 END),3) pct_return_gt_1pct,
       COUNT(DISTINCT CASE WHEN orr IS NOT NULL AND ABS(orr-hrr)>0.01 THEN s END) syms_return_gt_1pct
     FROM r""")

q("F5 SZ301590 affine check: ops = 0.714296*hist - 0.574 reproduces every bar?",
  """SELECT d.trade_date, d.close ops, b.close hist,
            ROUND(0.714296*b.close-0.574,3) affine_pred,
            ROUND(d.close-(0.714296*b.close-0.574),4) residual
     FROM daily_bar_cache d JOIN mh.daily_bars b
       ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
     WHERE d.symbol='SZ301590' AND d.quality_status='ready' AND d.adjustment_mode='qfq'
       AND d.trade_date BETWEEN '2025-08-01' AND '2025-12-31'
     ORDER BY ABS(d.close-(0.714296*b.close-0.574)) DESC LIMIT 6""")
con.close()
