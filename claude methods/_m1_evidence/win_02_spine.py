import sqlite3, datetime
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
c.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")
print("### calendar-ish tables in either DB")
for r in c.execute("SELECT 'TL', name FROM sqlite_master WHERE type='table' AND (name LIKE '%calendar%' OR name LIKE '%session%' OR name LIKE '%holiday%')"): print("   ", r)
for r in c.execute("SELECT 'MH', name FROM mh.sqlite_master WHERE type='table' AND (name LIKE '%calendar%' OR name LIKE '%session%' OR name LIKE '%holiday%')"): print("   ", r)

print("\n### full cache spine within window: first 60 sessions with distinct-symbol counts")
SQL_SPINE = """
SELECT d.trade_date, COUNT(DISTINCT d.symbol) AS n_sym
FROM daily_bar_cache d JOIN mh.instruments i ON i.symbol=d.symbol
WHERE d.trade_date BETWEEN '2023-09-04' AND '2026-09-04'
  AND d.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
GROUP BY d.trade_date ORDER BY d.trade_date"""
print("SQL:", " ".join(SQL_SPINE.split()))
rows = list(c.execute(SQL_SPINE))
print("total sessions in spine:", len(rows))
print("first session:", rows[0], " last session:", rows[-1])
for i, r in enumerate(rows[:60]): print(f"   [{i+1:3d}] {r[0]}  {r[1]:5d}")
print("   ...")
for i, r in enumerate(rows[-5:]): print(f"   [{len(rows)-4+i:3d}] {r[0]}  {r[1]:5d}")

import statistics
ns = [r[1] for r in rows]
print("\nsymbol-count per session: min=%d p10=%d median=%d p90=%d max=%d" % (
    min(ns), sorted(ns)[len(ns)//10], statistics.median(ns), sorted(ns)[len(ns)*9//10], max(ns)))
low = [r for r in rows if r[1] < 3000]
print("sessions with <3000 symbols reporting: %d" % len(low))
for r in low[:60]: print("   LOW", r)
