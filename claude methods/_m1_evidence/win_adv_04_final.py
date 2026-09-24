# -*- coding: utf-8 -*-
import sqlite3
MH = r"D:/codex-A股交易/market_history.sqlite3"; TL = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
mh = ro(MH); tl = ro(TL)
print("== 1. delist_date: EVERY row is SQL NULL (typeof), not blank-string ==")
q="SELECT COUNT(*) total, SUM(delist_date IS NULL) null_delist, COUNT(DISTINCT typeof(delist_date)) n_types, SUM(list_date IS NOT NULL AND trim(list_date)<>'') has_list FROM instruments"
print(q); print("  ->", mh.execute(q).fetchone())

print("\n== 2. universe snapshots vs the FIXED research window 2023-09-04..2026-09-04 ==")
q="""SELECT COUNT(*) total,
 SUM(snapshot_date BETWEEN '2023-09-04' AND '2026-09-04') in_window,
 SUM(snapshot_date < '2026-07-14') before_jul14,
 CAST(julianday('2026-09-04')-julianday('2023-09-04') AS INT) window_days,
 CAST(julianday(MIN(snapshot_date))-julianday('2023-09-04') AS INT) uncovered_days
FROM universe_snapshots"""
print(q); r=mh.execute(q).fetchone(); print("  ->", r)
print(f"  -> uncovered {r[4]}/{r[3]} days = {100*r[4]/r[3]:.1f}% of window has NO universe snapshot")

print("\n== 3. THE SMOKING GUN they missed: zero terminated price series ==")
q="""SELECT COUNT(*) syms,
 SUM(last_d >= '2026-06-29') alive_at_end,
 SUM(last_d <  '2026-06-29') terminated_early
FROM (SELECT symbol, MAX(trade_date) last_d FROM daily_bar_cache
      WHERE trade_date LIKE '____-__-__' GROUP BY symbol)"""
print(q); print("  ->", tl.execute(q).fetchone())

print("\n== 4. actual observable delisting EVENTS on disk (catalog churn) ==")
q="""SELECT COUNT(*) FROM universe_members WHERE snapshot_id=18
     AND symbol NOT IN (SELECT symbol FROM universe_members WHERE snapshot_id=94)"""
print(q); print("  -> removals 2026-07-16 -> 2026-09-04:", mh.execute(q).fetchone()[0])
q="SELECT symbol,status,provider FROM instruments WHERE status='inactive' AND provider LIKE 'akshare%'"
print(q); print("  ->", mh.execute(q).fetchall())

print("\n== 5. real span of the 'three-year' window ==")
for lbl,con,t in (("daily_bar_cache",tl,"daily_bar_cache"),("daily_bars",mh,"daily_bars")):
    q=f"SELECT MIN(trade_date),MAX(trade_date),COUNT(DISTINCT trade_date) FROM {t} WHERE trade_date LIKE '____-__-__'"
    print(f"  {lbl}: {q}"); print("   ->", con.execute(q).fetchone())
q="SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date>='2023-09-04' AND trade_date<'2024-04-09'"
print(q); print("  -> rows in first 218 days of window:", tl.execute(q).fetchone()[0])
mh.close(); tl.close()
