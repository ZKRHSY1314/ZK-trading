# -*- coding: utf-8 -*-
"""Adjustment-mode / corporate-action integrity audit. READ-ONLY."""
import sqlite3, sys, json, collections, statistics
sys.stdout.reconfigure(encoding='utf-8')
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
OUT = r"D:/codex-A股交易/claude methods/_m1_evidence"
W0, W1 = "2023-09-04", "2026-09-04"

con = sqlite3.connect("file:" + TL + "?mode=ro", uri=True)
con.execute("PRAGMA query_only=ON")
con.execute("ATTACH DATABASE 'file:" + MH + "?mode=ro' AS mh")
con.execute("PRAGMA mh.query_only=ON")


def board_of(sym):
    if sym.startswith("SH688") or sym.startswith("SH689"):
        return ("star", 0.20)
    if sym.startswith("SZ30"):
        return ("chi_next", 0.20)
    if sym.startswith("BJ"):
        return ("beijing", 0.30)
    if sym.startswith("SH60"):
        return ("sh_main", 0.10)
    if sym.startswith("SZ00"):
        return ("sz_main", 0.10)
    if sym.startswith("SH00"):
        return ("index", 9.99)
    return ("other", 9.99)


DATE_GLOB = "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]"

sessions = [r[0] for r in con.execute(
    "SELECT DISTINCT trade_date FROM daily_bar_cache WHERE trade_date GLOB ? ORDER BY trade_date",
    (DATE_GLOB,))]
sidx = {d: i for i, d in enumerate(sessions)}
print("[calendar] distinct valid trade_dates in daily_bar_cache = %d  (%s .. %s)"
      % (len(sessions), sessions[0], sessions[-1]))

SQL_MAIN = ("SELECT symbol, trade_date, close, source, adjustment_mode, volume_unit, quality_status "
            "FROM daily_bar_cache "
            "WHERE trade_date GLOB ? AND trade_date BETWEEN ? AND ? "
            "ORDER BY symbol, trade_date")
print("SQL_MAIN = " + SQL_MAIN)

sym_modes = collections.defaultdict(set)
sym_units = collections.defaultdict(set)
sym_sources = collections.defaultdict(set)
mode_ranges = collections.defaultdict(lambda: collections.defaultdict(lambda: [None, None, 0]))
src_ranges = collections.defaultdict(lambda: collections.defaultdict(lambda: [None, None, 0]))
boundaries = []
jumps = []
all_rets_n = 0

prev_sym = prev_date = prev_close = prev_src = None
n = 0
for sym, td, close, src, mode, unit, qs in con.execute(SQL_MAIN, (DATE_GLOB, W0, W1)):
    n += 1
    sym_modes[sym].add(mode)
    sym_units[sym].add(unit)
    sym_sources[sym].add(src)
    mr = mode_ranges[sym][mode]
    if mr[0] is None or td < mr[0]:
        mr[0] = td
    if mr[1] is None or td > mr[1]:
        mr[1] = td
    mr[2] += 1
    sr = src_ranges[sym][src]
    if sr[0] is None or td < sr[0]:
        sr[0] = td
    if sr[1] is None or td > sr[1]:
        sr[1] = td
    sr[2] += 1
    if sym == prev_sym:
        gap = sidx.get(td, -1) - sidx.get(prev_date, -1)
        if src != prev_src:
            r = (close / prev_close - 1.0) if (close and prev_close) else None
            boundaries.append((sym, prev_date, td, prev_src, src, prev_close, close, r, gap))
        if close and prev_close and prev_close > 0:
            ret = close / prev_close - 1.0
            all_rets_n += 1
            if abs(ret) > 0.11:
                b, lim = board_of(sym)
                jumps.append((sym, prev_date, td, prev_close, close, ret, b, lim, gap,
                              prev_src, src, mode, qs))
    prev_sym, prev_date, prev_close, prev_src = sym, td, close, src

print("[scan] rows scanned in window = %d ; consecutive-return pairs = %d" % (n, all_rets_n))

mix_modes = {s: v for s, v in sym_modes.items() if len(v) > 1}
mix_units = {s: v for s, v in sym_units.items() if len(v) > 1}
mix_srcs = {s: v for s, v in sym_sources.items() if len(v) > 1}

print("")
print("[1] symbols with >1 adjustment_mode across their series : %d" % len(mix_modes))
for s, v in sorted(mix_modes.items())[:60]:
    parts = "; ".join("%s:%s..%s(n=%d)" % (m, mode_ranges[s][m][0], mode_ranges[s][m][1],
                                           mode_ranges[s][m][2]) for m in sorted(v))
    print("    %s  modes=%s  %s" % (s, sorted(v), parts))
print("[1b] symbols with >1 volume_unit : %d" % len(mix_units))
for s, v in sorted(mix_units.items())[:20]:
    print("    %s %s" % (s, sorted(v)))
print("[1c] symbols with >1 source : %d  (out of %d symbols in window)" % (len(mix_srcs), len(sym_sources)))
cnt = collections.Counter(len(v) for v in sym_sources.values())
print("     distinct-source-count histogram: %s" % dict(sorted(cnt.items())))
combo = collections.Counter(tuple(sorted(v)) for v in sym_sources.values())
print("     top source-combinations per symbol:")
for k, c in combo.most_common(12):
    print("       %5d  %s" % (c, k))

print("")
print("[2] source-change boundaries inside window = %d  (symbols affected = %d)"
      % (len(boundaries), len(set(b[0] for b in boundaries))))
brets = [abs(b[7]) for b in boundaries if b[7] is not None]
if brets:
    bs = sorted(brets)

    def pct(a, p):
        return a[min(len(a) - 1, int(len(a) * p))]
    print("     |jump| at boundary: n=%d mean=%.5f p50=%.5f p90=%.5f p99=%.5f max=%.5f"
          % (len(brets), statistics.mean(brets), pct(bs, .5), pct(bs, .9), pct(bs, .99), bs[-1]))
    for thr in (0.005, 0.01, 0.02, 0.05, 0.11, 0.20, 0.50):
        c = sum(1 for x in brets if x > thr)
        print("       |jump|>%-6s: %6d  (%.3f%%)" % (thr, c, 100.0 * c / len(brets)))
print("     boundary examples (largest 15):")
for b in sorted([b for b in boundaries if b[7] is not None], key=lambda x: -abs(x[7]))[:15]:
    print("       %s %s->%s gap=%s %s -> %s  close %s -> %s  ret=%+.4f"
          % (b[0], b[1], b[2], b[8], b[3], b[4], b[5], b[6], b[7]))
bysrcpair = collections.Counter((b[3], b[4]) for b in boundaries)
print("     boundary source-pair counts:")
for k, c in bysrcpair.most_common(20):
    print("       %6d  %s  ->  %s" % (c, k[0], k[1]))

print("")
print("[3] |close_t/close_(t-1)-1| > 0.11 events in window = %d  (symbols = %d)"
      % (len(jumps), len(set(j[0] for j in jumps))))
print("     by board: %s" % dict(collections.Counter(j[6] for j in jumps)))
over_limit = [j for j in jumps if abs(j[5]) > j[7] + 0.005]
print("     [3a] jumps EXCEEDING that board's own price limit (+0.5pp tol) = %d  (symbols=%d)"
      % (len(over_limit), len(set(j[0] for j in over_limit))))
print("     by board (over-limit): %s" % dict(collections.Counter(j[6] for j in over_limit)))
gap1 = [j for j in over_limit if j[8] == 1]
print("     [3b] of those, CONSECUTIVE sessions (session_gap==1, no suspension) = %d (symbols=%d)"
      % (len(gap1), len(set(j[0] for j in gap1))))
srcchg = [j for j in gap1 if j[9] != j[10]]
print("     [3c] of those, at a source change = %d" % len(srcchg))
print("     session-gap histogram of over-limit jumps: %s"
      % dict(collections.Counter(min(j[8], 9) for j in over_limit).most_common()))
print("     largest 25 over-limit consecutive-session jumps:")
for j in sorted(gap1, key=lambda x: -abs(x[5]))[:25]:
    print("       %s %s->%s board=%s lim=%s close %s -> %s ret=%+.4f src %s -> %s"
          % (j[0], j[1], j[2], j[6], j[7], j[3], j[4], j[5], j[9], j[10]))

json.dump({"boundaries": boundaries, "jumps": jumps, "over_limit_gap1": gap1},
          open(OUT + "/adjustment_03_events.json", "w", encoding="utf-8"), ensure_ascii=False)
print("")
print("[saved] " + OUT + "/adjustment_03_events.json")
con.close()
