import sqlite3, sys
OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
con = sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
con.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")
q = lambda s,p=(): con.execute(s,p).fetchall()
def sec(t): print("\n"+"="*78+"\n"+t+"\n"+"="*78)

sec("1. RAW SHAPE OF daily_bar_cache (my own count, no assumptions)")
print(q("SELECT COUNT(*) total, COUNT(DISTINCT symbol) syms, MIN(trade_date), MAX(trade_date) FROM daily_bar_cache"))
print("non-ISO trade_date rows:", q("SELECT trade_date, COUNT(*) FROM daily_bar_cache WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' GROUP BY 1"))
print("rows OUTSIDE window 2023-09-04..2026-09-04 (valid dates only):",
  q("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND (trade_date < '2023-09-04' OR trade_date > '2026-09-04')"))
print("rows INSIDE window:",
  q("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'"))
print("window part with ZERO rows: 2023-09-04..2024-04-08 count =",
  q("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2024-04-08'"))

sec("2. created_at DOMAIN: is it a capture stamp or a rebuild stamp?")
print("min/max/nulls:", q("SELECT MIN(created_at), MAX(created_at), SUM(created_at IS NULL) FROM daily_bar_cache"))
print("distinct created_at DAYS:", q("SELECT COUNT(DISTINCT substr(created_at,1,10)) FROM daily_bar_cache"))
print("\nrows per created_at day (ALL days, this is the whole write history):")
for r in q("SELECT substr(created_at,1,10) d, COUNT(*) n, MIN(trade_date), MAX(trade_date) FROM daily_bar_cache GROUP BY d ORDER BY d"):
    print(f"   {r[0]}  n={r[1]:>9,}  trade_date {r[2]} .. {r[3]}")

sec("3. THE TAUTOLOGY TEST: can a pre-2026-06-30 bar EVER be same-day?")
print("rows with trade_date < 2026-06-30 (created_at floor):",
  q("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND trade_date < '2026-06-30'"))
print("...of those, how many COULD be same-day given created_at>=2026-06-30? -> 0 by construction")
print("rows with trade_date >= 2026-06-30 (the only rows where 'live' is even possible):",
  q("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date >= '2026-06-30' AND trade_date <= '2026-09-04'"))

sec("4. MY OWN LAG BUCKETS - integer day arithmetic, date() not substr, NULL-safe")
rows = q("""
SELECT CASE
  WHEN created_at IS NULL THEN 'Z_null_created_at'
  WHEN CAST(julianday(date(created_at)) - julianday(date(trade_date)) AS INTEGER) < 0 THEN 'X_negative'
  WHEN CAST(julianday(date(created_at)) - julianday(date(trade_date)) AS INTEGER) = 0 THEN 'A_same_day'
  WHEN CAST(julianday(date(created_at)) - julianday(date(trade_date)) AS INTEGER) <= 3 THEN 'B_1to3d'
  WHEN CAST(julianday(date(created_at)) - julianday(date(trade_date)) AS INTEGER) <= 30 THEN 'C_4to30d'
  WHEN CAST(julianday(date(created_at)) - julianday(date(trade_date)) AS INTEGER) <= 90 THEN 'D_31to90d'
  WHEN CAST(julianday(date(created_at)) - julianday(date(trade_date)) AS INTEGER) <= 365 THEN 'E_91to365d'
  WHEN CAST(julianday(date(created_at)) - julianday(date(trade_date)) AS INTEGER) <= 730 THEN 'F_1to2y'
  ELSE 'G_over2y' END bucket,
  COUNT(*) n, COUNT(DISTINCT symbol) syms, MIN(trade_date), MAX(trade_date)
FROM daily_bar_cache
WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
  AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'
GROUP BY bucket ORDER BY bucket""")
tot = sum(r[1] for r in rows)
for b,n,s,a,z in rows: print(f"   {b:<18} n={n:>9,} ({100.0*n/tot:6.3f}%)  syms={s:>5}  {a}..{z}")
print(f"   TOTAL            n={tot:,}")
live = sum(n for b,n,s,a,z in rows if b in ('A_same_day','B_1to3d'))
print(f"\n   <=3d 'live-ish' = {live:,} = {100.0*live/tot:.4f}%   backfilled = {tot-live:,} = {100.0*(tot-live)/tot:.4f}%")

sec("5. TIMEZONE TRAP: created_at is SQLite CURRENT_TIMESTAMP = UTC; updated_at is python local (UTC+8)")
print("sample created_at/updated_at pairs:", q("SELECT created_at, updated_at FROM daily_bar_cache LIMIT 3"))
print("updated_at min/max:", q("SELECT MIN(updated_at), MAX(updated_at) FROM daily_bar_cache"))
print("rows where updated_at (normalized) is EARLIER than created_at  -> proves created_at was RESET:",
  q("""SELECT COUNT(*) FROM daily_bar_cache
       WHERE updated_at IS NOT NULL AND created_at IS NOT NULL
         AND replace(updated_at,'T',' ') < created_at"""))
print("rows where updated_at is earlier than created_at by MORE than 12h (beyond any tz offset):",
  q("""SELECT COUNT(*) FROM daily_bar_cache
       WHERE updated_at IS NOT NULL AND created_at IS NOT NULL
         AND julianday(replace(updated_at,'T',' ')) < julianday(created_at) - 0.5"""))
print("rows where updated_at > created_at by >1 day (row was REFRESHED after insert):",
  q("""SELECT COUNT(*) FROM daily_bar_cache
       WHERE julianday(replace(updated_at,'T',' ')) > julianday(created_at) + 1.0"""))

sec("6. SAME-DAY ROWS: are they real live captures, or a UTC/CST boundary artifact?")
for r in q("""SELECT substr(created_at,1,10) cd, trade_date, COUNT(*) n, MIN(created_at), MAX(created_at)
              FROM daily_bar_cache WHERE substr(created_at,1,10)=trade_date
              GROUP BY cd, trade_date ORDER BY trade_date"""):
    print("   ", r)

sec("7. DO INDICES INFLATE THIS? symbol shape + instruments join")
print("symbol samples:", [r[0] for r in q("SELECT DISTINCT symbol FROM daily_bar_cache LIMIT 12")])
print("symbols in dbc matching index-ish patterns:",
  q("""SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache
       WHERE symbol GLOB 'sh00[0-9]*' OR symbol GLOB 'sz39[0-9]*' OR symbol LIKE '%.SH' OR symbol LIKE '%INDEX%'"""))
try:
    print("instruments exchange breakdown:", q("SELECT exchange, COUNT(*) FROM mh.instruments GROUP BY 1"))
    print("dbc symbols that are INDEX per instruments:",
      q("""SELECT COUNT(*) FROM daily_bar_cache b JOIN mh.instruments i ON i.symbol=b.symbol WHERE i.exchange='INDEX'"""))
except Exception as e:
    print("instruments join failed:", e)

sec("8. INDEPENDENT PIT EVIDENCE ELSEWHERE - did capture predate 2026-06-30?")
try:
    print("mh.ingest_runs time span:", q("SELECT COUNT(*), MIN(started_at), MAX(started_at) FROM mh.ingest_runs"))
except Exception as e:
    print("ingest_runs started_at n/a:", e)
    print(q("SELECT name,sql FROM mh.sqlite_master WHERE name='ingest_runs'"))
print("mh.daily_bars fetched_at span:", q("SELECT MIN(fetched_at), MAX(fetched_at) FROM mh.daily_bars"))
print("mh.daily_bars available_at span:", q("SELECT MIN(available_at), MAX(available_at) FROM mh.daily_bars"))
print("mh.daily_bars fetched_at DAYS distinct:", q("SELECT COUNT(DISTINCT substr(fetched_at,1,10)) FROM mh.daily_bars"))
con.close()
