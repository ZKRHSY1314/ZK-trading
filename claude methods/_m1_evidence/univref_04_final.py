import sqlite3, json, datetime, os
TL = "D:/codex-A股交易/trading_local.sqlite3"
MH = "D:/codex-A股交易/market_history.sqlite3"
t = sqlite3.connect(f"file:{TL}?mode=ro", uri=True); q  = lambda s,a=(): t.execute(s,a).fetchall()
m = sqlite3.connect(f"file:{MH}?mode=ro", uri=True); qm = lambda s,a=(): m.execute(s,a).fetchall()

print("### Y. invalid trade_date values in daily_bar_cache (no CHECK constraint)")
for r in q("""SELECT trade_date, COUNT(*) FROM daily_bar_cache
              WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' GROUP BY trade_date"""):
    print("   ",r)
print("   max VALID trade_date:", q("SELECT MAX(trade_date) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'")[0][0])

print("\n### Z. window arithmetic")
w0=datetime.date(2023,9,4); w1=datetime.date(2026,9,4)
for label,d in (("table min 2024-04-09",datetime.date(2024,4,9)),("breadth start 2024-06-24",datetime.date(2024,6,24))):
    print("   %s : %d calendar days after window start; window len=%d days; front gap=%.1f%%"
          %(label,(d-w0).days,(w1-w0).days+1,100.0*(d-w0).days/((w1-w0).days+1)))

print("\n### AA. is 536 a FIXED-LENGTH CAP or just full coverage of the available spine?")
spine = [x[0] for x in qm("SELECT DISTINCT trade_date FROM daily_bars ORDER BY trade_date")]
print("   total spine dates:", len(spine), " spine[0]:", spine[0], " index of 2024-06-24:", spine.index('2024-06-24'))
print("   dates from 2024-06-24 to end:", len(spine)-spine.index('2024-06-24'))
print("   -> symbols with exactly 536 bars whose first bar is 2024-06-24 AND last is max:",
  qm("""SELECT COUNT(*) FROM (SELECT symbol, COUNT(*) n, MIN(trade_date) f, MAX(trade_date) l FROM daily_bars GROUP BY symbol)
        WHERE n=536 AND f='2024-06-24' AND l='2026-09-03'""")[0][0])
print("   -> so 536 == gapless coverage of every stored date since the 2024-06-24 load, NOT a 500-bar cap")
print("   symbols holding MORE than 500 bars:",
  qm("SELECT COUNT(*) FROM (SELECT symbol, COUNT(*) n FROM daily_bars GROUP BY symbol) WHERE n>500")[0][0])
print("   symbols holding <=500 bars:",
  qm("SELECT COUNT(*) FROM (SELECT symbol, COUNT(*) n FROM daily_bars GROUP BY symbol) WHERE n<=500")[0][0])

print("\n### AB. TRUE truncation numerator/denominator (market_history.daily_bars)")
den = qm("""SELECT COUNT(*) FROM (SELECT DISTINCT symbol s FROM daily_bars) x JOIN instruments i ON i.symbol=x.s
            WHERE i.list_date IS NOT NULL AND i.list_date < '2024-04-09'""")[0][0]
num = qm("""SELECT COUNT(*) FROM (SELECT symbol, MIN(trade_date) ft FROM daily_bars GROUP BY symbol) f
            JOIN instruments i ON i.symbol=f.symbol
            WHERE i.list_date IS NOT NULL AND i.list_date < '2024-04-09' AND f.ft > i.list_date""")[0][0]
print("   denominator (bar-carrying, listed before the store's earliest date):", den)
print("   numerator   (first bar strictly later than own list_date):", num, " -> %.2f%%"%(100.0*num/den))
print("   same numerator over THEIR denominator 5560: %.1f%%"%(100.0*num/5560))
print("   symbols listed ON/AFTER 2024-04-09 (legit late first bar, NOT truncation):",
  qm("""SELECT COUNT(*) FROM (SELECT DISTINCT symbol s FROM daily_bars) x JOIN instruments i ON i.symbol=x.s
        WHERE i.list_date IS NULL OR i.list_date >= '2024-04-09'""")[0][0])

print("\n### AC. SURVIVORSHIP: delisted / non-active instruments and whether they carry bars")
for r in qm("""SELECT i.status, (i.delist_date IS NOT NULL) has_delist, COUNT(*) n,
               SUM(CASE WHEN b.s IS NULL THEN 0 ELSE 1 END) with_bars
               FROM instruments i LEFT JOIN (SELECT DISTINCT symbol s FROM daily_bars) b ON b.s=i.symbol
               GROUP BY i.status, has_delist"""):
    print("   status=%-10s has_delist=%s  n=%-5s with_bars=%s"%r)

print("\n### AD. universe_snapshots metadata (their cited mechanism)")
for r in qm("SELECT id, universe_name, snapshot_date, provider, member_count, substr(metadata_json,1,220) FROM universe_snapshots ORDER BY snapshot_date"):
    print("   ",r)
t.close(); m.close()
