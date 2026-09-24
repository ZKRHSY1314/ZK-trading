# -*- coding: utf-8 -*-
"""Per-symbol coverage manifest + calendar spine. READ-ONLY (mode=ro URIs only)."""
import sqlite3, pathlib, sys, csv, datetime, statistics, collections

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
OP = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"
OUT = pathlib.Path(r"D:\codex-A股交易\claude methods\_m1_evidence")
W0, W1 = "2023-09-04", "2026-09-04"
DG = "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]"


def rouri(p):
    return "file:" + pathlib.Path(p).as_posix() + "?mode=ro"


c = sqlite3.connect(rouri(OP), uri=True)
c.execute("ATTACH DATABASE ? AS mh", (rouri(MH),))


def q(sql, params=()):
    return list(c.execute(sql, params))


# ---------- 1. CALENDAR SPINE ----------
# Spine = distinct trade_dates in window from rows belonging to CLASSIFIED A-share STOCKS
# (instruments.asset_type='stock' AND exchange IN SH/SZ/BJ), unioned across both stores.
# Indices and unclassifiable symbols are excluded so an index-only row cannot invent a session.
SPINE_SQL = """
SELECT DISTINCT d.trade_date FROM daily_bar_cache d JOIN mh.instruments i ON i.symbol=d.symbol
 WHERE i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ')
   AND d.trade_date BETWEEN ? AND ? AND d.trade_date GLOB ?
UNION
SELECT DISTINCT b.trade_date FROM mh.daily_bars b JOIN mh.instruments i ON i.symbol=b.symbol
 WHERE i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ')
   AND b.trade_date BETWEEN ? AND ?
"""
spine = sorted(r[0] for r in q(SPINE_SQL, (W0, W1, DG, W0, W1)))
print("SPINE SQL:", " ".join(SPINE_SQL.split()))
print("spine sessions (stock-only, union of both stores) =", len(spine))
print("spine first=%s  last=%s" % (spine[0], spine[-1]))

cache_dates = sorted(r[0] for r in q(
    "SELECT DISTINCT trade_date FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ? AND trade_date GLOB ?",
    (W0, W1, DG)))
mh_dates = sorted(r[0] for r in q(
    "SELECT DISTINCT trade_date FROM mh.daily_bars WHERE trade_date BETWEEN ? AND ?", (W0, W1)))
print("cache distinct dates(any symbol)=%d first=%s last=%s" % (len(cache_dates), cache_dates[0], cache_dates[-1]))
print("mh    distinct dates(any symbol)=%d first=%s last=%s" % (len(mh_dates), mh_dates[0], mh_dates[-1]))
print("dates in cache not in mh:", sorted(set(cache_dates) - set(mh_dates)))
print("dates in mh not in cache:", sorted(set(mh_dates) - set(cache_dates)))

breadth = dict(q("""SELECT d.trade_date, COUNT(DISTINCT d.symbol) FROM daily_bar_cache d
  JOIN mh.instruments i ON i.symbol=d.symbol WHERE i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ')
  AND d.trade_date BETWEEN ? AND ? AND d.trade_date GLOB ? GROUP BY 1""", (W0, W1, DG)))
breadth_mh = dict(q("""SELECT b.trade_date, COUNT(DISTINCT b.symbol) FROM mh.daily_bars b
  JOIN mh.instruments i ON i.symbol=b.symbol WHERE i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ')
  AND b.trade_date BETWEEN ? AND ? GROUP BY 1""", (W0, W1)))

print("\nBREADTH RAMP (trading_local cache, stock-only distinct symbols per session)")
for n in (100, 500, 1000, 2000, 3000, 4000, 5000, 5400, 5500):
    fd = next((d for d in spine if breadth.get(d, 0) >= n), None)
    cnt = sum(1 for d in spine if breadth.get(d, 0) >= n)
    print("  first session with >=%5d stocks: %s   sessions at/above: %d" % (n, fd, cnt))
print("\nBREADTH RAMP (market_history)")
for n in (1000, 3000, 5000, 5400):
    fd = next((d for d in spine if breadth_mh.get(d, 0) >= n), None)
    cnt = sum(1 for d in spine if breadth_mh.get(d, 0) >= n)
    print("  first session with >=%5d stocks: %s   sessions at/above: %d" % (n, fd, cnt))

bk = collections.Counter()
for d in spine:
    b = breadth.get(d, 0)
    bk["<100" if b < 100 else "100-999" if b < 1000 else "1000-2999" if b < 3000
       else "3000-4999" if b < 5000 else ">=5000"] += 1
print("\nsessions by cache-breadth bucket:")
for k in ("<100", "100-999", "1000-2999", "3000-4999", ">=5000"):
    print("  %10s: %d" % (k, bk[k]))

d0 = datetime.date.fromisoformat(W0)
d1 = datetime.date.fromisoformat(W1)
wd_full = [d0 + datetime.timedelta(days=i) for i in range((d1 - d0).days + 1)]
wd_full = [d for d in wd_full if d.weekday() < 5]
dstart = datetime.date.fromisoformat(spine[0])
wd_sub = [d for d in wd_full if d >= dstart]
print("\nESTIMATE (not a measurement): weekdays in full window %s..%s = %d" % (W0, W1, len(wd_full)))
print("ESTIMATE (not a measurement): weekdays in data sub-window %s..%s = %d" % (spine[0], W1, len(wd_sub)))
sset = set(spine)
missing_wd = [d.isoformat() for d in wd_sub if d.isoformat() not in sset]
print("weekdays inside sub-window with NO session in spine = %d (holidays + any dropped sessions)" % len(missing_wd))
print("  sample:", missing_wd[:30])

# ---------- 2. PER-SYMBOL COVERAGE ----------
instruments = q("""SELECT symbol, name, exchange, asset_type, board, list_date, delist_date, status
                   FROM mh.instruments WHERE asset_type='stock' AND exchange IN ('SH','SZ','BJ') ORDER BY symbol""")
print("\nclassified stock instruments =", len(instruments))

obs_cache = {}
for sym, n, f, l in q("""SELECT d.symbol, COUNT(*), MIN(d.trade_date), MAX(d.trade_date)
   FROM daily_bar_cache d WHERE d.trade_date BETWEEN ? AND ? AND d.trade_date GLOB ?
     AND d.open IS NOT NULL AND d.high IS NOT NULL AND d.low IS NOT NULL AND d.close IS NOT NULL AND d.close>0
   GROUP BY d.symbol""", (W0, W1, DG)):
    obs_cache[sym] = (n, f, l)
obs_mh = {}
for sym, n, f, l in q("""SELECT b.symbol, COUNT(*), MIN(b.trade_date), MAX(b.trade_date)
   FROM mh.daily_bars b WHERE b.trade_date BETWEEN ? AND ? AND b.close>0 GROUP BY b.symbol""", (W0, W1)):
    obs_mh[sym] = (n, f, l)
print("symbols with >=1 valid cache row in window =", len(obs_cache))
print("symbols with >=1 valid mh    row in window =", len(obs_mh))

rows = []
unknown_list = 0
for sym, name, exch, atype, board, ld, dd, status in instruments:
    n_c, f_c, l_c = obs_cache.get(sym, (0, "", ""))
    if ld and ld.strip():
        lo = max(ld, W0)
        hi = min(dd, W1) if (dd and dd.strip()) else W1
        elig = sum(1 for d in spine if lo <= d <= hi)
        basis = "listing_interval"
        ratio = (n_c / elig) if elig else None
    else:
        unknown_list += 1
        elig = None
        basis = "unknown_list_date"
        ratio = None
    rows.append(dict(symbol=sym, name=name or "", exchange=exch, asset_type=atype,
                     list_date=ld or "", delist_date=dd or "", status=status,
                     window_first=f_c or "", window_last=l_c or "",
                     observed_sessions=n_c,
                     eligible_sessions="" if elig is None else elig,
                     coverage_ratio="" if ratio is None else "%.6f" % ratio,
                     eligibility_basis=basis))

path = OUT / "coverage_manifest.csv"
with open(path, "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=["symbol", "name", "exchange", "asset_type", "list_date", "delist_date",
                                       "status", "window_first", "window_last", "observed_sessions",
                                       "eligible_sessions", "coverage_ratio", "eligibility_basis"])
    w.writeheader()
    w.writerows(rows)
print("\nwrote %s (%d rows)" % (path, len(rows)))

comp = [r for r in rows if r["eligibility_basis"] == "listing_interval" and r["eligible_sessions"] != ""
        and int(r["eligible_sessions"]) > 0]
zero_elig = [r for r in rows if r["eligibility_basis"] == "listing_interval" and r["eligible_sessions"] != ""
             and int(r["eligible_sessions"]) == 0]
ratios = sorted(float(r["coverage_ratio"]) for r in comp)
print("\ncomputable stocks (listing_interval, eligible>0) =", len(comp))
print("stocks with eligible_sessions==0 (listed after last spine session) =", len(zero_elig))
print("stocks with NULL list_date (eligibility NOT computable) =", unknown_list)
print("\nCOVERAGE DECILES  (valid cache sessions observed / eligible spine sessions):")
for i in range(0, 11):
    idx = min(len(ratios) - 1, max(0, int(round(i / 10 * (len(ratios) - 1)))))
    print("  P%-3d  %.4f" % (i * 10, ratios[idx]))
print("  mean=%.4f  median=%.4f" % (sum(ratios) / len(ratios), statistics.median(ratios)))
for thr in (0.99, 0.95, 0.90, 0.50):
    n = sum(1 for r in ratios if r >= thr)
    print("  count >= %.2f : %d  (%.1f%% of computable)" % (thr, n, 100 * n / len(ratios)))
print("  count <  0.50 : %d" % sum(1 for r in ratios if r < 0.50))
print("  count == 0.00 : %d" % sum(1 for r in ratios if r == 0))
print("  count >  1.00 : %d" % sum(1 for r in ratios if r > 1.0))

pre = [r for r in comp if r["list_date"] < spine[0]]
pre_r = sorted(float(r["coverage_ratio"]) for r in pre)
print("\nSUBSET: stocks already listed before the first data session (%s), n=%d" % (spine[0], len(pre_r)))
for thr in (0.99, 0.95, 0.90, 0.50):
    n = sum(1 for x in pre_r if x >= thr)
    print("  count >= %.2f : %d  (%.1f%%)" % (thr, n, 100 * n / len(pre_r)))
print("  median=%.4f  mean=%.4f" % (statistics.median(pre_r), sum(pre_r) / len(pre_r)))
for i in range(0, 11):
    idx = min(len(pre_r) - 1, max(0, int(round(i / 10 * (len(pre_r) - 1)))))
    print("  P%-3d  %.4f" % (i * 10, pre_r[idx]))
