# -*- coding: utf-8 -*-
"""Final gaps: BJ coverage in market_history, missing-history composition,
per-symbol boundary counts, window session coverage. READ-ONLY."""
import sqlite3, sys, json, collections
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

run("9a market_history coverage by exchange prefix vs cache",
    "SELECT substr(symbol,1,2) AS px, COUNT(*) AS mh_rows, COUNT(DISTINCT symbol) AS mh_syms "
    "FROM mh.daily_bars GROUP BY 1 ORDER BY 2 DESC")
run("9b cache coverage by exchange prefix",
    "SELECT substr(symbol,1,2) AS px, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS syms "
    "FROM daily_bar_cache GROUP BY 1 ORDER BY 2 DESC")
run("9c symbols present in cache but absent from market_history",
    "SELECT COUNT(DISTINCT c.symbol) FROM daily_bar_cache c "
    "WHERE NOT EXISTS (SELECT 1 FROM mh.daily_bars m WHERE m.symbol=c.symbol)")
run("9d cache rows with NO matching market_history row (key-level)",
    "SELECT COUNT(*) FROM daily_bar_cache c WHERE c.adjustment_mode='qfq' AND NOT EXISTS "
    "(SELECT 1 FROM mh.daily_bars m WHERE m.symbol=c.symbol AND m.trade_date=c.trade_date "
    " AND m.adjustment_mode='qfq')")
run("9e those unmatched cache rows, by source",
    "SELECT c.source, COUNT(*), COUNT(DISTINCT c.symbol) FROM daily_bar_cache c "
    "WHERE c.adjustment_mode='qfq' AND NOT EXISTS "
    "(SELECT 1 FROM mh.daily_bars m WHERE m.symbol=c.symbol AND m.trade_date=c.trade_date "
    " AND m.adjustment_mode='qfq') GROUP BY 1 ORDER BY 2 DESC")

print("")
print("### 9f composition of the 173 'history_missing' over-limit jumps")
c = collections.Counter()
for j in over_gap1:
    c[(j[6], j[10])] += 1
print("    all 424 over-limit jumps by (board, source):")
for k, v in c.most_common():
    print("      %-30s %s" % (k, v))

print("")
print("### 9g per-symbol source-boundary counts")
bs = collections.Counter(b[0] for b in boundaries)
print("    SQL: derived from the ORDER BY symbol,trade_date scan in adjustment_03_mainpass.py")
print("    boundaries-per-symbol histogram: %s"
      % dict(sorted(collections.Counter(bs.values()).items())))
big = collections.Counter(b[0] for b in boundaries if b[7] is not None and abs(b[7]) > 0.02)
print("    symbols with >=2 breaks of |jump|>2%%: %d"
      % sum(1 for v in big.values() if v >= 2))

run("9h window session coverage: sessions present per calendar year",
    "SELECT substr(trade_date,1,4) AS yr, COUNT(DISTINCT trade_date) AS sessions, "
    "COUNT(*) AS rows FROM daily_bar_cache "
    "WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' GROUP BY 1 ORDER BY 1")

run("9i rows strictly before the research window start (warm-up)",
    "SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date < '2023-09-04' "
    "AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'")

run("9j rows in window 2023-09-04..2024-04-08 (first 7 months of the window)",
    "SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2024-04-08'")

run("9k market_history: same, sessions per year",
    "SELECT substr(trade_date,1,4) AS yr, COUNT(DISTINCT trade_date), COUNT(*) "
    "FROM mh.daily_bars GROUP BY 1 ORDER BY 1")

run("9l bar_quality_issues content (should flag exactly these problems)",
    "SELECT COUNT(*) FROM mh.bar_quality_issues")

con.close()
