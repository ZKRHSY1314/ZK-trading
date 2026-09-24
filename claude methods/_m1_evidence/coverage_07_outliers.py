# -*- coding: utf-8 -*-
"""Outliers, amount coverage, staleness, store divergence. READ-ONLY."""
import sqlite3, pathlib, sys, csv

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
OP = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"
OUT = pathlib.Path(r"D:\codex-A股交易\claude methods\_m1_evidence")
W0, W1 = "2023-09-04", "2026-09-04"
FM0 = "2024-06-24"   # first full-market session (>=5000 stocks)


def rouri(p):
    return "file:" + pathlib.Path(p).as_posix() + "?mode=ro"


c = sqlite3.connect(rouri(OP), uri=True)
c.execute("ATTACH DATABASE ? AS mh", (rouri(MH),))


def show(label, sql, params=(), lim=40):
    print("### " + label)
    print("SQL:", " ".join(sql.split()))
    rows = list(c.execute(sql, params))
    for r in rows[:lim]:
        print("   ", r)
    if len(rows) > lim:
        print("    ... (%d rows total)" % len(rows))
    print(flush=True)


# --- low-coverage outliers from the manifest
mani = list(csv.DictReader(open(OUT / "coverage_manifest.csv", encoding="utf-8-sig")))
low = [r for r in mani if r["coverage_ratio"] and float(r["coverage_ratio"]) < 0.90]
low.sort(key=lambda r: float(r["coverage_ratio"]))
print("### manifest rows with coverage_ratio < 0.90 : %d" % len(low))
for r in low[:40]:
    print("   ", r["symbol"], r["name"], r["exchange"], "list=%s status=%s obs=%s elig=%s ratio=%s first=%s last=%s"
          % (r["list_date"], r["status"], r["observed_sessions"], r["eligible_sessions"],
             r["coverage_ratio"], r["window_first"], r["window_last"]))
print()
nul = [r for r in mani if r["eligibility_basis"] == "unknown_list_date"]
print("### manifest rows with unknown_list_date : %d" % len(nul))
for r in nul:
    print("   ", r["symbol"], r["name"], r["exchange"], "status=%s obs=%s first=%s last=%s"
          % (r["status"], r["observed_sessions"], r["window_first"], r["window_last"]))
print()

# --- full-market sub-window coverage (2024-06-24 .. 2026-09-04)
show("cache: sessions in full-market sub-window",
     "SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ?", (FM0, W1))
show("cache: valid STOCK rows in full-market sub-window",
     """SELECT COUNT(*) FROM daily_bar_cache d JOIN mh.instruments i ON i.symbol=d.symbol
        WHERE i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ') AND d.trade_date BETWEEN ? AND ?
          AND d.open IS NOT NULL AND d.high IS NOT NULL AND d.low IS NOT NULL AND d.close IS NOT NULL AND d.close>0""",
     (FM0, W1))
show("cache: valid STOCK rows in ramp sub-window 2024-04-09..2024-06-21",
     """SELECT COUNT(*), COUNT(DISTINCT d.symbol) FROM daily_bar_cache d JOIN mh.instruments i ON i.symbol=d.symbol
        WHERE i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ') AND d.trade_date BETWEEN '2024-04-09' AND '2024-06-21'""")
show("cache: breadth on the last 3 sessions",
     """SELECT d.trade_date, COUNT(DISTINCT d.symbol) FROM daily_bar_cache d JOIN mh.instruments i ON i.symbol=d.symbol
        WHERE i.asset_type='stock' AND d.trade_date >= '2026-09-01' GROUP BY 1 ORDER BY 1""")

# --- amount (turnover) coverage
show("cache: amount NULL by year (in window)",
     """SELECT substr(trade_date,1,4) yr, COUNT(*) n, SUM(amount IS NULL) amt_null,
               ROUND(100.0*SUM(amount IS NULL)/COUNT(*),2) pct_null
        FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ? GROUP BY 1 ORDER BY 1""", (W0, W1))
show("mh: amount NULL by year (in window)",
     """SELECT substr(trade_date,1,4) yr, COUNT(*) n, SUM(amount IS NULL) amt_null,
               ROUND(100.0*SUM(amount IS NULL)/COUNT(*),2) pct_null
        FROM mh.daily_bars WHERE trade_date BETWEEN ? AND ? GROUP BY 1 ORDER BY 1""", (W0, W1))
show("cache: amount NULL by source",
     """SELECT source, COUNT(*), SUM(amount IS NULL), ROUND(100.0*SUM(amount IS NULL)/COUNT(*),2)
        FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ? GROUP BY 1 ORDER BY 2 DESC""", (W0, W1))
show("cache: sessions where EVERY stock row has NULL amount",
     """SELECT COUNT(*) FROM (SELECT trade_date FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ?
        GROUP BY trade_date HAVING SUM(amount IS NOT NULL)=0)""", (W0, W1))

# --- volume==0 (suspension proxy) and zero-range bars
show("cache: volume=0 rows in window (suspension-like)",
     "SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ? AND volume=0", (W0, W1))
show("cache: zero-range bars (open=high=low=close) in window",
     """SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ?
        AND open=high AND high=low AND low=close""", (W0, W1))
show("mh: volume=0 rows in window", "SELECT COUNT(*) FROM mh.daily_bars WHERE trade_date BETWEEN ? AND ? AND volume=0", (W0, W1))

# --- staleness of updated_at
show("cache: updated_at recency buckets",
     """SELECT substr(updated_at,1,7) ym, COUNT(*) FROM daily_bar_cache GROUP BY 1 ORDER BY 1""")
show("mh: fetched_at recency buckets",
     """SELECT substr(fetched_at,1,7) ym, COUNT(*) FROM mh.daily_bars GROUP BY 1 ORDER BY 1""")

# --- store divergence: rows in cache but not in mh and vice versa (stock symbols, in window)
show("STOCK (symbol,date) in cache but NOT in mh.daily_bars(qfq)",
     """SELECT COUNT(*) FROM daily_bar_cache d JOIN mh.instruments i ON i.symbol=d.symbol
        WHERE i.asset_type='stock' AND d.trade_date BETWEEN ? AND ?
          AND NOT EXISTS (SELECT 1 FROM mh.daily_bars b WHERE b.symbol=d.symbol AND b.trade_date=d.trade_date)""",
     (W0, W1))
show("STOCK (symbol,date) in mh but NOT in cache",
     """SELECT COUNT(*) FROM mh.daily_bars b
        WHERE b.trade_date BETWEEN ? AND ?
          AND NOT EXISTS (SELECT 1 FROM daily_bar_cache d WHERE d.symbol=b.symbol AND d.trade_date=b.trade_date)""",
     (W0, W1))
show("close disagreement between stores (>0.5% relative) on shared keys",
     """SELECT COUNT(*) FROM daily_bar_cache d JOIN mh.daily_bars b
          ON b.symbol=d.symbol AND b.trade_date=d.trade_date
        WHERE d.trade_date BETWEEN ? AND ? AND d.close>0 AND b.close>0
          AND abs(d.close-b.close)/b.close > 0.005""", (W0, W1))
show("shared-key count between stores",
     """SELECT COUNT(*) FROM daily_bar_cache d JOIN mh.daily_bars b
          ON b.symbol=d.symbol AND b.trade_date=d.trade_date WHERE d.trade_date BETWEEN ? AND ?""", (W0, W1))
