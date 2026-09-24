import sqlite3, statistics, datetime, json
from collections import Counter
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
W0, W1 = '2023-09-04', '2026-09-04'
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
c.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")

# ---------- 1. THE DATA SPINE (what the original audit used as denominator) ----------
SQL_SPINE = """
SELECT DISTINCT d.trade_date FROM daily_bar_cache d
JOIN mh.instruments i ON i.symbol=d.symbol
WHERE d.trade_date BETWEEN ? AND ?
  AND d.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
ORDER BY 1"""
spine = [r[0] for r in c.execute(SQL_SPINE, (W0, W1))]
print("SPINE sessions in window: %d   first=%s last=%s" % (len(spine), spine[0], spine[-1]))

# ---------- 2. REAL CALENDAR: weekdays in window, and in the pre-data gap ----------
d0 = datetime.date(2023,9,4); d1 = datetime.date(2026,9,4)
wk_all = wk_gap = wk_covered = 0
gap_end = datetime.date(2024,4,8)   # last day BEFORE first data session
d = d0
while d <= d1:
    if d.weekday() < 5:
        wk_all += 1
        if d <= gap_end: wk_gap += 1
        else: wk_covered += 1
    d += datetime.timedelta(days=1)
print("\nWEEKDAYS(Mon-Fri) in window %s..%s : %d" % (W0, W1, wk_all))
print("  weekdays in PRE-DATA GAP %s..2024-04-08 : %d   (ZERO sessions of data exist here)" % (W0, wk_gap))
print("  weekdays from 2024-04-09..%s            : %d   (spine has %d -> session/weekday ratio %.4f)"
      % (W1, wk_covered, len(spine), len(spine)/wk_covered))
ratio = len(spine)/wk_covered
est_gap_sessions = round(wk_gap*ratio)
est_true_calendar = len(spine) + est_gap_sessions
print("  => estimated real A-share sessions in the 3y window = %d spine + %d missing = ~%d"
      % (len(spine), est_gap_sessions, est_true_calendar))

# ---------- 3. PER-SYMBOL observed, INDEPENDENT implementation (COUNT DISTINCT date) ----------
SQL_OBS = """
SELECT i.symbol, i.list_date, i.delist_date, i.status, i.exchange,
       COUNT(DISTINCT d.trade_date) AS observed
FROM mh.instruments i
LEFT JOIN daily_bar_cache d
  ON d.symbol = i.symbol
 AND d.trade_date >= ? AND d.trade_date <= ?
 AND d.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
 AND d.open IS NOT NULL AND d.high IS NOT NULL AND d.low IS NOT NULL
 AND d.close IS NOT NULL AND d.close > 0
WHERE i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ')
GROUP BY i.symbol, i.list_date, i.delist_date, i.status, i.exchange"""
rows = list(c.execute(SQL_OBS, (W0, W1)))
print("\nInstrument rows (stocks, SH/SZ/BJ): %d" % len(rows))

spine_set = spine
def eligible_spine(list_date, delist_date):
    lo = max(W0, list_date) if list_date else W0
    hi = min(W1, delist_date) if delist_date else W1
    return sum(1 for t in spine_set if lo <= t <= hi)

recs=[]
for sym, ld, dd, st, ex, obs in rows:
    e_sp = eligible_spine(ld, dd)
    recs.append(dict(sym=sym, ld=ld, dd=dd, st=st, ex=ex, obs=obs, e_sp=e_sp))

computable = [r for r in recs if r['e_sp'] > 0]
print("computable (eligible_spine>0): %d   non-computable: %d" % (len(computable), len(recs)-len(computable)))

ratios = sorted(r['obs']/r['e_sp'] for r in computable)
def dec(p): return ratios[min(len(ratios)-1, int(len(ratios)*p))]
print("\n### RATIO vs SPINE (reproducing their metric)")
for p in (0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9):
    print("   D%02d = %.6f" % (p*100, dec(p)))
print("   median=%.6f  mean=%.6f" % (statistics.median(ratios), statistics.mean(ratios)))
print("   536/587=%.6f   537/587=%.6f" % (536/587, 537/587))
n_two = sum(1 for r in computable if r['e_sp']==587 and r['obs'] in (536,537))
print("   symbols with eligible=587 AND observed in {536,537}: %d" % n_two)
print("   observed histogram top: %s" % Counter(r['obs'] for r in computable).most_common(8))
print("   share of computable >0.90 : %.4f" % (sum(1 for x in ratios if x>0.90)/len(ratios)))

# ---------- 4. THE PRE-EXISTING COHORT ----------
FIRST = spine[0]  # 2024-04-09
pre = [r for r in computable if r['ld'] and r['ld'] < FIRST]
print("\n### stocks listed BEFORE first data session %s : %d" % (FIRST, len(pre)))
print("   of those, count reaching >=0.95 of spine-eligible : %d" % sum(1 for r in pre if r['obs']/r['e_sp']>=0.95))
print("   max spine-ratio in that cohort: %.6f" % max(r['obs']/r['e_sp'] for r in pre))
print("   max observed in that cohort   : %d" % max(r['obs'] for r in pre))

# ---------- 5. THE REAL WINDOW DENOMINATOR (my correction) ----------
print("\n### SAME COHORT vs the REAL 3-year calendar (~%d sessions)" % est_true_calendar)
pre_true = [r['obs']/est_true_calendar for r in pre]
print("   median true-window coverage: %.4f   mean: %.4f   max: %.4f"
      % (statistics.median(pre_true), statistics.mean(pre_true), max(pre_true)))
print("   count of ALL %d computable stocks reaching >=0.95 of the real window: %d"
      % (len(computable), sum(1 for r in computable if r['obs']/est_true_calendar>=0.95)))
print("   count reaching >=0.90 of the real window: %d"
      % sum(1 for r in computable if r['obs']/est_true_calendar>=0.90))

# ---------- 6. THE >0.99 COHORT: are they late IPOs? ----------
hi = [r for r in computable if r['obs']/r['e_sp']>0.99]
print("\n### symbols with spine-ratio > 0.99 : %d" % len(hi))
late = sum(1 for r in hi if r['ld'] and r['ld'] > '2024-06-24')
print("   of those, listed AFTER 2024-06-24 : %d (%.1f%%)" % (late, 100*late/max(1,len(hi))))
print("   their median observed sessions: %d (vs spine 587)" % statistics.median([r['obs'] for r in hi]))
json.dump([[r['sym'],r['ld'],r['obs'],r['e_sp']] for r in recs], open('win_recs.json','w'))
c.close()
