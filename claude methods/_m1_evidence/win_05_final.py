import sqlite3, statistics
from collections import Counter
TL = r"D:/codex-A股交易/trading_local.sqlite3"; MH = r"D:/codex-A股交易/market_history.sqlite3"
W0,W1='2023-09-04','2026-09-04'
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True); c.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")
def q(sql,label,args=()):
    print("\n### "+label); print("SQL:"," ".join(sql.split()))
    out=list(c.execute(sql,args))
    for r in out: print("   ",r)
    return out

# 1. reconcile 5,543 vs 5,561
q("""SELECT COUNT(*) FROM mh.instruments i WHERE i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ')
     AND NOT EXISTS (SELECT 1 FROM daily_bar_cache d WHERE d.symbol=i.symbol
       AND d.trade_date BETWEEN ? AND ? AND d.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
       AND d.open IS NOT NULL AND d.high IS NOT NULL AND d.low IS NOT NULL AND d.close IS NOT NULL AND d.close>0)""",
  "stocks with ZERO observed sessions in window (explains 5561 - 5543 = 18)", (W0,W1))

# 2. MH cross-check, CORRECTED to the only mode present (qfq)
q("""SELECT observed, COUNT(*) FROM (
      SELECT i.symbol, COUNT(DISTINCT b.trade_date) AS observed
      FROM mh.instruments i JOIN mh.daily_bars b ON b.symbol=i.symbol AND b.adjustment_mode='qfq'
      WHERE b.trade_date BETWEEN ? AND ? AND i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ')
        AND i.list_date < '2024-04-09' GROUP BY i.symbol)
     GROUP BY observed ORDER BY COUNT(*) DESC LIMIT 6""",
  "market_history.daily_bars(qfq): observed-session histogram, PRE-EXISTING stocks", (W0,W1))
r=q("""SELECT COUNT(*), MAX(observed) FROM (
      SELECT i.symbol, COUNT(DISTINCT b.trade_date) AS observed
      FROM mh.instruments i JOIN mh.daily_bars b ON b.symbol=i.symbol AND b.adjustment_mode='qfq'
      WHERE b.trade_date BETWEEN ? AND ? AND i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ')
        AND i.list_date < '2024-04-09' GROUP BY i.symbol)""",
  "MH pre-existing cohort: n symbols, max observed sessions (MH spine=586)", (W0,W1))

# 3. mean over observed>0 only, to match their 0.914902
spine=[x[0] for x in c.execute("""SELECT DISTINCT d.trade_date FROM daily_bar_cache d JOIN mh.instruments i ON i.symbol=d.symbol
    WHERE d.trade_date BETWEEN ? AND ? AND d.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' ORDER BY 1""",(W0,W1))]
rows=list(c.execute("""SELECT i.symbol,i.list_date,i.delist_date,COUNT(DISTINCT d.trade_date)
    FROM mh.instruments i LEFT JOIN daily_bar_cache d ON d.symbol=i.symbol AND d.trade_date BETWEEN ? AND ?
      AND d.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND d.open IS NOT NULL AND d.high IS NOT NULL
      AND d.low IS NOT NULL AND d.close IS NOT NULL AND d.close>0
    WHERE i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ') GROUP BY i.symbol""",(W0,W1)))
def elig(ld,dd):
    lo=max(W0,ld) if ld else W0; hi=min(W1,dd) if dd else W1
    return sum(1 for t in spine if lo<=t<=hi)
nz=[(o,elig(ld,dd)) for s,ld,dd,o in rows if o>0]
rt=[o/e for o,e in nz]
print("\n### restricted to the %d stocks with observed>0 (their 'computable')" % len(nz))
print("   mean=%.6f  median=%.6f   (their reported mean 0.914902)" % (statistics.mean(rt), statistics.median(rt)))
print("   >0.90 share = %.4f  (their '95.4%% above 90%%')" % (sum(1 for x in rt if x>0.90)/len(rt)))

# 4. THE HEADLINE: coverage against the real 3-year window
EST=733
print("\n### FINAL: coverage of the ACTUAL 3-year research window (~%d A-share sessions)" % EST)
allobs=[o for s,ld,dd,o in rows]
print("   max observed sessions by ANY stock          : %d  -> %.4f of window" % (max(allobs), max(allobs)/EST))
print("   median observed sessions                    : %d  -> %.4f of window" % (statistics.median(allobs), statistics.median(allobs)/EST))
print("   stocks reaching >=0.95 of the real window   : %d" % sum(1 for o in allobs if o/EST>=0.95))
print("   stocks reaching >=0.90 of the real window   : %d" % sum(1 for o in allobs if o/EST>=0.90))
print("   stocks reaching >=0.80 of the real window   : %d" % sum(1 for o in allobs if o/EST>=0.80))
print("   window days with ZERO data (2023-09-04..2024-04-08): 156 weekdays / ~146 sessions = %.1f%% of window" % (146/EST*100))
c.close()
