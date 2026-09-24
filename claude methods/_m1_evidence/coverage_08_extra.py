# -*- coding: utf-8 -*-
"""Severe leading-gap symbols, ramp accounting, session-count reconciliation. READ-ONLY."""
import sqlite3, pathlib, sys, csv, datetime

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
OUT = pathlib.Path(r"D:\codex-A股交易\claude methods\_m1_evidence")

gs = list(csv.DictReader(open(OUT / "coverage_gap_shape.csv", encoding="utf-8-sig")))
print("### symbols with leading_gap > 300 (never backfilled; joined the cache late)")
for r in sorted(gs, key=lambda x: -int(x["leading_gap"]))[:20]:
    print("   ", r["symbol"], r["name"], "list=%s status=%s elig=%s obs=%s lead=%s first_obs=%s"
          % (r["list_date"], r["status"], r["eligible_sessions"], r["observed_sessions"],
             r["leading_gap"], r["first_observed"]))
print()
print("### symbols with interior_gap>0 :", sum(1 for r in gs if int(r["interior_gap"]) > 0))
print("### symbols with interior_gap>0 whose name contains ST or 退 :",
      sum(1 for r in gs if int(r["interior_gap"]) > 0 and ("ST" in r["name"] or "退" in r["name"])))
print("### total symbols with interior gaps and name ST/退 share of interior slots:")
tot_i = sum(int(r["interior_gap"]) for r in gs)
st_i = sum(int(r["interior_gap"]) for r in gs if "ST" in r["name"] or "退" in r["name"])
print("    interior slots total=%d  on ST/退 names=%d (%.1f%%)" % (tot_i, st_i, 100 * st_i / tot_i))
print()

# session-count reconciliation, clearly separating measured vs estimated
W0, W1 = "2023-09-04", "2026-09-04"
d0 = datetime.date.fromisoformat(W0)
d1 = datetime.date.fromisoformat(W1)
wd = [d0 + datetime.timedelta(days=i) for i in range((d1 - d0).days + 1)]
wd = [d for d in wd if d.weekday() < 5]
sub0 = datetime.date.fromisoformat("2024-04-09")
wd_sub = [d for d in wd if d >= sub0]
wd_pre = [d for d in wd if d < sub0]
print("MEASURED: sessions observed in window                 = 587  (2024-04-09..2026-09-04)")
print("MEASURED: sessions with >=5000 stocks (full market)   = 536  (2024-06-24..2026-09-03)")
print("MEASURED: weekdays in window                          =", len(wd))
print("MEASURED: weekdays before first data day (no rows)    =", len(wd_pre))
print("MEASURED: weekdays in data sub-window                 =", len(wd_sub))
print("MEASURED: observed-session rate inside sub-window     = 587/%d = %.4f" % (len(wd_sub), 587 / len(wd_sub)))
print("ESTIMATE (NOT a measurement): true sessions in full window ~= %d weekdays * %.4f = %.0f"
      % (len(wd), 587 / len(wd_sub), len(wd) * 587 / len(wd_sub)))
est = len(wd) * 587 / len(wd_sub)
print("ESTIMATE: sessions in window with NO data at all      ~= %.0f" % (est - 587))
print("ESTIMATE: full-market session share of window         ~= 536/%.0f = %.1f%%" % (est, 100 * 536 / est))
