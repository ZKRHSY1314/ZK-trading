import sqlite3
TL=r"D:/codex-A股交易/trading_local.sqlite3"
MH=r"D:/codex-A股交易/market_history.sqlite3"
c=sqlite3.connect(f"file:{TL}?mode=ro",uri=True)
c.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")
def P(t,s,*a):
    print("\n### "+t); print("SQL:",' '.join(s.split()))
    for r in c.execute(s,a): print("   ",r)

BASE = """FROM daily_bar_cache c
          JOIN mh.daily_bars m ON m.symbol=c.symbol AND m.trade_date=c.trade_date AND m.adjustment_mode='qfq'
          JOIN mh.instruments i ON i.symbol=c.symbol
          WHERE c.adjustment_mode='qfq' AND c.source=m.provider
            AND c.close IS NOT NULL AND c.close>0 AND m.close>0"""

P("R1 same-provider joined universe: rows, distinct symbols, index-vs-stock split",
  f"""SELECT COUNT(*) keys, COUNT(DISTINCT c.symbol) syms,
             SUM(i.exchange='INDEX') idx_rows, SUM(i.exchange<>'INDEX') stock_rows
      {BASE}""")

P("R2 MY restatement count, STOCKS ONLY, by history available_at cohort AND cache vintage",
  f"""SELECT substr(m.available_at,1,10) hist_vintage, substr(c.updated_at,1,10) cache_vintage,
             COUNT(*) keys, COUNT(DISTINCT c.symbol) syms,
             SUM(abs(m.close/c.close-1.0)>0.01) gt1pct,
             SUM(abs(m.close/c.close-1.0)>0.05) gt5pct
      {BASE} AND i.exchange<>'INDEX'
      GROUP BY 1,2 ORDER BY 3 DESC""")

P("R3 STOCKS ONLY totals (my headline denominator)",
  f"""SELECT COUNT(*) keys, COUNT(DISTINCT c.symbol) syms,
             SUM(abs(m.close/c.close-1.0)>0.01) gt1, COUNT(DISTINCT CASE WHEN abs(m.close/c.close-1.0)>0.01 THEN c.symbol END) syms_gt1,
             SUM(abs(m.close/c.close-1.0)>0.05) gt5, COUNT(DISTINCT CASE WHEN abs(m.close/c.close-1.0)>0.05 THEN c.symbol END) syms_gt5
      {BASE} AND i.exchange<>'INDEX'""")

P("R4 ROUNDING-ARTIFACT CONTROL: price level of the >1% rows (2-decimal quantization test)",
  f"""SELECT CASE WHEN c.close<1 THEN 'a <1' WHEN c.close<3 THEN 'b 1-3' WHEN c.close<10 THEN 'c 3-10'
                  WHEN c.close<50 THEN 'd 10-50' ELSE 'e >=50' END lvl,
             COUNT(*) all_rows, SUM(abs(m.close/c.close-1.0)>0.01) gt1,
             SUM(abs(m.close-c.close)<=0.011) within_1cent_of_diff
      {BASE} AND i.exchange<>'INDEX' GROUP BY 1 ORDER BY 1""")

P("R5 of the >1% rows, how many differ by <= 0.02 absolute (i.e. pure penny rounding)",
  f"""SELECT COUNT(*) gt1_total, SUM(abs(m.close-c.close)<=0.02) gt1_but_within_2cents,
             SUM(abs(m.close-c.close)>0.02) gt1_real_magnitude
      {BASE} AND i.exchange<>'INDEX' AND abs(m.close/c.close-1.0)>0.01""")

P("R6 identical-vintage control: rows where cache.updated_at day == history.available_at day",
  f"""SELECT COUNT(*) keys, SUM(abs(m.close/c.close-1.0)>0.01) gt1,
             ROUND(100.0*SUM(abs(m.close/c.close-1.0)>0.01)/COUNT(*),4) pct
      {BASE} AND i.exchange<>'INDEX' AND substr(c.updated_at,1,10)=substr(m.available_at,1,10)""")

P("R7 true cross-vintage cohort: hist available_at 2026-07-15/16/19 vs cache updated 2026-09-03/04",
  f"""SELECT COUNT(*) keys, COUNT(DISTINCT c.symbol) syms,
             SUM(abs(m.close/c.close-1.0)>0.01) gt1,
             ROUND(100.0*SUM(abs(m.close/c.close-1.0)>0.01)/COUNT(*),4) pct_gt1,
             SUM(abs(m.close/c.close-1.0)>0.05) gt5,
             SUM(abs(m.close/c.close-1.0)>0.01 AND abs(m.close-c.close)>0.02) gt1_and_gt2cents
      {BASE} AND i.exchange<>'INDEX'
        AND substr(m.available_at,1,10)<'2026-08-01' AND substr(c.updated_at,1,10)>='2026-09-01'""")
c.close()
