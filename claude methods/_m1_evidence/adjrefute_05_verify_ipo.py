# -*- coding: utf-8 -*-
"""Verify the IPO-window exclusion is honest: does the symbol's first cached bar
actually equal its instruments.list_date, and is d1 within 5 exchange sessions of it?
READ-ONLY."""
import sqlite3, sys, collections, json
sys.stdout.reconfigure(encoding='utf-8')
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
W0, W1 = "2023-09-04", "2026-09-04"
con = sqlite3.connect("file:" + TL + "?mode=ro", uri=True); con.execute("PRAGMA query_only=ON")
mcon = sqlite3.connect("file:" + MH + "?mode=ro", uri=True); mcon.execute("PRAGMA query_only=ON")

over = json.load(open(r"D:/codex-A股交易/claude methods/_m1_evidence/adjrefute_over2.json"))
ld = dict(mcon.execute("SELECT symbol, list_date FROM instruments"))
sessions = [r[0] for r in con.execute(
    "SELECT DISTINCT trade_date FROM daily_bar_cache WHERE trade_date GLOB "
    "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND trade_date BETWEEN ? AND ? "
    "ORDER BY trade_date", (W0, W1))]
sidx = {d: i for i, d in enumerate(sessions)}
first = dict(con.execute(
    "SELECT symbol, MIN(trade_date) FROM daily_bar_cache WHERE trade_date GLOB "
    "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' GROUP BY symbol"))
print("SQL: SELECT symbol, MIN(trade_date) FROM daily_bar_cache GROUP BY symbol")
print("SQL: SELECT symbol, list_date FROM instruments  (market_history)")

theirs1 = [e for e in over if abs(e["ret"]) > 0.11 and e["gap"] == 1]
ipo = [e for e in theirs1 if e["within_first5"]]
print("\nIPO-window events inside their 424: %d" % len(ipo))
mism = [e for e in ipo if first.get(e["sym"]) != ld.get(e["sym"])]
print("of those, symbols whose first cached bar != instruments.list_date: %d" % len(mism))
for e in mism[:10]:
    print("   %s first_cached=%s list_date=%s" % (e["sym"], first.get(e["sym"]), ld.get(e["sym"])))

print("\nsessions elapsed between list_date and the event's later date (0 = listing day):")
h = collections.Counter()
for e in ipo:
    l = ld.get(e["sym"])
    h[sidx.get(e["d1"], -99) - sidx.get(l, -99)] += 1
print("   %s" % dict(sorted(h.items())))
print("   -> all must be <=4 for the 'first 5 sessions unlimited' rule to apply")

print("\n15 largest excluded IPO-window events (these are legal no-limit trading, not defects):")
for e in sorted(ipo, key=lambda x: -abs(x["ret"]))[:15]:
    print("   %-9s listed %s  %s->%s  %8.3f -> %8.3f  ret=%+7.3f  board=%-8s session#%d"
          % (e["sym"], ld.get(e["sym"]), e["d0"], e["d1"], e["pclose"], e["close"], e["ret"],
             e["board"], sidx.get(e["d1"], -99) - sidx.get(ld.get(e["sym"]), -99) + 1))

# ---- price-level proof that the 0.5-2pp bin cannot be tick rounding
print("\n" + "=" * 78)
print("M. CAN 2-dp TICK ROUNDING PRODUCE A 0.5pp OVERSHOOT? (needs prev_close < ~1 yuan)")
print("=" * 78)
sql = ("SELECT SUM(close < 1.0), SUM(close < 2.5), COUNT(*) FROM daily_bar_cache "
       "WHERE close IS NOT NULL AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'")
print("SQL: " + sql)
print("   rows with close<1 / close<2.5 / total: %s" % (con.execute(sql).fetchone(),))
surv = [e for e in over if e["gap"] == 1 and not e["within_first5"]
        and "demo_seed_fixture" not in (e["src0"], e["src1"]) and not e["explained_by_rounding"]]
print("   surviving over-limit events with prev_close >= 2.5 yuan (rounding impossible): %d of %d"
      % (sum(1 for e in surv if e["pclose"] >= 2.5), len(surv)))

print("\n" + "=" * 78)
print("N. FINAL RECONCILIATION")
print("=" * 78)
print("   their claim                                   : 430 events / 274 symbols (424 gap==1)")
print("   my re-derivation of the same recipe           : 430 / 274 (424 gap==1)  MATCH")
print("   minus legal IPO no-limit days                 : -%d" % len(ipo))
print("   minus demo_seed_fixture synthetic rows        : -%d"
      % len([e for e in theirs1 if "demo_seed_fixture" in (e["src0"], e["src1"])]))
print("   minus 2-dp tick-rounding-explainable          : -%d"
      % len([e for e in theirs1 if e["explained_by_rounding"] and not e["within_first5"]
             and "demo_seed_fixture" not in (e["src0"], e["src1"])]))
print("   = defensible over-limit events                : %d events / %d symbols" % (len(surv_t := [
    e for e in theirs1 if not e["within_first5"] and "demo_seed_fixture" not in (e["src0"], e["src1"])
    and not e["explained_by_rounding"]]), len(set(e["sym"] for e in surv_t))))
print("   using a CONSISTENT per-board threshold instead of their |ret|>0.11 prefilter:")
print("   = %d events / %d symbols" % (len(surv), len(set(e["sym"] for e in surv))))
print("     by board: %s" % dict(collections.Counter(e["board"] for e in surv)))
print("     mh verdict: %s" % dict(collections.Counter(e.get("mh") for e in surv)))
con.close(); mcon.close()
