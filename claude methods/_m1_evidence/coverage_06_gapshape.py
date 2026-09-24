# -*- coding: utf-8 -*-
"""Decompose per-symbol absence into leading gap / interior gap / trailing gap. READ-ONLY."""
import sqlite3, pathlib, sys, csv, statistics, collections

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
q = lambda s, p=(): list(c.execute(s, p))

spine = sorted(r[0] for r in q("""
SELECT DISTINCT d.trade_date FROM daily_bar_cache d JOIN mh.instruments i ON i.symbol=d.symbol
 WHERE i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ')
   AND d.trade_date BETWEEN ? AND ? AND d.trade_date GLOB ?
UNION
SELECT DISTINCT b.trade_date FROM mh.daily_bars b JOIN mh.instruments i ON i.symbol=b.symbol
 WHERE i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ') AND b.trade_date BETWEEN ? AND ?
""", (W0, W1, DG, W0, W1)))
spine_idx = {d: i for i, d in enumerate(spine)}
S = len(spine)
print("spine sessions =", S, spine[0], "..", spine[-1])

inst = {r[0]: r for r in q("""SELECT symbol,name,exchange,list_date,delist_date,status FROM mh.instruments
                             WHERE asset_type='stock' AND exchange IN ('SH','SZ','BJ')""")}
print("stock instruments =", len(inst))

# pull all (symbol, trade_date) valid pairs from cache in window
print("streaming cache pairs ...")
per = collections.defaultdict(list)
for sym, td in c.execute("""SELECT symbol, trade_date FROM daily_bar_cache
   WHERE trade_date BETWEEN ? AND ? AND trade_date GLOB ?
     AND open IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL AND close IS NOT NULL AND close>0""",
                         (W0, W1, DG)):
    i = spine_idx.get(td)
    if i is not None:
        per[sym].append(i)
print("symbols with cache rows on spine =", len(per))

lead = []
inter = []
trail = []
detail = []
for sym, (s_, name, exch, ld, dd, status) in inst.items():
    idxs = sorted(per.get(sym, []))
    if not idxs:
        continue
    if ld and ld.strip():
        lo = max(ld, W0)
    else:
        lo = spine[0]
    hi = min(dd, W1) if (dd and dd.strip()) else W1
    elig = [i for i, d in enumerate(spine) if lo <= d <= hi]
    if not elig:
        continue
    e0, e1 = elig[0], elig[-1]
    o0, o1 = idxs[0], idxs[-1]
    leading = o0 - e0                      # eligible sessions before first observed bar
    trailing = e1 - o1                     # eligible sessions after last observed bar
    interior = (o1 - o0 + 1) - len(idxs)   # holes inside the observed span
    lead.append(leading)
    inter.append(interior)
    trail.append(trailing)
    detail.append((sym, name, exch, ld or "", status, len(elig), len(idxs), leading, interior, trailing,
                   spine[o0], spine[o1]))

print("\nn symbols analysed =", len(detail))
print("TOTAL eligible-session slots       =", sum(d[5] for d in detail))
print("TOTAL observed valid bars          =", sum(d[6] for d in detail))
print("TOTAL leading absence (never backfilled before first bar) =", sum(lead))
print("TOTAL interior absence (suspension OR missing)            =", sum(inter))
print("TOTAL trailing absence (stopped updating / delist?)       =", sum(trail))
tot_elig = sum(d[5] for d in detail)
print("share leading  = %.2f%%" % (100 * sum(lead) / tot_elig))
print("share interior = %.2f%%" % (100 * sum(inter) / tot_elig))
print("share trailing = %.2f%%" % (100 * sum(trail) / tot_elig))

print("\nleading-gap distribution (sessions):")
lead_s = sorted(lead)
for p in (0, 10, 25, 50, 75, 90, 99, 100):
    print("  P%-3d %d" % (p, lead_s[min(len(lead_s) - 1, int(p / 100 * (len(lead_s) - 1)))]))
print("  symbols with leading gap == 0 :", sum(1 for x in lead if x == 0))
print("  symbols with leading gap > 100:", sum(1 for x in lead if x > 100))
print("  symbols with leading gap > 300:", sum(1 for x in lead if x > 300))

print("\ninterior-gap distribution (sessions):")
int_s = sorted(inter)
for p in (0, 50, 75, 90, 95, 99, 100):
    print("  P%-3d %d" % (p, int_s[min(len(int_s) - 1, int(p / 100 * (len(int_s) - 1)))]))
print("  symbols with interior gap == 0 :", sum(1 for x in inter if x == 0))
print("  symbols with interior gap >= 20:", sum(1 for x in inter if x >= 20))

print("\ntrailing-gap distribution (sessions):")
tr_s = sorted(trail)
for p in (0, 50, 90, 99, 100):
    print("  P%-3d %d" % (p, tr_s[min(len(tr_s) - 1, int(p / 100 * (len(tr_s) - 1)))]))
print("  symbols with trailing gap >= 5 (stale / stopped):", sum(1 for x in trail if x >= 5))
print("  symbols with trailing gap >= 20:", sum(1 for x in trail if x >= 20))

with open(OUT / "coverage_gap_shape.csv", "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh)
    w.writerow(["symbol", "name", "exchange", "list_date", "status", "eligible_sessions", "observed_sessions",
                "leading_gap", "interior_gap", "trailing_gap", "first_observed", "last_observed"])
    w.writerows(sorted(detail))
print("\nwrote", OUT / "coverage_gap_shape.csv")

print("\nworst 15 by interior gap:")
for d in sorted(detail, key=lambda x: -x[8])[:15]:
    print("  ", d[0], d[1], "elig=%d obs=%d interior=%d span %s..%s" % (d[5], d[6], d[8], d[10], d[11]))
print("\nworst 15 by trailing gap:")
for d in sorted(detail, key=lambda x: -x[9])[:15]:
    print("  ", d[0], d[1], "status=%s elig=%d obs=%d trailing=%d last=%s" % (d[4], d[5], d[6], d[9], d[11]))
