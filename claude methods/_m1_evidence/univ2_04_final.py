# -*- coding: utf-8 -*-
import sqlite3
from collections import Counter
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
mh = ro(MH); mh.row_factory = sqlite3.Row
tl = ro(TL); tl.row_factory = sqlite3.Row

print("### P. TIMELINE-PROXY TEST: can the 5 delistings be dated after all?")
print("    last real bar vs the undated status-flip stamp")
for r in mh.execute("""
    SELECT i.symbol, i.status, i.delist_date, i.updated_at,
           MAX(b.trade_date) AS last_bar, MAX(b.available_at) AS last_available_at,
           COUNT(b.trade_date) AS n_bars
    FROM instruments i LEFT JOIN daily_bars b ON b.symbol = i.symbol
    WHERE i.status <> 'active'
    GROUP BY i.symbol ORDER BY last_bar
""").fetchall():
    d = dict(r)
    print(f"   {d['symbol']}: last_bar={d['last_bar']}  flip(updated_at)={d['updated_at'][:10]}  "
          f"delist_date={d['delist_date']}  n_bars={d['n_bars']}")

print("\n### Q. SURVIVORSHIP SIGNATURE: last-bar year for EVERY symbol, both stores")
print("    (a genuine panel would show delistings scattered across 2024 and 2025)")
for label, con, tbl, dcol in (("MH daily_bars", mh, "daily_bars", "trade_date"),
                              ("TL daily_bar_cache", tl, "daily_bar_cache", "trade_date")):
    rows = con.execute(f"""
        SELECT SUBSTR(last_bar,1,4) AS yr, COUNT(*) AS n_symbols FROM (
            SELECT symbol, MAX({dcol}) AS last_bar FROM {tbl}
            WHERE LENGTH({dcol})=10 GROUP BY symbol
        ) GROUP BY yr ORDER BY yr
    """).fetchall()
    print(f"   {label}: " + ", ".join(f"{r['yr']}={r['n_symbols']}" for r in rows))

print("\n### R. WINDOW COVERAGE of the delisting question")
print("    research window 2023-09-04..2026-09-04; earliest bar anywhere:")
print("    MH daily_bars  min =", mh.execute("SELECT MIN(trade_date) FROM daily_bars WHERE LENGTH(trade_date)=10").fetchone()[0])
print("    TL daily_bars  min =", tl.execute("SELECT MIN(trade_date) FROM daily_bar_cache WHERE LENGTH(trade_date)=10").fetchone()[0])
print("    instruments first created_at =", mh.execute("SELECT MIN(created_at) FROM instruments").fetchone()[0])
print("    -> months of the window with NO catalog at all: 2023-09-04 .. 2026-07-15")

print("\n### S. list_date coverage (the other half of a survivorship reconstruction)")
for r in mh.execute("""SELECT status,
    COUNT(*) n, SUM(CASE WHEN list_date IS NULL THEN 1 ELSE 0 END) null_list,
    MIN(list_date) mn, MAX(list_date) mx FROM instruments GROUP BY status"""):
    print("   ", dict(r))
print("    listings dated INSIDE window (new-listing evidence that DOES exist):")
print("   ", dict(mh.execute("SELECT COUNT(*) n FROM instruments "
      "WHERE list_date BETWEEN '2023-09-04' AND '2026-09-04'").fetchone()))
mh.close(); tl.close()
