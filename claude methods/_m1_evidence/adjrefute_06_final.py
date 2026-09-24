import sqlite3, statistics, collections
TL=r"D:/codex-A股交易/trading_local.sqlite3"; MH=r"D:/codex-A股交易/market_history.sqlite3"
c=sqlite3.connect(f"file:{TL}?mode=ro",uri=True); c.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")

print("### F1 ratio spread is 2-decimal ROUNDING, not noise: spread shrinks as price rises (SH600558)")
s="""SELECT c.trade_date,m.close,c.close,ROUND(m.close/c.close,6)
     FROM daily_bar_cache c JOIN mh.daily_bars m ON m.symbol=c.symbol AND m.trade_date=c.trade_date
       AND m.adjustment_mode='qfq'
     WHERE c.symbol='SH600558' AND c.adjustment_mode='qfq' AND c.source=m.provider
     ORDER BY c.trade_date"""
rows=c.execute(s).fetchall(); print("SQL:",' '.join(s.split()))
lo=[r[3] for r in rows if r[2]<6]; hi=[r[3] for r in rows if r[2]>=9]
print(f"   n={len(rows)}  bars close<6: n={len(lo)} ratio med={statistics.median(lo):.6f} spread={max(lo)-min(lo):.6f}")
print(f"             bars close>=9: n={len(hi)} ratio med={statistics.median(hi):.6f} spread={max(hi)-min(hi):.6f}")
for r in rows[:3]+rows[-3:]: print("   ",r)

print("\n### F2 clean ex-date cut proves corporate action, not vendor drift (SH600600)")
s="""SELECT c.trade_date,m.close,c.close,ROUND(m.close/c.close,6)
     FROM daily_bar_cache c JOIN mh.daily_bars m ON m.symbol=c.symbol AND m.trade_date=c.trade_date
       AND m.adjustment_mode='qfq'
     WHERE c.symbol='SH600600' AND c.adjustment_mode='qfq' AND c.source=m.provider
       AND c.trade_date BETWEEN '2025-11-27' AND '2025-12-08' ORDER BY c.trade_date"""
print("SQL:",' '.join(s.split()))
for r in c.execute(s): print("   ",r)

print("\n### F3 CORRECTED headline: restatement rate on the ONLY rows that can show it")
s="""SELECT
  (SELECT COUNT(*) FROM daily_bar_cache c JOIN mh.daily_bars m ON m.symbol=c.symbol AND m.trade_date=c.trade_date AND m.adjustment_mode='qfq'
     JOIN mh.instruments i ON i.symbol=c.symbol WHERE c.adjustment_mode='qfq' AND c.source=m.provider AND c.close>0 AND m.close>0
       AND i.exchange<>'INDEX') all_same_provider_keys,
  (SELECT COUNT(*) FROM daily_bar_cache c JOIN mh.daily_bars m ON m.symbol=c.symbol AND m.trade_date=c.trade_date AND m.adjustment_mode='qfq'
     JOIN mh.instruments i ON i.symbol=c.symbol WHERE c.adjustment_mode='qfq' AND c.source=m.provider AND c.close>0 AND m.close>0
       AND i.exchange<>'INDEX' AND substr(c.updated_at,1,10)=substr(m.available_at,1,10)) same_vintage_dead_weight,
  (SELECT COUNT(*) FROM daily_bar_cache c JOIN mh.daily_bars m ON m.symbol=c.symbol AND m.trade_date=c.trade_date AND m.adjustment_mode='qfq'
     JOIN mh.instruments i ON i.symbol=c.symbol WHERE c.adjustment_mode='qfq' AND c.source=m.provider AND c.close>0 AND m.close>0
       AND i.exchange<>'INDEX' AND substr(c.updated_at,1,10)<>substr(m.available_at,1,10)) cross_vintage_keys,
  (SELECT SUM(abs(m.close/c.close-1.0)>0.01) FROM daily_bar_cache c JOIN mh.daily_bars m ON m.symbol=c.symbol AND m.trade_date=c.trade_date AND m.adjustment_mode='qfq'
     JOIN mh.instruments i ON i.symbol=c.symbol WHERE c.adjustment_mode='qfq' AND c.source=m.provider AND c.close>0 AND m.close>0
       AND i.exchange<>'INDEX' AND substr(c.updated_at,1,10)<>substr(m.available_at,1,10)) cross_vintage_gt1pct"""
print("SQL:",' '.join(s.split()))
r=c.execute(s).fetchone(); print("   ",r)
print(f"   THEIR rate = {6519}/{r[0]} = {100*6519/r[0]:.3f}%")
print(f"   MY   rate = {r[3]}/{r[2]} = {100*r[3]/r[2]:.3f}%   (their denominator carries {r[1]} rows that are the SAME snapshot)")
c.close()
