import sqlite3, sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
tl, mh = ro(TL), ro(MH)
a, b = tl.cursor(), mh.cursor()

print("### 1. trade_date FORMAT CENSUS (do NOT assume ISO; string MIN can be fooled)")
for lbl, cur, tbl in (("cache", a, "daily_bar_cache"), ("mh", b, "daily_bars")):
    q = f"SELECT length(trade_date) AS L, COUNT(*) FROM {tbl} GROUP BY L ORDER BY L"
    print(f" [{lbl}] length histogram:", cur.execute(q).fetchall())
    # anything that is NOT strictly YYYY-MM-DD digits
    q2 = (f"SELECT trade_date, COUNT(*) FROM {tbl} WHERE trade_date NOT GLOB "
          f"'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' GROUP BY trade_date ORDER BY 2 DESC LIMIT 20")
    bad = cur.execute(q2).fetchall()
    print(f" [{lbl}] NON-ISO trade_date values (top20):", bad if bad else "NONE")
    q3 = f"SELECT COUNT(*) FROM {tbl} WHERE trade_date IS NULL"
    print(f" [{lbl}] NULL trade_date:", cur.execute(q3).fetchone()[0])

print()
print("### 2. TRUE MIN/MAX over ISO-VALID rows only (my own filter, not theirs)")
GL = "trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"
for lbl, cur, tbl in (("cache", a, "daily_bar_cache"), ("mh", b, "daily_bars")):
    q = (f"SELECT MIN(trade_date), MAX(trade_date), COUNT(*), COUNT(DISTINCT symbol), "
         f"COUNT(DISTINCT trade_date) FROM {tbl} WHERE {GL}")
    print(f" [{lbl}]", cur.execute(q).fetchone())
    # date() cast cross-check: does julianday parse agree with string order?
    q = (f"SELECT MIN(julianday(trade_date)), MAX(julianday(trade_date)) FROM {tbl} WHERE {GL}")
    jd = cur.execute(q).fetchone()
    q = (f"SELECT date(MIN(julianday(trade_date))), date(MAX(julianday(trade_date))) FROM {tbl} WHERE {GL}")
    print(f" [{lbl}] julianday-derived min/max:", cur.execute(q).fetchone())

print()
print("### 3. ROWS STRICTLY BEFORE WINDOW START 2023-09-04 -- three independent formulations")
for lbl, cur, tbl in (("cache", a, "daily_bar_cache"), ("mh", b, "daily_bars")):
    r1 = cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE {GL} AND trade_date < '2023-09-04'").fetchone()[0]
    r2 = cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE {GL} AND julianday(trade_date) < julianday('2023-09-04')").fetchone()[0]
    r3 = cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE {GL} AND CAST(replace(trade_date,'-','') AS INTEGER) < 20230904").fetchone()[0]
    r4 = cur.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    print(f" [{lbl}] string<: {r1}   julianday<: {r2}   int<: {r3}   (total rows incl. malformed: {r4})")

print()
print("### 4. IN-WINDOW rows 2023-09-04..2026-09-04 inclusive (BETWEEN, inclusive both ends)")
for lbl, cur, tbl in (("cache", a, "daily_bar_cache"), ("mh", b, "daily_bars")):
    q = (f"SELECT COUNT(*), COUNT(DISTINCT symbol), COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date) "
         f"FROM {tbl} WHERE {GL} AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'")
    print(f" [{lbl}]", cur.execute(q).fetchone())
    q = (f"SELECT COUNT(*) FROM {tbl} WHERE {GL} AND trade_date > '2026-09-04'")
    print(f" [{lbl}] rows AFTER window end:", cur.execute(q).fetchone()[0])
tl.close(); mh.close()
