import sqlite3, json
MH="file:D:/codex-A股交易/market_history.sqlite3?mode=ro"
TL="file:D:/codex-A股交易/trading_local.sqlite3?mode=ro"
mh=sqlite3.connect(MH,uri=True); tl=sqlite3.connect(TL,uri=True)

def q(c,s,p=()):
    return c.execute(s,p).fetchall()

print("### A. Which tables in EITHER db carry list/delist/status/universe columns?")
for tag,c in (("market_history",mh),("trading_local",tl)):
    hits=[]
    for (n,) in q(c,"SELECT name FROM sqlite_master WHERE type='table'"):
        try:
            cols=[r[1] for r in q(c,f'PRAGMA table_info("{n}")')]
        except Exception:
            continue
        want=[x for x in cols if any(k in x.lower() for k in ("delist","list_date","listing","ipo","status","universe","member","snapshot"))]
        if want:
            try: cnt=q(c,f'SELECT COUNT(*) FROM "{n}"')[0][0]
            except Exception: cnt="?"
            hits.append((n,cnt,want))
    print(f"-- {tag}:")
    for n,cnt,w in sorted(hits): print(f"   {n:<45} rows={cnt:<10} cols={w}")

print()
print("### B. instruments denominator decomposed (INDEX must not count as a stock)")
print(q(mh,"""SELECT exchange, asset_type, COUNT(*) n,
       SUM(CASE WHEN list_date IS NOT NULL AND trim(list_date)<>'' THEN 1 ELSE 0 END) has_list,
       SUM(CASE WHEN delist_date IS NOT NULL AND trim(delist_date)<>'' THEN 1 ELSE 0 END) has_delist
       FROM instruments GROUP BY 1,2 ORDER BY 1,2"""))

print()
print("### C. the 5 status<>'active' rows verbatim")
for r in q(mh,"SELECT symbol,name,exchange,asset_type,board,list_date,delist_date,status,provider,fetched_at FROM instruments WHERE status<>'active'"):
    print("   ",r)

print()
print("### D. list_date usable range? (can we at least reconstruct the NEW-LISTING side?)")
print(q(mh,"""SELECT COUNT(*) n, MIN(list_date), MAX(list_date),
       SUM(CASE WHEN length(trim(coalesce(list_date,'')))=10 THEN 1 ELSE 0 END) wellformed
       FROM instruments WHERE exchange<>'INDEX'"""))
print("   listed AFTER window start (2023-09-04) i.e. IPO inside window:",
  q(mh,"SELECT COUNT(*) FROM instruments WHERE exchange<>'INDEX' AND length(trim(coalesce(list_date,'')))=10 AND list_date>'2023-09-04'"))
print("   listed on/before window start:",
  q(mh,"SELECT COUNT(*) FROM instruments WHERE exchange<>'INDEX' AND length(trim(coalesce(list_date,'')))=10 AND list_date<='2023-09-04'"))

print()
print("### E. universe_snapshots FULL dump (adversarial: is snapshot_date an as-of date they misread?)")
for r in q(mh,"SELECT id,universe_name,snapshot_date,provider,fetched_at,member_count,substr(metadata_json,1,200) FROM universe_snapshots ORDER BY snapshot_date"):
    print("   ",r)
print("   MIN/MAX snapshot_date via string AND via date():",
  q(mh,"SELECT MIN(snapshot_date),MAX(snapshot_date),MIN(date(snapshot_date)),MAX(date(snapshot_date)) FROM universe_snapshots"))
print("   any snapshot inside 2023-09-04..2026-06-30:",
  q(mh,"SELECT COUNT(*) FROM universe_snapshots WHERE date(snapshot_date) BETWEEN '2023-09-04' AND '2026-06-30'"))
print("   distinct universe_name:", q(mh,"SELECT universe_name,COUNT(*),COUNT(DISTINCT snapshot_date) FROM universe_snapshots GROUP BY 1"))
