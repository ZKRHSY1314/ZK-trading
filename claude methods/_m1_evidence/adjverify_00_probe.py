import sqlite3, os
OP = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"
def ro(p):
    c = sqlite3.connect(f"file:{p.replace(os.sep,'/')}?mode=ro", uri=True)
    return c
op = ro(OP); mh = ro(MH)
def q(c,s,n=40):
    cur=c.execute(s); rows=cur.fetchmany(n)
    return [d[0] for d in cur.description], rows
print("=== daily_bar_cache symbol formats (sample) ===")
h,r = q(op,"SELECT symbol, trade_date, close, source, quality_status, adjustment_mode, volume_unit FROM daily_bar_cache WHERE trade_date='2024-08-13' LIMIT 8")
print(h)
for x in r: print(x)
print()
print("=== symbol prefix distribution on 2024-08-13 ===")
h,r=q(op,"""SELECT substr(symbol,1,2) AS pfx, length(symbol) AS L, COUNT(*) c
FROM daily_bar_cache WHERE trade_date='2024-08-13' GROUP BY 1,2 ORDER BY c DESC""",60)
for x in r: print(x)
print()
print("=== quality_status on 2024-08-13 ===")
h,r=q(op,"SELECT quality_status, source, COUNT(*) FROM daily_bar_cache WHERE trade_date='2024-08-13' GROUP BY 1,2 ORDER BY 3 DESC",30)
for x in r: print(x)
print()
print("=== market_history.daily_bars symbol format ===")
h,r=q(mh,"SELECT symbol,trade_date,close,adjustment_mode,provider,available_at FROM daily_bars WHERE trade_date='2024-08-13' LIMIT 8")
print(h)
for x in r: print(x)
print()
print("=== mh adjustment_mode x provider on 2024-08-13 ===")
h,r=q(mh,"SELECT adjustment_mode, provider, COUNT(*) FROM daily_bars WHERE trade_date='2024-08-13' GROUP BY 1,2 ORDER BY 3 DESC",30)
for x in r: print(x)
print()
print("=== mh distinct trade_dates near 2024-08 ===")
h,r=q(mh,"SELECT trade_date, COUNT(*) FROM daily_bars WHERE trade_date BETWEEN '2024-08-05' AND '2024-08-20' GROUP BY 1 ORDER BY 1",30)
for x in r: print(x)
