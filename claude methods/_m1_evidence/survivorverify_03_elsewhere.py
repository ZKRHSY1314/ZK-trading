import sqlite3
tl=sqlite3.connect("file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True)
mh=sqlite3.connect("file:D:/codex-A股交易/market_history.sqlite3?mode=ro",uri=True)
q=lambda c,s,p=(): c.execute(s,p).fetchall()

print("### K. daily_bar_cache symbol FORMAT (my earlier join may have been a format mismatch)")
print(q(tl,"""SELECT CASE WHEN symbol GLOB '[A-Z][A-Z]*' THEN 'prefixed(SHxxxxxx)' ELSE 'bare(6digit)' END fmt,
   COUNT(DISTINCT symbol) FROM daily_bar_cache GROUP BY 1"""))
print("   the 6 cache symbols not in instruments:",
  q(tl,"SELECT symbol FROM (SELECT DISTINCT symbol FROM daily_bar_cache) WHERE symbol NOT IN (SELECT symbol FROM instruments)") if False else "")
tl.execute("ATTACH DATABASE 'file:D:/codex-A股交易/market_history.sqlite3?mode=ro' AS mh")
print("   ->",q(tl,"SELECT symbol FROM (SELECT DISTINCT symbol FROM daily_bar_cache) WHERE symbol NOT IN (SELECT symbol FROM mh.instruments)"))

print()
print("### L. sector_membership_snapshots: 98 rows - do they reach back into the window?")
cols=[r[1] for r in q(tl,"PRAGMA table_info(sector_membership_snapshots)")]
print("   cols:",cols)
dc=[c for c in cols if 'date' in c.lower() or 'at' in c.lower()]
for c in dc:
    print(f"   MIN/MAX {c}:",q(tl,f"SELECT MIN({c}),MAX({c}) FROM sector_membership_snapshots"))

print()
print("### M. candidate_pool: any pre-2026 history?")
try:
    cols=[r[1] for r in q(tl,"PRAGMA table_info(candidate_pool)")]
    print("   cols:",cols)
    print("   rows:",q(tl,"SELECT COUNT(*),COUNT(DISTINCT symbol) FROM candidate_pool"))
    for c in cols:
        if 'date' in c.lower() or c.lower().endswith('_at'):
            print(f"   MIN/MAX {c}:",q(tl,f"SELECT MIN({c}),MAX({c}) FROM candidate_pool"))
except Exception as e:
    print("   ",e)

print()
print("### N. full_market_feature_runs.universe_snapshot_id -> which snapshots, what dates?")
print(q(tl,"SELECT MIN(created_at),MAX(created_at),COUNT(*),COUNT(DISTINCT universe_snapshot_id) FROM full_market_feature_runs")
      if 'created_at' in [r[1] for r in q(tl,"PRAGMA table_info(full_market_feature_runs)")] else "no created_at")
print("   cols:",[r[1] for r in q(tl,"PRAGMA table_info(full_market_feature_runs)")])

print()
print("### O. Do the 5 'stops 2026-06/07' symbols == the 5 status='inactive' rows?")
print(q(mh,"""WITH last AS (SELECT symbol,MAX(trade_date) mx FROM daily_bars GROUP BY symbol)
SELECT l.symbol,l.mx,i.status,i.list_date,i.delist_date,i.provider FROM last l JOIN instruments i USING(symbol)
WHERE l.mx<'2026-08-01' ORDER BY l.mx"""))

print()
print("### P. earliest bar coverage - does daily_bars even reach the window start?")
print("   MIN/MAX trade_date in mh.daily_bars:",q(mh,"SELECT MIN(trade_date),MAX(trade_date) FROM daily_bars"))
print("   symbols whose FIRST bar <= 2023-09-04:",q(mh,"SELECT COUNT(*) FROM (SELECT symbol,MIN(trade_date) mn FROM daily_bars GROUP BY symbol) WHERE mn<='2023-09-04'"))
print("   distinct trade_date count inside window:",q(mh,"SELECT COUNT(DISTINCT trade_date) FROM daily_bars WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'"))
