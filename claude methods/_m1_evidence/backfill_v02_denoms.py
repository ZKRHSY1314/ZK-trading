import sqlite3, datetime
OP = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"
def q(c,s,a=()): return c.execute(s,a).fetchall()
op = sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
mh = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)

print("### F. instruments composition — is their 5,167 denominator polluted by indices / delisted?")
print("F0 total instruments:", q(mh,"SELECT COUNT(*) FROM instruments"))
print("F1 by exchange:", q(mh,"SELECT exchange, COUNT(*) FROM instruments GROUP BY exchange ORDER BY 2 DESC"))
print("F2 by asset_type:", q(mh,"SELECT asset_type, COUNT(*) FROM instruments GROUP BY asset_type ORDER BY 2 DESC"))
print("F3 by status:", q(mh,"SELECT status, COUNT(*) FROM instruments GROUP BY status ORDER BY 2 DESC"))
print("F4 list_date null/notnull:", q(mh,"SELECT (list_date IS NULL) AS d_null, COUNT(*) FROM instruments GROUP BY d_null"))
print("F5 delist_date not null:", q(mh,"SELECT COUNT(*) FROM instruments WHERE delist_date IS NOT NULL AND delist_date<>''"))

W0, W1, GAPEND = '2023-09-04','2026-09-04','2024-04-08'
print()
print("### G. THEIR denominator vs a cleaned one, for symbols listed on/before window start")
print("G1 ALL instruments with list_date <= 2023-09-04 (their likely 5,167):",
      q(mh,"SELECT COUNT(*) FROM instruments WHERE list_date IS NOT NULL AND list_date<>'' AND date(list_date) <= ?", (W0,)))
print("G2 same, EXCLUDING exchange='INDEX':",
      q(mh,"SELECT COUNT(*) FROM instruments WHERE list_date IS NOT NULL AND list_date<>'' AND date(list_date)<=? AND exchange<>'INDEX'", (W0,)))
print("G3 same, exchange in (SH,SZ,BJ) only:",
      q(mh,"SELECT COUNT(*) FROM instruments WHERE list_date IS NOT NULL AND list_date<>'' AND date(list_date)<=? AND exchange IN ('SH','SZ','BJ')", (W0,)))
print("G4 G3 minus those DELISTED before window start (never tradable in window):",
      q(mh,"""SELECT COUNT(*) FROM instruments WHERE list_date IS NOT NULL AND list_date<>'' AND date(list_date)<=?
              AND exchange IN ('SH','SZ','BJ')
              AND NOT (delist_date IS NOT NULL AND delist_date<>'' AND date(delist_date) < ?)""", (W0,W0)))
print("G5 G3 minus those delisted before the GAP END 2024-04-08 (i.e. alive for >=1 gap session):",
      q(mh,"""SELECT COUNT(*) FROM instruments WHERE list_date IS NOT NULL AND list_date<>'' AND date(list_date)<=?
              AND exchange IN ('SH','SZ','BJ')
              AND NOT (delist_date IS NOT NULL AND delist_date<>'' AND date(delist_date) < ?)""", (W0,W0)))
print("G6 how many of the G1 set are INDEX rows:",
      q(mh,"SELECT COUNT(*) FROM instruments WHERE list_date IS NOT NULL AND list_date<>'' AND date(list_date)<=? AND exchange='INDEX'", (W0,)))
print("G7 asset_type breakdown of the G1 set:",
      q(mh,"SELECT exchange, asset_type, COUNT(*) FROM instruments WHERE list_date IS NOT NULL AND list_date<>'' AND date(list_date)<=? GROUP BY 1,2 ORDER BY 3 DESC", (W0,)))
print("G8 delisted DURING the gap window (2023-09-04..2024-04-08) — partial sessions only:",
      q(mh,"""SELECT COUNT(*) FROM instruments WHERE list_date IS NOT NULL AND list_date<>'' AND date(list_date)<=?
              AND exchange IN ('SH','SZ','BJ') AND delist_date IS NOT NULL AND delist_date<>''
              AND date(delist_date) BETWEEN ? AND ?""", (W0,W0,GAPEND)))

print()
print("### H. where does '5,566 dated symbols' come from? symbol universes")
cache_syms = set(x[0] for x in q(op,"SELECT DISTINCT symbol FROM daily_bar_cache"))
hist_syms  = set(x[0] for x in q(mh,"SELECT DISTINCT symbol FROM daily_bars"))
inst_syms  = set(x[0] for x in q(mh,"SELECT DISTINCT symbol FROM instruments"))
inst_dated = set(x[0] for x in q(mh,"SELECT symbol FROM instruments WHERE list_date IS NOT NULL AND list_date<>''"))
print("H1 |cache symbols|=%d |hist symbols|=%d |instruments|=%d |instruments with list_date|=%d" %
      (len(cache_syms), len(hist_syms), len(inst_syms), len(inst_dated)))
print("H2 |cache UNION hist| = %d   |cache INTERSECT hist| = %d" % (len(cache_syms|hist_syms), len(cache_syms&hist_syms)))
print("H3 |cache - instruments| = %d   sample:%s" % (len(cache_syms-inst_syms), sorted(cache_syms-inst_syms)[:8]))

print()
print("### I. INDEP session-count estimate for the gap 2023-09-04..2024-04-08 (no calendar table exists)")
d0 = datetime.date(2023,9,4); d1 = datetime.date(2024,4,8)
wk = sum(1 for i in range((d1-d0).days+1) if (d0+datetime.timedelta(days=i)).weekday()<5)
print("I1 weekdays in gap:", wk)
# CN public-holiday weekdays 2023-09-04..2024-04-08 (Mid-Autumn/National 2023-09-29..10-06 -> weekday holidays;
# New Year 2024-01-01; Spring Festival 2024-02-09..02-16; Qingming 2024-04-04..04-05)
hol = ['2023-09-29','2023-10-02','2023-10-03','2023-10-04','2023-10-05','2023-10-06',
       '2024-01-01','2024-02-09','2024-02-12','2024-02-13','2024-02-14','2024-02-15','2024-02-16',
       '2024-04-04','2024-04-05']
hol = [h for h in hol if datetime.date(*map(int,h.split('-'))).weekday()<5]
print("I2 weekday public holidays subtracted:", len(hol), hol)
print("I3 => estimated gap sessions:", wk-len(hol))
# observed density check
n_obs = q(op,"SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN '2024-04-09' AND '2026-09-04'")[0][0]
span = (datetime.date(2026,9,4)-datetime.date(2024,4,9)).days+1
print("I4 observed: %d sessions over %d calendar days = %.4f sess/day" % (n_obs, span, n_obs/span))
gap_days = (d1-d0).days+1
print("I5 gap calendar days=%d -> density-implied sessions=%.1f" % (gap_days, gap_days*n_obs/span))
print("I6 implied TOTAL window sessions = %d observed + gap estimate" % n_obs)

op.close(); mh.close()
