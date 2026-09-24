# -*- coding: utf-8 -*-
import sqlite3
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
mh = ro(MH)
W0, W1 = "2023-09-04", "2026-09-04"
d = mh.execute("SELECT COUNT(*), COUNT(DISTINCT snapshot_date) FROM universe_snapshots").fetchone()
td = mh.execute("SELECT COUNT(DISTINCT trade_date) FROM daily_bars WHERE trade_date BETWEEN ? AND ?",(W0,W1)).fetchone()[0]
cov = mh.execute("SELECT COUNT(*) FROM (SELECT DISTINCT trade_date t FROM daily_bars WHERE trade_date BETWEEN ? AND ?)"
                 " WHERE t IN (SELECT snapshot_date FROM universe_snapshots)",(W0,W1)).fetchone()[0]
print(f"snapshot rows={d[0]}  DISTINCT snapshot dates={d[1]}")
print(f"calendar-day coverage : {d[1]}/1097 = {100*d[1]/1097:.2f}%   (auditor said 53/1097 = 4.83%)")
print(f"trading-day coverage  : {cov}/{td} = {100*cov/td:.2f}%")
print(f"uncovered calendar days: {1097-d[1]}  (auditor said 1044)")
print(f"uncovered trading days : {td-cov}")
ex = mh.execute("SELECT COUNT(*) FROM (SELECT symbol,MAX(trade_date) m FROM daily_bars GROUP BY symbol) WHERE m<'2026-01-01'").fetchone()[0]
n  = mh.execute("SELECT COUNT(DISTINCT symbol) FROM daily_bars").fetchone()[0]
ld = mh.execute("SELECT SUM(list_date IS NOT NULL), COUNT(*) FROM instruments").fetchone()
print(f"symbols in daily_bars={n}; symbols whose history ENDS before 2026 = {ex}  <-- zero exits in 3 years")
print(f"instruments with list_date = {ld[0]}/{ld[1]} = {100*ld[0]/ld[1]:.2f}%  <-- entry side IS reconstructible")
