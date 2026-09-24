# -*- coding: utf-8 -*-
"""How many over-limit events survive the exclusions the audit omitted?
Plus an independent market_history cross-check and BJ deep dive. READ-ONLY."""
import sqlite3, sys, collections, json
sys.stdout.reconfigure(encoding='utf-8')
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
W0, W1 = "2023-09-04", "2026-09-04"

con = sqlite3.connect("file:" + TL + "?mode=ro", uri=True)
con.execute("PRAGMA query_only=ON")
mcon = sqlite3.connect("file:" + MH + "?mode=ro", uri=True)
mcon.execute("PRAGMA query_only=ON")

over = json.load(open(r"D:/codex-A股交易/claude methods/_m1_evidence/adjrefute_over2.json"))
mi = {}
for sym, name, board, ld, dd, st in mcon.execute(
        "SELECT symbol, name, board, list_date, delist_date, status FROM instruments"):
    mi[sym] = dict(name=name, board=board, list_date=ld, delist_date=dd, status=st)

print("=" * 78)
print("F. list_date availability for the affected symbols")
print("=" * 78)
print("SQL: SELECT symbol, list_date FROM instruments WHERE symbol IN (affected symbols)")
aff = sorted(set(e["sym"] for e in over))
nolist = [s for s in aff if not mi.get(s, {}).get("list_date")]
print("affected symbols=%d ; with NULL/absent list_date=%d -> listing status unknowable: %s"
      % (len(aff), len(nolist), nolist[:20]))
print("SQL: SELECT COUNT(*) FROM instruments WHERE list_date IS NULL")
print("   whole universe with NULL list_date: %s"
      % mcon.execute("SELECT COUNT(*) FROM instruments WHERE list_date IS NULL").fetchone())

# ------------------------------------------------------------------ reconstruct their 430
theirs = [e for e in over if abs(e["ret"]) > 0.11]
theirs1 = [e for e in theirs if e["gap"] == 1]
print("\n" + "=" * 78)
print("G. THEIR HEADLINE SET, RE-DERIVED, THEN CLEANED")
print("=" * 78)
print("their 430 reproduced      : %d events / %d symbols" % (len(theirs), len(set(e['sym'] for e in theirs))))
print("their 424 (gap==1)        : %d events / %d symbols" % (len(theirs1), len(set(e['sym'] for e in theirs1))))

def cleaned(pool, label):
    ipo = [e for e in pool if e["within_first5"]]
    fixture = [e for e in pool if "demo_seed_fixture" in (e["src0"], e["src1"])]
    rnd = [e for e in pool if e["explained_by_rounding"]]
    drop = set(id(e) for e in ipo) | set(id(e) for e in fixture) | set(id(e) for e in rnd)
    surv = [e for e in pool if id(e) not in drop]
    print("\n%s: n=%d" % (label, len(pool)))
    print("   - IPO no-limit window (new listing, event in its first 5 bars): %d" % len(ipo))
    print("   - demo_seed_fixture rows (synthetic test data)               : %d" % len(fixture))
    print("   - explainable by 2-dp tick rounding alone                    : %d" % len(rnd))
    print("   = SURVIVING unexplained over-limit events: %d  (symbols=%d)"
          % (len(surv), len(set(e['sym'] for e in surv))))
    print("     by board: %s" % dict(collections.Counter(e["board"] for e in surv)))
    return surv

surv_theirs = cleaned(theirs1, "their 424 consecutive-session set")
surv_mine = cleaned([e for e in over if e["gap"] == 1], "my full 611 consecutive-session set")

# ------------------------------------------------------------------ H. independent mh cross-check
print("\n" + "=" * 78)
print("H. INDEPENDENT market_history CROSS-CHECK (my own query, bulk not per-row)")
print("=" * 78)
print("SQL: SELECT symbol, trade_date, close FROM daily_bars "
      "WHERE symbol=? AND trade_date IN (?,?)  -- executed as one IN-list per symbol")

need = collections.defaultdict(set)
for e in surv_mine + surv_theirs:
    need[e["sym"]].update([e["d0"], e["d1"]])
mhclose = {}
mcur = mcon.cursor()
for s, ds in need.items():
    ql = ",".join("?" * len(ds))
    for d, c in mcur.execute(
            "SELECT trade_date, close FROM daily_bars WHERE symbol=? AND trade_date IN (%s)" % ql,
            [s] + sorted(ds)):
        mhclose[(s, d)] = c

def xcheck(pool, label):
    cnt = collections.Counter()
    detail = []
    for e in pool:
        a = mhclose.get((e["sym"], e["d0"]))
        b = mhclose.get((e["sym"], e["d1"]))
        if a is None or b is None or not a:
            cnt["mh_absent (no second source)"] += 1
            e["mh"] = "absent"
            continue
        mret = b / a - 1.0
        if abs(mret - e["ret"]) < 0.005:
            cnt["mh_confirms_the_same_move"] += 1
            e["mh"] = "confirms"
        elif abs(mret) <= e["lim"] + 0.005:
            cnt["mh_shows_a_LEGAL_move -> cache-only artefact"] += 1
            e["mh"] = "cache_only"
            detail.append((e["sym"], e["d0"], e["d1"], e["board"], round(e["ret"], 4), round(mret, 4), e["src1"][:26]))
        else:
            cnt["mh_also_over_limit_but_different_size"] += 1
            e["mh"] = "differs"
            detail.append((e["sym"], e["d0"], e["d1"], e["board"], round(e["ret"], 4), round(mret, 4), e["src1"][:26]))
    print("\n%s (n=%d):" % (label, len(pool)))
    for k, v in cnt.most_common():
        print("   %-48s %4d  (%.1f%%)" % (k, v, 100.0 * v / max(1, len(pool))))
    return cnt, detail

c1, d1 = xcheck(surv_theirs, "surviving subset of THEIR 424")
c2, d2 = xcheck(surv_mine, "surviving subset of MY 611")
print("\n   cache-only / differing examples (cache_ret vs market_history_ret):")
for x in d2[:20]:
    print("     %-9s %s->%s %-8s cache=%+.4f mh=%+.4f  %s" % x)

# ------------------------------------------------------------------ I. BJ coverage
print("\n" + "=" * 78)
print("I. BJ SECOND-SOURCE COVERAGE (is the BJ cluster really unverifiable?)")
print("=" * 78)
for sql, lbl in [
    ("SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date), MAX(trade_date) "
     "FROM daily_bars WHERE symbol LIKE 'BJ%'", "market_history BJ rows"),
]:
    print("SQL: " + sql)
    print("   %s -> %s" % (lbl, mcon.execute(sql).fetchone()))
sql = ("SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date), MAX(trade_date) "
       "FROM daily_bar_cache WHERE symbol LIKE 'BJ%' AND trade_date GLOB "
       "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'")
print("SQL: " + sql)
print("   cache BJ rows -> %s" % (con.execute(sql).fetchone(),))
sql = ("SELECT substr(trade_date,1,7) AS ym, COUNT(*) FROM daily_bars WHERE symbol LIKE 'BJ%' "
       "GROUP BY 1 ORDER BY 1")
print("SQL: " + sql)
rows = mcon.execute(sql).fetchall()
print("   mh BJ rows per month: first 6 %s ... last 6 %s" % (rows[:6], rows[-6:]))
sql = ("SELECT substr(trade_date,1,7) AS ym, COUNT(*) FROM daily_bar_cache WHERE symbol LIKE 'BJ%' "
       "AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' GROUP BY 1 ORDER BY 1")
print("SQL: " + sql)
rows2 = con.execute(sql).fetchall()
print("   cache BJ rows per month: first 6 %s ... last 6 %s" % (rows2[:6], rows2[-6:]))

bj = [e for e in surv_mine if e["board"] == "beijing"]
print("\n   surviving BJ over-limit events: %d ; mh verdicts: %s"
      % (len(bj), dict(collections.Counter(e.get("mh") for e in bj))))
print("   their |ret| distribution: %s"
      % [round(x, 3) for x in sorted(abs(e["ret"]) for e in bj)[:12]])
print("   BJ event month histogram: %s"
      % dict(sorted(collections.Counter(e["d1"][:7] for e in bj).items())))

# BJ intraday consistency: does the same bar's own OPEN also breach the band?
print("\n   BJ bar-level check: is the flagged bar internally consistent with a 30% band?")
print("   SQL: SELECT trade_date,open,high,low,close FROM daily_bar_cache WHERE symbol=? AND trade_date IN (?,?)")
bad_open = 0
sample = []
for e in bj[:400]:
    r = con.execute("SELECT open, high, low, close FROM daily_bar_cache WHERE symbol=? AND trade_date=?",
                    (e["sym"], e["d1"])).fetchone()
    r0 = con.execute("SELECT open, high, low, close FROM daily_bar_cache WHERE symbol=? AND trade_date=?",
                     (e["sym"], e["d0"])).fetchone()
    if not r or not r0:
        continue
    hi_ret = r[1] / e["pclose"] - 1.0
    lo_ret = r[2] / e["pclose"] - 1.0
    if hi_ret > 0.305 or lo_ret < -0.305:
        bad_open += 1
    if len(sample) < 12:
        sample.append((e["sym"], e["d0"], e["d1"], r0, r, round(e["ret"], 4),
                       round(hi_ret, 4), round(lo_ret, 4)))
print("   BJ flagged bars whose own HIGH/LOW also breaches +-30.5%% of prev close: %d of %d"
      % (bad_open, len(bj)))
for s in sample:
    print("     %-9s %s(o/h/l/c=%s) -> %s(o/h/l/c=%s) ret=%+.4f hi_ret=%+.4f lo_ret=%+.4f"
          % (s[0], s[1], s[3], s[2], s[4], s[5], s[6], s[7]))

json.dump(surv_mine, open(r"D:/codex-A股交易/claude methods/_m1_evidence/adjrefute_survivors.json", "w"),
          ensure_ascii=False)
con.close()
mcon.close()
