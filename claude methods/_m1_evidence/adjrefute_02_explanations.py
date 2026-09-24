# -*- coding: utf-8 -*-
"""Can the over-limit events be explained by legitimate no-limit trading,
tick rounding, or ST rules?  READ-ONLY."""
import sqlite3, sys, collections, json, datetime
sys.stdout.reconfigure(encoding='utf-8')
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
EV = r"D:/codex-A股交易/claude methods/_m1_evidence/adjrefute_over.json"
W0, W1 = "2023-09-04", "2026-09-04"

con = sqlite3.connect("file:" + TL + "?mode=ro", uri=True)
con.execute("PRAGMA query_only=ON")
mcon = sqlite3.connect("file:" + MH + "?mode=ro", uri=True)
mcon.execute("PRAGMA query_only=ON")

over = json.load(open(EV))
print("loaded over-limit events (my derivation, no 0.11 prefilter): %d" % len(over))

mi = {}
for sym, name, board, ld, dd, st in mcon.execute(
        "SELECT symbol, name, board, list_date, delist_date, status FROM instruments"):
    mi[sym] = dict(name=name, board=board, list_date=ld, delist_date=dd, status=st)

sessions = [r[0] for r in con.execute(
    "SELECT DISTINCT trade_date FROM daily_bar_cache "
    "WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' "
    "AND trade_date BETWEEN ? AND ? ORDER BY trade_date", (W0, W1))]
sidx = {d: i for i, d in enumerate(sessions)}
CACHE_START = sessions[0]
print("cache calendar: %d sessions %s..%s" % (len(sessions), sessions[0], sessions[-1]))

# ------------------------------------------------------------------ A. IPO window
print("\n" + "=" * 78)
print("A. IPO NO-LIMIT WINDOW  (registration-system boards: first 5 sessions unlimited)")
print("=" * 78)
print("SQL: SELECT symbol, list_date FROM instruments  (market_history)")
print("SQL: per symbol -> ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY trade_date) from the scan")

ipo_syms = {s: v["list_date"] for s, v in mi.items()
            if v["list_date"] and v["list_date"] >= CACHE_START}
print("symbols whose instruments.list_date falls inside the cache's own date range: %d" % len(ipo_syms))

for e in over:
    ld = mi.get(e["sym"], {}).get("list_date")
    e["list_date"] = ld
    e["new_listing"] = bool(ld and ld >= CACHE_START)
    # sessions elapsed from the symbol's own first cached bar to the event's later date
    e["rn_of_d1"] = e["rn"]           # rn is the row index of d1 within the symbol
    e["within_first5"] = e["new_listing"] and e["rn"] <= 5

c = collections.Counter()
for e in over:
    c[(e["board"], e["new_listing"], e["rn"] <= 5)] += 1
print("\n(board, is_new_listing, event_within_first_5_bars) -> count")
for k, v in sorted(c.items()):
    print("   %-40s %d" % (str(k), v))

n_ipo = sum(1 for e in over if e["within_first5"])
print("\nover-limit events inside a genuine IPO no-limit window (first 5 bars of a symbol "
      "first listed after %s): %d of %d" % (CACHE_START, n_ipo, len(over)))
print("   by board: %s" % dict(collections.Counter(e["board"] for e in over if e["within_first5"])))

print("\nrow-number-within-symbol histogram for ALL over-limit events (rn=2 means the")
print("symbol's 2nd cached bar; a listing-window artefact would pile up at rn 2..5):")
print("   %s" % dict(sorted(collections.Counter(min(e["rn"], 12) for e in over).items())))
print("same histogram restricted to BJ:")
print("   %s" % dict(sorted(collections.Counter(min(e["rn"], 12) for e in over if e["board"] == "beijing").items())))

# ------------------------------------------------------------------ B. tick rounding
print("\n" + "=" * 78)
print("B. TICK-ROUNDING HEADROOM  (2-dp storage can inflate a legal limit move)")
print("=" * 78)
print("SQL: SELECT close, prev_close from the LAG scan; headroom = "
      "(close+0.005)/(prev_close-0.005)-1 minus close/prev_close-1")
for e in over:
    p, c2 = e["pclose"], e["close"]
    if c2 > p:
        worst = (c2 + 0.005) / (p - 0.005) - 1.0
    else:
        worst = (c2 - 0.005) / (p + 0.005) - 1.0
    e["rounding_headroom"] = abs(worst) - abs(e["ret"])
    e["explained_by_rounding"] = abs(e["ret"]) - e["rounding_headroom"] <= e["lim"]
n_round = sum(1 for e in over if e["explained_by_rounding"])
print("over-limit events that 2-dp rounding alone could explain: %d of %d" % (n_round, len(over)))
print("   price level of over-limit events: %s"
      % dict(sorted(collections.Counter(
          ("<1" if e["pclose"] < 1 else "1-2" if e["pclose"] < 2 else "2-5" if e["pclose"] < 5 else ">=5")
          for e in over).items())))

# ------------------------------------------------------------------ C. ST / 5pct board
print("\n" + "=" * 78)
print("C. ST / RISK-WARNING BOARD  (5% limit -> the audit's 10% limit UNDERCOUNTS)")
print("=" * 78)
st_syms = [s for s, v in mi.items() if v["name"] and "ST" in v["name"].upper()]
print("SQL: SELECT symbol,name FROM instruments WHERE upper(name) LIKE '%ST%'")
print("instruments currently flagged ST/*ST: %d" % len(st_syms))
print("over-limit events on currently-ST symbols: %d"
      % sum(1 for e in over if e["sym"] in set(st_syms)))

# ------------------------------------------------------------------ D. magnitudes
print("\n" + "=" * 78)
print("D. MAGNITUDE PROFILE  (a rules artefact sits just over the line; a splice does not)")
print("=" * 78)
for b in ("beijing", "sh_main", "sz_main", "chi_next", "star"):
    xs = sorted(abs(e["ret"]) - e["lim"] for e in over if e["board"] == b)
    if not xs:
        continue
    print("   %-9s n=%3d  excess over limit: p25=%.3f p50=%.3f p75=%.3f max=%.3f  "
          ">2x limit: %d" % (b, len(xs), xs[len(xs)//4], xs[len(xs)//2], xs[3*len(xs)//4], xs[-1],
                             sum(1 for e in over if e["board"] == b and abs(e["ret"]) > 2 * e["lim"])))

print("\n   20 largest over-limit moves:")
for e in sorted(over, key=lambda x: -abs(x["ret"]))[:20]:
    print("     %-9s %s->%s %-8s lim=%.2f  %8.3f -> %8.3f  ret=%+8.3f gap=%d rn=%d list=%s src=%s"
          % (e["sym"], e["d0"], e["d1"], e["board"], e["lim"], e["pclose"], e["close"],
             e["ret"], e["gap"], e["rn"], e["list_date"], e["src1"][:28]))

# ------------------------------------------------------------------ E. date clustering
print("\n" + "=" * 78)
print("E. DATE CLUSTERING  (a market-wide provider restatement lands on one day)")
print("=" * 78)
dc = collections.Counter(e["d1"] for e in over)
print("   top event dates: %s" % dc.most_common(15))
bjdc = collections.Counter(e["d1"] for e in over if e["board"] == "beijing")
print("   top BJ event dates: %s" % bjdc.most_common(15))

json.dump(over, open(r"D:/codex-A股交易/claude methods/_m1_evidence/adjrefute_over2.json", "w"),
          ensure_ascii=False)
con.close()
mcon.close()
