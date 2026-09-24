# -*- coding: utf-8 -*-
"""Coverage recomputed against the FULL-MARKET regime only (2024-06-24..2026-09-03). READ-ONLY."""
import sqlite3, pathlib, sys, statistics, collections

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
OP = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"
F0, F1 = "2024-06-24", "2026-09-03"
DG = "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]"


def rouri(p):
    return "file:" + pathlib.Path(p).as_posix() + "?mode=ro"


c = sqlite3.connect(rouri(OP), uri=True)
c.execute("ATTACH DATABASE ? AS mh", (rouri(MH),))
q = lambda s, p=(): list(c.execute(s, p))

spine = sorted(r[0] for r in q("""SELECT DISTINCT d.trade_date FROM daily_bar_cache d
  JOIN mh.instruments i ON i.symbol=d.symbol WHERE i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ')
  AND d.trade_date BETWEEN ? AND ? AND d.trade_date GLOB ?""", (F0, F1, DG)))
print("full-market spine sessions =", len(spine), spine[0], "..", spine[-1])
S = len(spine)

inst = q("""SELECT symbol,name,exchange,list_date,delist_date,status FROM mh.instruments
            WHERE asset_type='stock' AND exchange IN ('SH','SZ','BJ')""")
obs_c = dict(q("""SELECT symbol, COUNT(*) FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ? AND trade_date GLOB ?
   AND open IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL AND close IS NOT NULL AND close>0
   GROUP BY symbol""", (F0, F1, DG)))
obs_m = dict(q("""SELECT symbol, COUNT(*) FROM mh.daily_bars WHERE trade_date BETWEEN ? AND ? AND close>0
   GROUP BY symbol""", (F0, F1)))

for label, obs in (("trading_local.daily_bar_cache", obs_c), ("market_history.daily_bars", obs_m)):
    rr = []
    nullld = 0
    zero = 0
    for sym, name, exch, ld, dd, status in inst:
        if not (ld and ld.strip()):
            nullld += 1
            continue
        lo = max(ld, F0)
        hi = min(dd, F1) if (dd and dd.strip()) else F1
        elig = sum(1 for d in spine if lo <= d <= hi)
        if elig == 0:
            zero += 1
            continue
        rr.append(obs.get(sym, 0) / elig)
    rr.sort()
    print("\n=== %s : coverage vs FULL-MARKET spine (%d sessions) ===" % (label, S))
    print("computable n=%d  null_list_date=%d  eligible0=%d" % (len(rr), nullld, zero))
    for i in range(0, 11):
        print("  P%-3d %.4f" % (i * 10, rr[min(len(rr) - 1, int(round(i / 10 * (len(rr) - 1))))]))
    print("  mean=%.4f median=%.4f" % (sum(rr) / len(rr), statistics.median(rr)))
    for thr in (0.995, 0.99, 0.95, 0.90, 0.50):
        n = sum(1 for x in rr if x >= thr)
        print("  >=%.3f : %d (%.1f%%)" % (thr, n, 100 * n / len(rr)))
    print("  <0.50 : %d" % sum(1 for x in rr if x < 0.50))
    print("  ==1.00: %d" % sum(1 for x in rr if x >= 0.999999))
