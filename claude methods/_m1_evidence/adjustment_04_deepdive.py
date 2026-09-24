# -*- coding: utf-8 -*-
"""Deep dive: baseline returns, source-splice level shifts, cache-vs-market_history
restatement, point-in-time availability. READ-ONLY."""
import sqlite3, sys, json, collections, statistics
sys.stdout.reconfigure(encoding='utf-8')
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
OUT = r"D:/codex-A股交易/claude methods/_m1_evidence"
W0, W1 = "2023-09-04", "2026-09-04"
DATE_GLOB = "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]"

con = sqlite3.connect("file:" + TL + "?mode=ro", uri=True)
con.execute("PRAGMA query_only=ON")
con.execute("ATTACH DATABASE 'file:" + MH + "?mode=ro' AS mh")
con.execute("PRAGMA mh.query_only=ON")


def hdr(t, sql):
    print("")
    print("### " + t)
    print("SQL: " + " ".join(sql.split()))


def run(t, sql, params=(), limit=None):
    hdr(t, sql)
    rows = con.execute(sql, params).fetchall()
    for r in (rows[:limit] if limit else rows):
        print("   ", r)
    return rows


ev = json.load(open(OUT + "/adjustment_03_events.json", encoding="utf-8"))
boundaries = ev["boundaries"]
jumps = ev["jumps"]

# ---------------------------------------------------------------- 1 baseline
print("=" * 78)
print("PART 1 - BASELINE: ordinary daily |return| vs source-boundary |return|")
print("=" * 78)
bset = set((b[0], b[2]) for b in boundaries)  # (symbol, date_t) that IS a boundary day
SQL_B = ("SELECT symbol, trade_date, close FROM daily_bar_cache "
         "WHERE trade_date GLOB ? AND trade_date BETWEEN ? AND ? ORDER BY symbol, trade_date")
print("SQL: " + SQL_B)
base_abs = []
bnd_abs = []
ps = pd = pc = None
for sym, td, close in con.execute(SQL_B, (DATE_GLOB, W0, W1)):
    if sym == ps and close and pc and pc > 0:
        r = abs(close / pc - 1.0)
        (bnd_abs if (sym, td) in bset else base_abs).append(r)
    ps, pd, pc = sym, td, close


def pcts(a):
    a = sorted(a)
    n = len(a)

    def p(q):
        return a[min(n - 1, int(n * q))]
    return dict(n=n, mean=round(statistics.mean(a), 6), p50=round(p(.5), 6),
                p75=round(p(.75), 6), p90=round(p(.9), 6), p95=round(p(.95), 6),
                p99=round(p(.99), 6), max=round(a[-1], 6))


print("   NON-boundary daily |ret| : %s" % pcts(base_abs))
print("   BOUNDARY   daily |ret| : %s" % pcts(bnd_abs))
for thr in (0.01, 0.02, 0.05, 0.11, 0.20):
    b1 = sum(1 for x in base_abs if x > thr) / len(base_abs)
    b2 = sum(1 for x in bnd_abs if x > thr) / len(bnd_abs)
    print("   P(|ret|>%-5s)  non-boundary=%.5f  boundary=%.5f  ratio=%.1fx"
          % (thr, b1, b2, (b2 / b1) if b1 else float('inf')))

# ------------------------------------------------- 2 the 2024-08-13 splice
print("")
print("=" * 78)
print("PART 2 - MASS SOURCE SPLICE (level re-basing)")
print("=" * 78)
bydate = collections.Counter(b[2] for b in boundaries)
print("   top boundary dates (date -> #symbols switching source that day):")
for d, c in bydate.most_common(15):
    sub = [abs(b[7]) for b in boundaries if b[2] == d and b[7] is not None]
    neg = [b[7] for b in boundaries if b[2] == d and b[7] is not None]
    med = statistics.median(sub) if sub else 0
    medsigned = statistics.median(neg) if neg else 0
    print("     %s  n=%-5d  median|jump|=%.4f  median signed jump=%+.4f  "
          "share>2%%=%.2f  share>10%%=%.2f"
          % (d, c, med, medsigned,
             sum(1 for x in sub if x > .02) / max(1, len(sub)),
             sum(1 for x in sub if x > .10) / max(1, len(sub))))

run("2b write-time lineage per source (created_at / updated_at spans)",
    "SELECT source, COUNT(*), MIN(created_at), MAX(created_at), MIN(updated_at), MAX(updated_at) "
    "FROM daily_bar_cache GROUP BY source ORDER BY 2 DESC")

run("2c write-time of the two segments of the 2024-08-12/13 splice",
    "SELECT source, substr(created_at,1,10) AS cday, substr(updated_at,1,10) AS uday, COUNT(*) "
    "FROM daily_bar_cache WHERE trade_date BETWEEN '2024-08-01' AND '2024-08-31' "
    "GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 25")

run("2d SH603093 full rows around the splice",
    "SELECT trade_date, open, high, low, close, volume, amount, source, adjustment_mode, "
    "quality_status, created_at, updated_at FROM daily_bar_cache "
    "WHERE symbol='SH603093' AND trade_date BETWEEN '2024-08-06' AND '2024-08-20' ORDER BY trade_date")

run("2e SH603093 same dates in market_history.daily_bars (qfq)",
    "SELECT trade_date, open, high, low, close, provider, fetched_at, available_at, ingest_run_id "
    "FROM mh.daily_bars WHERE symbol='SH603093' AND trade_date BETWEEN '2024-08-06' AND '2024-08-20' "
    "ORDER BY trade_date")

# --------------------------------------------- 3 cache vs market_history
print("")
print("=" * 78)
print("PART 3 - CACHE vs MARKET_HISTORY (both labelled qfq): restatement measure")
print("=" * 78)
run("3a common-key count and disagreement counts",
    "SELECT COUNT(*) AS common_keys, "
    "SUM(CASE WHEN abs(c.close - m.close) > 1e-9 THEN 1 ELSE 0 END) AS any_diff, "
    "SUM(CASE WHEN c.close>0 AND abs(m.close/c.close - 1.0) > 0.001 THEN 1 ELSE 0 END) AS diff_gt_0p1pct, "
    "SUM(CASE WHEN c.close>0 AND abs(m.close/c.close - 1.0) > 0.01 THEN 1 ELSE 0 END) AS diff_gt_1pct, "
    "SUM(CASE WHEN c.close>0 AND abs(m.close/c.close - 1.0) > 0.05 THEN 1 ELSE 0 END) AS diff_gt_5pct "
    "FROM daily_bar_cache c JOIN mh.daily_bars m "
    "ON m.symbol=c.symbol AND m.trade_date=c.trade_date AND m.adjustment_mode='qfq' "
    "WHERE c.adjustment_mode='qfq'")

run("3b disagreement broken out by market_history fetched_at day",
    "SELECT substr(m.fetched_at,1,10) AS mh_fetch_day, COUNT(*) AS keys, "
    "SUM(CASE WHEN c.close>0 AND abs(m.close/c.close - 1.0) > 0.001 THEN 1 ELSE 0 END) AS diff_gt_0p1pct, "
    "SUM(CASE WHEN c.close>0 AND abs(m.close/c.close - 1.0) > 0.01 THEN 1 ELSE 0 END) AS diff_gt_1pct "
    "FROM daily_bar_cache c JOIN mh.daily_bars m "
    "ON m.symbol=c.symbol AND m.trade_date=c.trade_date AND m.adjustment_mode='qfq' "
    "WHERE c.adjustment_mode='qfq' GROUP BY 1 ORDER BY 1")

run("3c largest cache-vs-history close disagreements",
    "SELECT c.symbol, c.trade_date, c.close AS cache_close, m.close AS hist_close, "
    "m.close/c.close - 1.0 AS rel, c.source, m.provider, m.fetched_at "
    "FROM daily_bar_cache c JOIN mh.daily_bars m "
    "ON m.symbol=c.symbol AND m.trade_date=c.trade_date AND m.adjustment_mode='qfq' "
    "WHERE c.adjustment_mode='qfq' AND c.close>0 AND abs(m.close/c.close-1.0)>0.05 "
    "ORDER BY abs(m.close/c.close-1.0) DESC LIMIT 25")

# -------------------------------------------------- 4 point in time
print("")
print("=" * 78)
print("PART 4 - POINT-IN-TIME evidence")
print("=" * 78)
run("4a available_at vs trade_date: is available_at ever near the trade date?",
    "SELECT CASE WHEN substr(available_at,1,10) <= trade_date THEN 'avail<=trade' "
    "WHEN julianday(substr(available_at,1,10)) - julianday(trade_date) <= 2 THEN 'avail within 2d' "
    "WHEN julianday(substr(available_at,1,10)) - julianday(trade_date) <= 30 THEN 'avail within 30d' "
    "ELSE 'avail >30d after trade' END AS rel, COUNT(*), MIN(trade_date), MAX(trade_date) "
    "FROM mh.daily_bars GROUP BY 1 ORDER BY 2 DESC")

run("4b rows visible to a point-in-time filter available_at<=as_of, for 3 as_of dates",
    "SELECT "
    "(SELECT COUNT(*) FROM mh.daily_bars WHERE available_at<='2024-06-30' AND trade_date<='2024-06-30') AS pit_2024_06_30, "
    "(SELECT COUNT(*) FROM mh.daily_bars WHERE available_at<='2025-06-30' AND trade_date<='2025-06-30') AS pit_2025_06_30, "
    "(SELECT COUNT(*) FROM mh.daily_bars WHERE available_at<='2026-06-30' AND trade_date<='2026-06-30') AS pit_2026_06_30, "
    "(SELECT COUNT(*) FROM mh.daily_bars WHERE available_at<='2026-09-04') AS pit_2026_09_04")

run("4c distinct (fetched_at, available_at) pairs",
    "SELECT fetched_at, available_at, COUNT(*) FROM mh.daily_bars GROUP BY 1,2 ORDER BY 3 DESC LIMIT 20")

run("4d any table anywhere holding split/dividend/corporate-action data? (market_history)",
    "SELECT name FROM mh.sqlite_master WHERE type='table' ORDER BY name")

run("4e any table anywhere holding split/dividend/corporate-action data? (trading_local)",
    "SELECT name FROM sqlite_master WHERE type='table' AND ("
    "lower(name) LIKE '%div%' OR lower(name) LIKE '%split%' OR lower(name) LIKE '%factor%' "
    "OR lower(name) LIKE '%corp%' OR lower(name) LIKE '%action%' OR lower(name) LIKE '%adjust%') "
    "ORDER BY name")

con.close()
