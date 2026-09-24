import sqlite3
OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
con = sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
q = lambda s,p=(): con.execute(s,p).fetchall()
def sec(t): print("\n"+"="*78+"\n"+t+"\n"+"="*78)

sec("A. WAS THE SYSTEM EVER RUNNING BEFORE 2026-06-30? earliest stamp per table")
names=[r[0] for r in q("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
found=[]
for t in names:
    cols=[c[1] for c in q(f"PRAGMA table_info('{t}')")]
    tc=[c for c in cols if c in ('created_at','received_ts','event_ts','started_at','recorded_at','decided_at','ts','timestamp')]
    if not tc: continue
    c=tc[0]
    try:
        n,mn,mx=q(f"SELECT COUNT(*),MIN({c}),MAX({c}) FROM '{t}' WHERE {c} IS NOT NULL")[0]
    except Exception: continue
    if n and mn: found.append((str(mn),t,c,n,str(mx)))
found.sort()
print(f"{'earliest':<26}{'table':<44}{'col':<14}{'rows':>10}  latest")
for mn,t,c,n,mx in found[:32]:
    print(f"{mn:<26}{t:<44}{c:<14}{n:>10,}  {mx}")

sec("B. LIVE-CAPTURE TABLES: realtime quotes and decisions")
for t,c in [("realtime_market_events","received_ts"),("realtime_market_events","event_ts"),
            ("forecast_decisions","created_at"),("forecast_outcomes","created_at")]:
    try: print(f"  {t}.{c}:", q(f"SELECT COUNT(*),MIN({c}),MAX({c}) FROM {t}")[0])
    except Exception as e: print(f"  {t}.{c}: {e}")

sec("C. HOW MANY DISTINCT CALENDAR DAYS DID THE SYSTEM EVER WRITE BARS ON?")
print("daily_bar_cache distinct created_at days:", q("SELECT COUNT(DISTINCT date(created_at)) FROM daily_bar_cache")[0])
print("daily_bar_cache distinct updated_at days:", q("SELECT COUNT(DISTINCT date(replace(updated_at,'T',' '))) FROM daily_bar_cache")[0])
print("\nrows per updated_at day:")
for r in q("SELECT date(replace(updated_at,'T',' ')) d, COUNT(*) n FROM daily_bar_cache GROUP BY d ORDER BY d"):
    print(f"   {r[0]}  n={r[1]:>9,}")

sec("D. TRADING SESSIONS IN WINDOW vs SESSIONS THE CACHE COULD HAVE WATCHED LIVE")
tds=q("""SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache
         WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
           AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'""")[0][0]
live=q("""SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache
          WHERE date(created_at)=trade_date""")[0][0]
near=q("""SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache
          WHERE julianday(date(created_at))-julianday(date(trade_date)) BETWEEN 0 AND 3""")[0][0]
print(f"  distinct trade_dates held in window : {tds}")
print(f"  trade_dates with ANY same-day row   : {live}  ({100.0*live/tds:.2f}%)")
print(f"  trade_dates with ANY <=3d row       : {near}  ({100.0*near/tds:.2f}%)")

sec("E. market_history available_at: is it a REAL point-in-time stamp or a copy of fetch time?")
con.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")
print("  rows where available_at == fetched_at:", q("SELECT COUNT(*) FROM mh.daily_bars WHERE available_at = fetched_at")[0])
print("  rows where available_at <> fetched_at:", q("SELECT COUNT(*) FROM mh.daily_bars WHERE available_at <> fetched_at")[0])
print("  distinct available_at values:", q("SELECT COUNT(DISTINCT available_at) FROM mh.daily_bars")[0])
print("  available_at vs trade_date same-day rows:",
   q("SELECT COUNT(*) FROM mh.daily_bars WHERE date(available_at)=trade_date")[0])
print("  mh.daily_bars trade_date span:", q("SELECT MIN(trade_date),MAX(trade_date),COUNT(*) FROM mh.daily_bars")[0])
con.close()
