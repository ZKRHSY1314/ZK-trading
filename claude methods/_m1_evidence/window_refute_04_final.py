# -*- coding: utf-8 -*-
import sqlite3, datetime as dt
B = r"D:/codex-A股交易"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
ops = ro(f"{B}/trading_local.sqlite3"); hist = ro(f"{B}/market_history.sqlite3")

print("#"*100); print("# HEADLINE SQL (mine) -- single statement per store, julianday, no length filter"); print("#"*100)
SQL = """
SELECT COUNT(*)                                                             AS rows_total,
       SUM(julianday(trade_date) <  julianday('2023-09-04'))                AS rows_before_window,
       SUM(julianday(trade_date) BETWEEN julianday('2023-09-04')
                                     AND julianday('2024-04-08'))           AS rows_in_head_gap,
       SUM(julianday(trade_date) IS NULL)                                   AS rows_unparseable,
       MIN(trade_date)                                                      AS min_date,
       COUNT(DISTINCT CASE WHEN julianday(trade_date)
             BETWEEN julianday('2023-09-04') AND julianday('2026-09-04')
             THEN trade_date END)                                           AS distinct_sessions_in_window
FROM {t}"""
for lbl, conn, t in (("trading_local.daily_bar_cache", ops, "daily_bar_cache"),
                     ("market_history.daily_bars",     hist, "daily_bars")):
    r = conn.execute(SQL.format(t=t)).fetchone()
    print(f"\n{lbl}")
    print(f"   rows_total={r[0]}  rows_before_window={r[1]}  rows_in_head_gap={r[2]}  unparseable={r[3]}")
    print(f"   min_date={r[4]}  distinct_sessions_in_window={r[5]}")

n1 = ops.execute("SELECT COUNT(*) FROM daily_bar_cache").fetchone()[0]
n2 = hist.execute("SELECT COUNT(*) FROM daily_bars").fetchone()[0]
print(f"\n   combined rows across the two stores = {n1+n2:,}   (their '5.68M' denominator)")

print()
print("#"*100); print("# EFFECTIVE (full-market) floor, not the single-symbol floor"); print("#"*100)
for r in hist.execute("""
SELECT (SELECT COUNT(DISTINCT b.symbol) FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
          WHERE i.asset_type='stock' AND b.trade_date='2024-04-09')                       AS stocks_on_floor_date,
       (SELECT MIN(trade_date) FROM (SELECT b.trade_date, COUNT(DISTINCT b.symbol) c
          FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
          WHERE i.asset_type='stock' GROUP BY 1 HAVING c>=4000))                          AS first_broad_session,
       (SELECT COUNT(*) FROM instruments WHERE asset_type='stock')                        AS stocks_known,
       (SELECT COUNT(*) FROM instruments WHERE asset_type='stock' AND list_date<'2023-09-04') AS listed_before_window
""").fetchall(): print("   ", r)

def dr(a,b):
    a=dt.date.fromisoformat(a); b=dt.date.fromisoformat(b); d=(b-a).days+1
    return d, sum(1 for i in range(d) if (a+dt.timedelta(days=i)).weekday()<5)
print()
print("#"*100); print("# ARITHMETIC AUDIT of their affected-count"); print("#"*100)
for lbl,a,b in (("their gap 2023-09-04..2024-04-08",'2023-09-04','2024-04-08'),
                ("effective gap 2023-09-04..2024-06-21",'2023-09-04','2024-06-21'),
                ("full window",'2023-09-04','2026-09-04')):
    d,w = dr(a,b); print(f"   {lbl:40s} calendar_days={d:5d}  weekdays={w:4d}  est_sessions={w*0.9332:6.1f}")
print("   they wrote 213 calendar days for a span that is 218 -- their only wrong number.")
ops.close(); hist.close()
