import sqlite3, statistics
TL=r"D:/codex-A股交易/trading_local.sqlite3"; MH=r"D:/codex-A股交易/market_history.sqlite3"
c=sqlite3.connect(f"file:{TL}?mode=ro",uri=True); c.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")

print("### F1 ratio spread tracks 2-decimal rounding (SH600558): split cohort at its own median price")
s="""SELECT c.trade_date,m.close,c.close,m.close/c.close FROM daily_bar_cache c
     JOIN mh.daily_bars m ON m.symbol=c.symbol AND m.trade_date=c.trade_date AND m.adjustment_mode='qfq'
     WHERE c.symbol='SH600558' AND c.adjustment_mode='qfq' AND c.source=m.provider ORDER BY c.trade_date"""
print("SQL:",' '.join(s.split()))
rows=c.execute(s).fetchall()
px=sorted(r[2] for r in rows); med=px[len(px)//2]
lo=[r[3] for r in rows if r[2]<med]; hi=[r[3] for r in rows if r[2]>=med]
print(f"   n={len(rows)} median close={med}")
for lbl,v in (("cheap half",lo),("expensive half",hi)):
    print(f"   {lbl}: n={len(v)} ratio_med={statistics.median(v):.6f} spread={max(v)-min(v):.6f}")
print("   first/last bars:",rows[0],rows[-1])

print("\n### F2 clean ex-date cut => corporate action, not vendor drift (SH600600)")
s="""SELECT c.trade_date,m.close,c.close,ROUND(m.close/c.close,6) FROM daily_bar_cache c
     JOIN mh.daily_bars m ON m.symbol=c.symbol AND m.trade_date=c.trade_date AND m.adjustment_mode='qfq'
     WHERE c.symbol='SH600600' AND c.adjustment_mode='qfq' AND c.source=m.provider
       AND c.trade_date BETWEEN '2025-11-26' AND '2025-12-08' ORDER BY c.trade_date"""
print("SQL:",' '.join(s.split()))
for r in c.execute(s): print("   ",r)

print("\n### F3 CORRECTED denominator")
J=("""FROM daily_bar_cache c JOIN mh.daily_bars m ON m.symbol=c.symbol AND m.trade_date=c.trade_date"""
   """ AND m.adjustment_mode='qfq' JOIN mh.instruments i ON i.symbol=c.symbol"""
   """ WHERE c.adjustment_mode='qfq' AND c.source=m.provider AND c.close>0 AND m.close>0 AND i.exchange<>'INDEX'""")
s=f"""SELECT COUNT(*) all_keys,
   SUM(substr(c.updated_at,1,10)=substr(m.available_at,1,10)) same_vintage,
   SUM(substr(c.updated_at,1,10)<>substr(m.available_at,1,10)) cross_vintage,
   SUM(substr(c.updated_at,1,10)<>substr(m.available_at,1,10) AND abs(m.close/c.close-1.0)>0.01) xv_gt1,
   SUM(substr(c.updated_at,1,10)<>substr(m.available_at,1,10) AND abs(m.close/c.close-1.0)>0.05) xv_gt5,
   COUNT(DISTINCT CASE WHEN substr(c.updated_at,1,10)<>substr(m.available_at,1,10) THEN c.symbol END) xv_syms,
   COUNT(DISTINCT CASE WHEN substr(c.updated_at,1,10)<>substr(m.available_at,1,10) AND abs(m.close/c.close-1.0)>0.01 THEN c.symbol END) xv_syms_moved
   {J}"""
print("SQL:",' '.join(s.split()))
r=c.execute(s).fetchone(); print("   ",r)
print(f"   THEIR: 6519/{r[0]} = {100*6519/r[0]:.3f}%  (denominator includes {r[1]} SAME-snapshot rows, structurally 0 by R6)")
print(f"   MINE : {r[3]}/{r[2]} = {100*r[3]/r[2]:.3f}% of bars ; {r[6]}/{r[5]} = {100*r[6]/r[5]:.2f}% of securities")
c.close()
