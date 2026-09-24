# -*- coding: utf-8 -*-
"""Cross-check jumps against market_history qfq; split restatement by provider;
quantify blast radius. READ-ONLY."""
import sqlite3, sys, json, collections, statistics
sys.stdout.reconfigure(encoding='utf-8')
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
OUT = r"D:/codex-A股交易/claude methods/_m1_evidence"

con = sqlite3.connect("file:" + TL + "?mode=ro", uri=True)
con.execute("PRAGMA query_only=ON")
con.execute("ATTACH DATABASE 'file:" + MH + "?mode=ro' AS mh")
con.execute("PRAGMA mh.query_only=ON")


def run(t, sql, params=(), limit=None):
    print("")
    print("### " + t)
    print("SQL: " + " ".join(sql.split()))
    rows = con.execute(sql, params).fetchall()
    for r in (rows[:limit] if limit else rows):
        print("   ", r)
    return rows


ev = json.load(open(OUT + "/adjustment_03_events.json", encoding="utf-8"))
boundaries = ev["boundaries"]
over_gap1 = ev["over_limit_gap1"]

print("=" * 78)
print("PART 5 - RESTATEMENT split by whether cache.source == history.provider")
print("=" * 78)
run("5a same-provider vs different-provider disagreement",
    "SELECT CASE WHEN c.source = m.provider THEN 'same_provider' ELSE 'different_provider' END AS k, "
    "COUNT(*) AS keys, "
    "SUM(CASE WHEN c.close>0 AND abs(m.close/c.close-1.0)>0.001 THEN 1 ELSE 0 END) AS d_gt_0p1pct, "
    "SUM(CASE WHEN c.close>0 AND abs(m.close/c.close-1.0)>0.01  THEN 1 ELSE 0 END) AS d_gt_1pct, "
    "SUM(CASE WHEN c.close>0 AND abs(m.close/c.close-1.0)>0.05  THEN 1 ELSE 0 END) AS d_gt_5pct "
    "FROM daily_bar_cache c JOIN mh.daily_bars m "
    "ON m.symbol=c.symbol AND m.trade_date=c.trade_date AND m.adjustment_mode='qfq' "
    "WHERE c.adjustment_mode='qfq' GROUP BY 1")

run("5b SAME-provider disagreement = pure qfq restatement over time, by fetch day",
    "SELECT substr(m.fetched_at,1,10) AS mh_fetch_day, COUNT(*) AS keys, "
    "SUM(CASE WHEN c.close>0 AND abs(m.close/c.close-1.0)>0.001 THEN 1 ELSE 0 END) AS d_gt_0p1pct, "
    "SUM(CASE WHEN c.close>0 AND abs(m.close/c.close-1.0)>0.01 THEN 1 ELSE 0 END) AS d_gt_1pct, "
    "SUM(CASE WHEN c.close>0 AND abs(m.close/c.close-1.0)>0.05 THEN 1 ELSE 0 END) AS d_gt_5pct "
    "FROM daily_bar_cache c JOIN mh.daily_bars m "
    "ON m.symbol=c.symbol AND m.trade_date=c.trade_date AND m.adjustment_mode='qfq' "
    "WHERE c.adjustment_mode='qfq' AND c.source=m.provider GROUP BY 1 ORDER BY 1")

run("5c symbols whose ENTIRE overlapping history is off by a constant factor "
    "(classic split/bonus restatement)",
    "SELECT symbol, COUNT(*) AS n, MIN(rel) AS min_rel, MAX(rel) AS max_rel FROM ("
    " SELECT c.symbol AS symbol, m.close/c.close AS rel FROM daily_bar_cache c "
    " JOIN mh.daily_bars m ON m.symbol=c.symbol AND m.trade_date=c.trade_date "
    "   AND m.adjustment_mode='qfq' "
    " WHERE c.adjustment_mode='qfq' AND c.close>0) GROUP BY symbol "
    "HAVING MAX(rel)-MIN(rel) < 0.02 AND (MIN(rel) > 1.02 OR MAX(rel) < 0.98) "
    "ORDER BY n DESC LIMIT 30")

run("5d count of symbols with a persistent constant restatement factor",
    "SELECT COUNT(*) FROM ("
    " SELECT symbol FROM ("
    "  SELECT c.symbol AS symbol, m.close/c.close AS rel FROM daily_bar_cache c "
    "  JOIN mh.daily_bars m ON m.symbol=c.symbol AND m.trade_date=c.trade_date "
    "    AND m.adjustment_mode='qfq' "
    "  WHERE c.adjustment_mode='qfq' AND c.close>0) GROUP BY symbol "
    " HAVING MAX(rel)-MIN(rel) < 0.02 AND (MIN(rel) > 1.02 OR MAX(rel) < 0.98))")

# --------------------------------------------------------- 6 jump cross-check
print("")
print("=" * 78)
print("PART 6 - Do the cache jumps also exist in the market_history qfq series?")
print("=" * 78)
print("SQL (per event): SELECT close FROM mh.daily_bars "
      "WHERE symbol=? AND trade_date=? AND adjustment_mode='qfq'")
cur = con.cursor()
mh_cache = {}


def mh_close(sym, d):
    k = (sym, d)
    if k not in mh_cache:
        r = cur.execute("SELECT close FROM mh.daily_bars WHERE symbol=? AND trade_date=? "
                        "AND adjustment_mode='qfq'", (sym, d)).fetchone()
        mh_cache[k] = r[0] if r else None
    return mh_cache[k]


def classify(events, idx_sym=0, idx_d0=1, idx_d1=2, idx_ret=5):
    out = collections.Counter()
    detail = []
    for e in events:
        s, d0, d1, ret = e[idx_sym], e[idx_d0], e[idx_d1], e[idx_ret]
        a, b = mh_close(s, d0), mh_close(s, d1)
        if a is None or b is None or not a:
            out["history_missing"] += 1
            continue
        mret = b / a - 1.0
        if abs(mret - ret) < 0.005:
            out["history_shows_same_jump"] += 1
        elif abs(mret) < 0.11:
            out["history_shows_NO_jump(<11pct) -> unadjusted/spliced in cache"] += 1
            detail.append((s, d0, d1, round(ret, 4), round(mret, 4)))
        else:
            out["history_shows_different_jump"] += 1
            detail.append((s, d0, d1, round(ret, 4), round(mret, 4)))
    return out, detail


print("")
print("[6a] the 424 over-limit consecutive-session jumps, cross-checked:")
c1, d1 = classify(over_gap1)
for k, v in c1.most_common():
    print("     %-55s %d" % (k, v))
print("     examples (cache_ret vs history_ret):")
for x in d1[:25]:
    print("       %s %s->%s cache_ret=%+.4f history_ret=%+.4f" % x)

print("")
print("[6b] the 6294 source-change boundaries, cross-checked "
      "(jump defined as |ret|>0.02 to catch level re-basing):")
bnd_big = [b for b in boundaries if b[7] is not None and abs(b[7]) > 0.02]
print("     boundaries with |jump|>2%%: %d" % len(bnd_big))
c2 = collections.Counter()
d2 = []
for b in bnd_big:
    s, d0, dd, ret = b[0], b[1], b[2], b[7]
    a, bb = mh_close(s, d0), mh_close(s, dd)
    if a is None or bb is None or not a:
        c2["history_missing"] += 1
        continue
    mret = bb / a - 1.0
    if abs(mret - ret) < 0.005:
        c2["history_reproduces_the_break"] += 1
    elif abs(mret) < 0.02:
        c2["history_is_SMOOTH_here -> break is a cache splice artifact"] += 1
        d2.append((s, d0, dd, round(ret, 4), round(mret, 4)))
    else:
        c2["history_differs"] += 1
        d2.append((s, d0, dd, round(ret, 4), round(mret, 4)))
for k, v in c2.most_common():
    print("     %-58s %d" % (k, v))
print("     examples:")
for x in d2[:20]:
    print("       %s %s->%s cache_ret=%+.4f history_ret=%+.4f" % x)

# --------------------------------------------------------- 7 blast radius
print("")
print("=" * 78)
print("PART 7 - BLAST RADIUS (backtest-visible rows: quality_status='ready')")
print("=" * 78)
aff2 = set(b[0] for b in boundaries if b[7] is not None and abs(b[7]) > 0.02)
aff5 = set(b[0] for b in boundaries if b[7] is not None and abs(b[7]) > 0.05)
aff10 = set(b[0] for b in boundaries if b[7] is not None and abs(b[7]) > 0.10)
print("     symbols with >=1 source-splice break  >2%%: %d" % len(aff2))
print("     symbols with >=1 source-splice break  >5%%: %d" % len(aff5))
print("     symbols with >=1 source-splice break >10%%: %d" % len(aff10))
run("7a total stock symbols the backtest can see",
    "SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE quality_status='ready' "
    "AND symbol NOT LIKE 'SH00%'")
run("7b rows the backtest can see, by adjustment_mode",
    "SELECT adjustment_mode, COUNT(*), COUNT(DISTINCT symbol) FROM daily_bar_cache "
    "WHERE quality_status='ready' GROUP BY 1")

# --------------------------------------------------------- 8 BJ cluster
print("")
print("=" * 78)
print("PART 8 - BJ / tonghuasun over-limit cluster: is the bar internally consistent?")
print("=" * 78)
run("8a BJ920976 OHLC around 2024-10-08",
    "SELECT trade_date, open, high, low, close, volume, amount, source, created_at, updated_at "
    "FROM daily_bar_cache WHERE symbol='BJ920976' AND trade_date BETWEEN '2024-09-25' "
    "AND '2024-10-15' ORDER BY trade_date")
run("8b BJ920976 in market_history",
    "SELECT trade_date, open, high, low, close, provider, fetched_at FROM mh.daily_bars "
    "WHERE symbol='BJ920976' AND trade_date BETWEEN '2024-09-25' AND '2024-10-15' "
    "ORDER BY trade_date")
bj = [j for j in over_gap1 if j[6] == 'beijing']
print("     over-limit BJ jump dates (top):",
      collections.Counter(j[2] for j in bj).most_common(10))
print("     over-limit BJ jump sources:",
      collections.Counter(j[10] for j in bj).most_common())
print("     over-limit sh_main/sz_main jump dates:",
      collections.Counter(j[2] for j in over_gap1 if j[6] in ('sh_main', 'sz_main')).most_common(10))

con.close()
