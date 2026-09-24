# -*- coding: utf-8 -*-
import sqlite3
HIST = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
c = ro(HIST); q = lambda s,a=(): c.execute(s,a).fetchall()

print("### Q1 full dump of universe_snapshots (all cols, no MIN/MAX shortcut)")
for r in q("SELECT id,universe_name,snapshot_date,provider,member_count,fetched_at,substr(metadata_json,1,160) FROM universe_snapshots ORDER BY snapshot_date"):
    print(r)

print("\n### Q2 snapshot_date FORMAT audit (string-vs-date bug hunt)")
print(q("""SELECT length(snapshot_date) AS len, COUNT(*),
        SUM(CASE WHEN snapshot_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN 1 ELSE 0 END) AS iso_ok,
        MIN(snapshot_date), MAX(snapshot_date)
        FROM universe_snapshots GROUP BY len"""))
print("date() parse check:", q("SELECT snapshot_date, date(snapshot_date) IS NULL AS unparseable FROM universe_snapshots GROUP BY snapshot_date"))

print("\n### Q3 distinct snapshot_date x universe_name (DISTINCT dates, not rows)")
print(q("SELECT universe_name, COUNT(*) rows_, COUNT(DISTINCT snapshot_date) distinct_dates, MIN(snapshot_date), MAX(snapshot_date) FROM universe_snapshots GROUP BY universe_name"))

print("\n### Q4 how many DISTINCT dates fall inside the research window")
print(q("""SELECT COUNT(DISTINCT snapshot_date) FROM universe_snapshots
           WHERE snapshot_date BETWEEN '2023-09-04' AND '2026-09-04'"""))
print("outside window:", q("SELECT COUNT(*) FROM universe_snapshots WHERE snapshot_date < '2023-09-04' OR snapshot_date > '2026-09-04'"))

print("\n### Q5 instruments: status x exchange x asset_type, and date-field population")
for r in q("SELECT status, exchange, asset_type, COUNT(*) FROM instruments GROUP BY status,exchange,asset_type ORDER BY 4 DESC"):
    print(r)
print("\nnon-active rows in full:", q("SELECT symbol,name,exchange,asset_type,status,list_date,delist_date FROM instruments WHERE status <> 'active'"))

print("\n### Q6 list_date / delist_date population (the auditor only tested delist_date)")
print(q("""SELECT COUNT(*) total,
  SUM(list_date IS NOT NULL AND trim(COALESCE(list_date,''))<>'') list_date_present,
  SUM(delist_date IS NOT NULL AND trim(COALESCE(delist_date,''))<>'') delist_date_present,
  MIN(NULLIF(trim(COALESCE(list_date,'')),'')), MAX(NULLIF(trim(COALESCE(list_date,'')),''))
  FROM instruments"""))
print("list_date present by exchange:", q("""SELECT exchange, COUNT(*),
  SUM(NULLIF(trim(COALESCE(list_date,'')),'') IS NOT NULL) FROM instruments GROUP BY exchange"""))
print("\ndelist_date empty-string vs NULL:", q("SELECT delist_date, COUNT(*) FROM instruments GROUP BY delist_date LIMIT 10"))
c.close()
