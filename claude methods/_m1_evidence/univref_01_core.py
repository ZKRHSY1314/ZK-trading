# -*- coding: utf-8 -*-
import sqlite3
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
W0, W1 = "2023-09-04", "2026-09-04"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
mh, tl = ro(MH), ro(TL)
def q(c, s, *a):
    return c.execute(s, a).fetchall()
def show(title, c, s, *a):
    print("\n### " + title)
    print("SQL: " + " ".join(s.split()))
    for r in q(c, s, *a): print("   ", r)

print("="*78); print("A. universe_snapshots -- DISTINCT DATES, not day-span")
show("A1 rows / distinct dates / range", mh,
 "SELECT COUNT(*) AS rows, COUNT(DISTINCT snapshot_date) AS distinct_dates,"
 " MIN(snapshot_date), MAX(snapshot_date) FROM universe_snapshots")
show("A2 every snapshot row verbatim", mh,
 "SELECT id, universe_name, snapshot_date, provider, member_count, substr(fetched_at,1,19)"
 " FROM universe_snapshots ORDER BY snapshot_date, id")
show("A3 typeof(snapshot_date) + length -- string/date bug check", mh,
 "SELECT typeof(snapshot_date), length(snapshot_date), COUNT(*)"
 " FROM universe_snapshots GROUP BY 1,2")
show("A4 snapshots INSIDE window by string compare", mh,
 "SELECT COUNT(*) FROM universe_snapshots WHERE snapshot_date>=? AND snapshot_date<=?", W0, W1)
show("A5 snapshots BEFORE window start (warm-up universe?)", mh,
 "SELECT COUNT(*) FROM universe_snapshots WHERE snapshot_date < ?", W0)
show("A6 members: distinct symbols per snapshot, and total distinct", mh,
 "SELECT s.snapshot_date, s.universe_name, COUNT(m.symbol) AS member_rows,"
 " COUNT(DISTINCT m.symbol) AS distinct_syms FROM universe_snapshots s"
 " LEFT JOIN universe_members m ON m.snapshot_id=s.id GROUP BY s.id ORDER BY s.snapshot_date")
show("A7 distinct symbols across ALL snapshots (union)", mh,
 "SELECT COUNT(DISTINCT symbol) FROM universe_members")

print("\n"+"="*78); print("B. instruments -- is list_date a usable reconstruction path?")
show("B1 status x asset_type x exchange census", mh,
 "SELECT status, asset_type, exchange, COUNT(*) FROM instruments GROUP BY 1,2,3 ORDER BY 4 DESC")
show("B2 delist_date population (the auditor's core claim)", mh,
 "SELECT COUNT(*) AS total, SUM(delist_date IS NOT NULL) AS has_delist,"
 " SUM(delist_date IS NULL) AS null_delist,"
 " SUM(delist_date IS NOT NULL AND trim(COALESCE(delist_date,''))<>'') AS has_nonblank_delist"
 " FROM instruments")
show("B3 list_date population, EXCLUDING indices", mh,
 "SELECT COUNT(*) AS non_index_instruments,"
 " SUM(list_date IS NOT NULL AND trim(COALESCE(list_date,''))<>'') AS has_list_date,"
 " MIN(NULLIF(trim(COALESCE(list_date,'')),'')), MAX(NULLIF(trim(COALESCE(list_date,'')),''))"
 " FROM instruments WHERE exchange<>'INDEX'")
show("B4 list_date INSIDE window = IPOs the listing-side filter would catch", mh,
 "SELECT COUNT(*) FROM instruments WHERE exchange<>'INDEX' AND list_date>=? AND list_date<=?", W0, W1)
show("B5 typeof/length of list_date", mh,
 "SELECT typeof(list_date), length(list_date), COUNT(*) FROM instruments GROUP BY 1,2")
