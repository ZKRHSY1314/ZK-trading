import sqlite3
OPS = r"D:/codex-A股交易/trading_local.sqlite3"
HIST= r"D:/codex-A股交易/market_history.sqlite3"
con = sqlite3.connect(f"file:{OPS}?mode=ro", uri=True)
con.execute(f"ATTACH DATABASE 'file:{HIST}?mode=ro' AS mh")
def q(label, sql, args=(), lim=80):
    print("="*100); print(label); print("SQL:", " ".join(sql.split()))
    cur=con.execute(sql,args); cols=[d[0] for d in cur.description]; rows=cur.fetchall()
    print(" | ".join(cols))
    for r in rows[:lim]: print(" | ".join("" if v is None else str(v) for v in r))
    if len(rows)>lim: print(f"... ({len(rows)} rows total)")
    print()

# C1: divergence by YEAR + explicit research-window restriction
q("C1 divergence by calendar year, and inside the fixed research window 2023-09-04..2026-09-04",
  """WITH j AS (SELECT d.trade_date td, d.close dc, b.close bc FROM daily_bar_cache d JOIN mh.daily_bars b
       ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
       WHERE d.quality_status='ready' AND d.adjustment_mode='qfq')
     SELECT substr(td,1,4) yr, COUNT(*) n,
       SUM(CASE WHEN ABS(dc-bc)>0.005 THEN 1 ELSE 0 END) d_half_cent,
       ROUND(100.0*SUM(CASE WHEN ABS(dc-bc)>0.005 THEN 1 ELSE 0 END)/COUNT(*),2) pct_half_cent,
       ROUND(100.0*SUM(CASE WHEN ABS(dc-bc)/NULLIF(bc,0)>0.01 THEN 1 ELSE 0 END)/COUNT(*),2) pct_gt1pct,
       MIN(td) first_td, MAX(td) last_td
     FROM j GROUP BY 1 ORDER BY 1""")

# C2: cross-tab of ops source vs hist provider on the diverging rows -- is this provider mismatch?
q("C2 divergence rate by (ops source, hist provider) pair",
  """SELECT d.source ops_source, b.provider hist_provider, COUNT(*) n,
            ROUND(100.0*SUM(CASE WHEN ABS(d.close-b.close)>0.005 THEN 1 ELSE 0 END)/COUNT(*),2) pct_half_cent,
            ROUND(100.0*SUM(CASE WHEN ABS(d.close-b.close)/NULLIF(b.close,0)>0.01 THEN 1 ELSE 0 END)/COUNT(*),2) pct_gt1pct
     FROM daily_bar_cache d JOIN mh.daily_bars b
       ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
     WHERE d.quality_status='ready' AND d.adjustment_mode='qfq'
     GROUP BY 1,2 HAVING n>200 ORDER BY n DESC""")

# C3: divergence by hist fetch vintage (date part of fetched_at)
q("C3 divergence rate by market_history fetched_at date (vintage)",
  """SELECT substr(b.fetched_at,1,10) hist_fetch_day, COUNT(*) n,
            ROUND(100.0*SUM(CASE WHEN ABS(d.close-b.close)>0.005 THEN 1 ELSE 0 END)/COUNT(*),2) pct_half_cent,
            ROUND(100.0*SUM(CASE WHEN ABS(d.close-b.close)/NULLIF(b.close,0)>0.01 THEN 1 ELSE 0 END)/COUNT(*),2) pct_gt1pct
     FROM daily_bar_cache d JOIN mh.daily_bars b
       ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
     WHERE d.quality_status='ready' AND d.adjustment_mode='qfq'
     GROUP BY 1 ORDER BY n DESC LIMIT 30""")

# C4: verify their stated worst case SZ301590 2025-09-30 and show its neighbourhood
q("C4 SZ301590 around 2025-09-30 (their worst case)",
  """SELECT d.trade_date, d.close ops_close, b.close hist_close,
            ROUND(b.close/NULLIF(d.close,0),6) hist_over_ops, d.source ops_source, b.provider hist_provider,
            d.volume ops_vol, b.volume hist_vol, b.fetched_at
     FROM daily_bar_cache d JOIN mh.daily_bars b
       ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
     WHERE d.symbol='SZ301590' AND d.quality_status='ready' AND d.adjustment_mode='qfq'
       AND d.trade_date BETWEEN '2025-09-20' AND '2025-10-20' ORDER BY d.trade_date""")

# C5: does market_history hold OTHER adjustment modes for the same key? (mode-label mismatch probe)
q("C5 adjustment_mode label integrity: does ops 'qfq' close match hist 'none'/'hfq' better?",
  """SELECT b.adjustment_mode, COUNT(*) n,
            ROUND(100.0*SUM(CASE WHEN ABS(d.close-b.close)>0.005 THEN 1 ELSE 0 END)/COUNT(*),2) pct_half_cent
     FROM daily_bar_cache d JOIN mh.daily_bars b ON b.symbol=d.symbol AND b.trade_date=d.trade_date
     WHERE d.quality_status='ready' AND d.adjustment_mode='qfq' GROUP BY 1""")
con.close()
