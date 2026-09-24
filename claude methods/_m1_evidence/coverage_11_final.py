# -*- coding: utf-8 -*-
"""Final tallies: BJ renumber cohort, window_first histogram, decile table. READ-ONLY."""
import csv, pathlib, sys, collections, statistics

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
OUT = pathlib.Path(r"D:\codex-A股交易\claude methods\_m1_evidence")
m = list(csv.DictReader(open(OUT / "coverage_manifest.csv", encoding="utf-8-sig")))
print("manifest rows =", len(m))

print("\n### window_first histogram (top 20) - shows when each cohort entered the store")
h = collections.Counter(r["window_first"] or "(none)" for r in m)
for d, n in h.most_common(20):
    print("   %s  %d" % (d, n))

print("\n### BJ cohort")
bj = [r for r in m if r["exchange"] == "BJ"]
print("   BJ stocks total =", len(bj))
print("   BJ stocks whose first observed bar is 2024-08-12/13 =",
      sum(1 for r in bj if r["window_first"] in ("2024-08-12", "2024-08-13")))
print("   BJ stocks listed before 2024-08-12 =", sum(1 for r in bj if r["list_date"] and r["list_date"] < "2024-08-12"))
print("   -> BJ pre-2024-08 history absent under the 920xxx symbol")

print("\n### exchange x coverage band (computable rows only)")
bands = collections.Counter()
for r in m:
    if not r["coverage_ratio"]:
        continue
    v = float(r["coverage_ratio"])
    b = ">=0.99" if v >= 0.99 else ">=0.95" if v >= 0.95 else ">=0.90" if v >= 0.90 else ">=0.50" if v >= 0.50 else "<0.50"
    bands[(r["exchange"], b)] += 1
for k in sorted(bands):
    print("   %s %-7s %d" % (k[0], k[1], bands[k]))

print("\n### full decile table (computable, eligible>0)")
rr = sorted(float(r["coverage_ratio"]) for r in m if r["coverage_ratio"])
n = len(rr)
print("   n =", n)
for i in range(0, 11):
    print("   D%-3d %.6f" % (i * 10, rr[min(n - 1, int(round(i / 10 * (n - 1))))]))
print("   mean=%.6f median=%.6f" % (sum(rr) / n, statistics.median(rr)))
print("   >=0.99: %d   >=0.95: %d   >=0.90: %d   <0.50: %d" %
      (sum(1 for x in rr if x >= .99), sum(1 for x in rr if x >= .95),
       sum(1 for x in rr if x >= .90), sum(1 for x in rr if x < .50)))
print("   distinct ratio values (top 10 by frequency):")
for v, k in collections.Counter("%.6f" % x for x in rr).most_common(10):
    print("      %s  x%d" % (v, k))

print("\n### observed_sessions histogram (top 12)")
for v, k in collections.Counter(r["observed_sessions"] for r in m).most_common(12):
    print("   obs=%s  x%d" % (v, k))

print("\n### status / delist_date accounting")
print("   status=active :", sum(1 for r in m if r["status"] == "active"))
print("   status=inactive :", sum(1 for r in m if r["status"] != "active"))
print("   rows with a non-empty delist_date :", sum(1 for r in m if r["delist_date"].strip()))
print("   rows with empty list_date :", sum(1 for r in m if not r["list_date"].strip()))
