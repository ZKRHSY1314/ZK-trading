# -*- coding: utf-8 -*-
"""Decisive test: in a faithful adjusted series, limit-up days pile up at EXACTLY
the board limit. Measure where they actually pile up, by board and by source.
Also: the 2024-08-13 cluster, and an exact replication of their 424 cross-check.
READ-ONLY."""
import sqlite3, sys, collections, json
sys.stdout.reconfigure(encoding='utf-8')
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
W0, W1 = "2023-09-04", "2026-09-04"

con = sqlite3.connect("file:" + TL + "?mode=ro", uri=True)
con.execute("PRAGMA query_only=ON")
mcon = sqlite3.connect("file:" + MH + "?mode=ro", uri=True)
mcon.execute("PRAGMA query_only=ON")

board = {}
for s, b in mcon.execute("SELECT symbol, board FROM instruments"):
    board[s] = b
LIM = {"sh_main": 0.10, "sz_main": 0.10, "chi_next": 0.20, "star": 0.20, "beijing": 0.30}

SQL = """
SELECT symbol, trade_date, close, prev_close, high, source, prev_source
FROM (
  SELECT symbol, trade_date, close, high, source,
         LAG(close)  OVER w AS prev_close,
         LAG(source) OVER w AS prev_source,
         LAG(trade_date) OVER w AS prev_date
  FROM daily_bar_cache
  WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
    AND trade_date BETWEEN ? AND ?
  WINDOW w AS (PARTITION BY symbol ORDER BY trade_date)
)
WHERE prev_close > 0 AND close > 0
"""
print("### J. WHERE DO LIMIT-UP DAYS LAND?")
print("SQL: " + " ".join(SQL.split()))
print("A faithful qfq series puts every limit-up close at exactly +limit (the exchange")
print("computes the band off the ex-rights-adjusted previous close, which is exactly what")
print("qfq reconstructs). Bins are in percentage points of |ret| minus the board limit.\n")

hist = collections.defaultdict(collections.Counter)
srchist = collections.defaultdict(collections.Counter)
n = 0
for sym, td, close, pclose, high, src, psrc in con.execute(SQL, (W0, W1)):
    b = board.get(sym)
    lim = LIM.get(b)
    if lim is None:
        continue
    n += 1
    ret = close / pclose - 1.0
    if ret < lim - 0.004:
        continue
    # a limit-up close: close == high is the exchange signature
    excess = ret - lim
    if excess < -0.004:
        bin_ = "below"
    elif excess <= 0.0005:
        bin_ = "exact(+-0.05pp)"
    elif excess <= 0.002:
        bin_ = "0.05-0.2pp over"
    elif excess <= 0.005:
        bin_ = "0.2-0.5pp over"
    elif excess <= 0.02:
        bin_ = "0.5-2pp over"
    else:
        bin_ = ">2pp over"
    hist[b][bin_] += 1
    srchist[(b, src)][bin_] += 1

ORDER = ["below", "exact(+-0.05pp)", "0.05-0.2pp over", "0.2-0.5pp over", "0.5-2pp over", ">2pp over"]
print("pairs scanned on limit-bearing boards = %d\n" % n)
print("%-10s %8s %16s %16s %16s %14s %12s" % ("board", "below", "exact", "0.05-0.2pp", "0.2-0.5pp", "0.5-2pp", ">2pp"))
for b in ("sh_main", "sz_main", "chi_next", "star", "beijing"):
    h = hist[b]
    tot = sum(h.values())
    print("%-10s %8d %16s %16s %16s %14s %12s" % (
        b, h["below"],
        "%d (%.1f%%)" % (h["exact(+-0.05pp)"], 100.0 * h["exact(+-0.05pp)"] / max(1, tot)),
        "%d" % h["0.05-0.2pp over"], "%d" % h["0.2-0.5pp over"],
        "%d" % h["0.5-2pp over"], "%d" % h[">2pp over"]))

print("\n### J2 same, split by source (limit-up candidates only, top sources)")
print("%-10s %-34s %7s %10s %10s %10s %8s %7s" % ("board", "source", "below", "exact", "0.05-.2", "0.2-.5", "0.5-2", ">2pp"))
for (b, s), h in sorted(srchist.items(), key=lambda kv: -sum(kv[1].values()))[:16]:
    tot = sum(h.values())
    if tot < 30:
        continue
    print("%-10s %-34s %7d %10d %10d %10d %8d %7d" % (
        b, s[:34], h["below"], h["exact(+-0.05pp)"], h["0.05-0.2pp over"],
        h["0.2-0.5pp over"], h["0.5-2pp over"], h[">2pp over"]))

# ---------------------------------------------------------------- K. 2024-08-13
print("\n" + "=" * 78)
print("K. THE 2024-08-13 CLUSTER")
print("=" * 78)
sql = ("SELECT source, COUNT(*) FROM daily_bar_cache WHERE trade_date='2024-08-13' GROUP BY 1")
print("SQL: " + sql)
for r in con.execute(sql):
    print("   ", r)
sql = ("SELECT source, COUNT(*) FROM daily_bar_cache WHERE trade_date='2024-08-12' GROUP BY 1")
print("SQL: " + sql)
for r in con.execute(sql):
    print("   ", r)
sql = ("SELECT created_at, updated_at, COUNT(*) FROM daily_bar_cache WHERE trade_date='2024-08-13' "
       "GROUP BY substr(created_at,1,13), substr(updated_at,1,13) ORDER BY 3 DESC LIMIT 5")
print("SQL: " + sql)
for r in con.execute(sql):
    print("   ", r)
sql = ("SELECT trade_date, open, high, low, close, volume, amount, source, created_at, updated_at "
       "FROM daily_bar_cache WHERE symbol='SH603093' AND trade_date BETWEEN '2024-08-07' AND '2024-08-16' "
       "ORDER BY trade_date")
print("SQL: " + sql)
for r in con.execute(sql):
    print("   ", r)
sql = ("SELECT trade_date, open, high, low, close, provider, fetched_at FROM daily_bars "
       "WHERE symbol='SH603093' AND trade_date BETWEEN '2024-08-07' AND '2024-08-16' ORDER BY trade_date")
print("SQL(mh): " + sql)
for r in mcon.execute(sql):
    print("   ", r)

# ---------------------------------------------------------------- L. exact replication of their 424 xcheck
print("\n" + "=" * 78)
print("L. EXACT REPLICATION OF THEIR 424-EVENT CROSS-CHECK (uncleaned)")
print("=" * 78)
over = json.load(open(r"D:/codex-A股交易/claude methods/_m1_evidence/adjrefute_over2.json"))
theirs1 = [e for e in over if abs(e["ret"]) > 0.11 and e["gap"] == 1]
print("SQL(mh, per event): SELECT close FROM daily_bars WHERE symbol=? AND trade_date=? AND adjustment_mode='qfq'")
cur = mcon.cursor()
cache_mh = {}


def mhc(s, d):
    k = (s, d)
    if k not in cache_mh:
        r = cur.execute("SELECT close FROM daily_bars WHERE symbol=? AND trade_date=? "
                        "AND adjustment_mode='qfq'", (s, d)).fetchone()
        cache_mh[k] = r[0] if r else None
    return cache_mh[k]


c = collections.Counter()
for e in theirs1:
    a, b = mhc(e["sym"], e["d0"]), mhc(e["sym"], e["d1"])
    if a is None or b is None or not a:
        c["history_missing"] += 1
        continue
    mret = b / a - 1.0
    if abs(mret - e["ret"]) < 0.005:
        c["same_jump"] += 1
    elif abs(mret) < 0.11:
        c["no_jump_in_mh"] += 1
    else:
        c["different_jump"] += 1
print("   my replication of their 424 classification: %s (total %d)" % (dict(c), sum(c.values())))
print("   their published figures                  : same=203 no_jump=37 differ=11 missing=173")

print("\n   how much of 'history_missing' is simply that market_history's BJ series")
print("   starts 2025-11-17 while the cache's BJ series starts 2024-07-30:")
miss = [e for e in theirs1 if mhc(e["sym"], e["d0"]) is None or mhc(e["sym"], e["d1"]) is None]
print("   missing events by board: %s" % dict(collections.Counter(e["board"] for e in miss)))
print("   missing events by d1 year-month (top): %s"
      % collections.Counter(e["d1"][:7] for e in miss).most_common(8))
print("   missing events whose d1 < 2025-11-17 (before mh's BJ coverage begins): %d of %d"
      % (sum(1 for e in miss if e["d1"] < "2025-11-17"), len(miss)))

con.close()
mcon.close()
