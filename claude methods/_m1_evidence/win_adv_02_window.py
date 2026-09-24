# -*- coding: utf-8 -*-
import sqlite3
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
def hdr(t): print("\n"+"="*74+"\n"+t+"\n"+"="*74)
mh = ro(MH); tl = ro(TL)

hdr("H. EXACT universe_snapshots contents (checking the auditor's sub-window choice)")
q = "SELECT id,universe_name,snapshot_date,provider,member_count,fetched_at FROM universe_snapshots ORDER BY snapshot_date"
print("SQL:", q)
for r in mh.execute(q): print("   ", r)
q2 = """SELECT
  SUM(CASE WHEN snapshot_date BETWEEN '2023-09-04' AND '2026-09-04' THEN 1 ELSE 0 END) in_research_window,
  SUM(CASE WHEN snapshot_date BETWEEN '2023-09-04' AND '2026-06-30' THEN 1 ELSE 0 END) in_their_subwindow,
  MIN(snapshot_date), MAX(snapshot_date), COUNT(*)
FROM universe_snapshots"""
print("SQL:", q2)
print("   ", mh.execute(q2).fetchone())
print("   julianday span of research window (days):",
      mh.execute("SELECT CAST(julianday('2026-09-04')-julianday('2023-09-04') AS INT)").fetchone()[0])
print("   days from first snapshot to window end:",
      mh.execute("SELECT CAST(julianday('2026-09-04')-julianday(MIN(snapshot_date)) AS INT) FROM universe_snapshots").fetchone()[0])

hdr("I. per-snapshot member counts -- does membership CHANGE (would prove point-in-time universe)?")
q = """SELECT s.snapshot_date, s.universe_name, COUNT(m.symbol) n
FROM universe_snapshots s LEFT JOIN universe_members m ON m.snapshot_id=s.id
GROUP BY s.id ORDER BY s.snapshot_date"""
print("SQL:", q)
for r in mh.execute(q): print("   ", r)

hdr("J. WINDOW COVERAGE: actual date extent of each bar store")
for label, con, tbl in (("trading_local.daily_bar_cache", tl, "daily_bar_cache"),
                        ("market_history.daily_bars", mh, "daily_bars")):
    q = f"SELECT MIN(trade_date),MAX(trade_date),COUNT(*),COUNT(DISTINCT trade_date) FROM {tbl} WHERE length(trade_date)=10 AND trade_date LIKE '____-__-__'"
    print(f"SQL[{label}]:", q)
    print("   valid-date rows:", con.execute(q).fetchone())
    q2 = f"SELECT COUNT(*) FROM {tbl} WHERE NOT (length(trade_date)=10 AND trade_date LIKE '____-__-__')"
    print("   INVALID-date rows:", con.execute(q2).fetchone()[0], " SQL:", q2)
    q3 = f"SELECT COUNT(*) FROM {tbl} WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'"
    print("   rows inside research window:", con.execute(q3).fetchone()[0])
    q4 = f"SELECT COUNT(*) FROM {tbl} WHERE trade_date < '2023-09-04'"
    print("   rows BEFORE window (warm-up):", con.execute(q4).fetchone()[0])

hdr("K. distinct trade_date per year -- where does history actually begin?")
q = """SELECT substr(trade_date,1,4) y, COUNT(DISTINCT trade_date) d, COUNT(*) rows, COUNT(DISTINCT symbol) syms
FROM daily_bar_cache WHERE trade_date LIKE '____-__-__' GROUP BY 1 ORDER BY 1"""
print("SQL:", q)
for r in tl.execute(q): print("   ", r)
q = """SELECT substr(trade_date,1,4) y, COUNT(DISTINCT trade_date) d, COUNT(*) rows, COUNT(DISTINCT symbol) syms
FROM daily_bars WHERE trade_date LIKE '____-__-__' GROUP BY 1 ORDER BY 1"""
print("SQL(market_history.daily_bars):", q)
for r in mh.execute(q): print("   ", r)

hdr("L. the 'ERROR' trade_date symbol")
q = "SELECT symbol, trade_date, COUNT(*) FROM daily_bar_cache WHERE trade_date NOT LIKE '____-__-__' GROUP BY 1,2 LIMIT 20"
print("SQL:", q)
for r in tl.execute(q): print("   ", r)
mh.close(); tl.close()
