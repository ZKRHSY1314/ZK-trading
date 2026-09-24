# -*- coding: utf-8 -*-
"""Field-level usability inside the window: amount, volume, adjustment_mode, staleness. READ-ONLY."""
import sqlite3, pathlib, sys

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
OP = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"
W0, W1 = "2023-09-04", "2026-09-04"


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
        print("    ... (%d rows)" % len(rows))
    print(flush=True)


show("cache: amount NULL by year (window)",
     """SELECT substr(trade_date,1,4) yr, COUNT(*) n, SUM(amount IS NULL) amt_null,
               ROUND(100.0*SUM(amount IS NULL)/COUNT(*),2) pct
        FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ? GROUP BY 1 ORDER BY 1""", (W0, W1))
show("mh: amount NULL by year (window)",
     """SELECT substr(trade_date,1,4) yr, COUNT(*) n, SUM(amount IS NULL) amt_null,
               ROUND(100.0*SUM(amount IS NULL)/COUNT(*),2) pct
        FROM mh.daily_bars WHERE trade_date BETWEEN ? AND ? GROUP BY 1 ORDER BY 1""", (W0, W1))
show("cache: amount NULL by source (window)",
     """SELECT source, COUNT(*), SUM(amount IS NULL), ROUND(100.0*SUM(amount IS NULL)/COUNT(*),2)
        FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ? GROUP BY 1 ORDER BY 2 DESC""", (W0, W1))
show("mh: amount NULL by provider (window)",
     """SELECT provider, COUNT(*), SUM(amount IS NULL), ROUND(100.0*SUM(amount IS NULL)/COUNT(*),2)
        FROM mh.daily_bars WHERE trade_date BETWEEN ? AND ? GROUP BY 1 ORDER BY 2 DESC""", (W0, W1))
show("cache: adjustment_mode of in-window STOCK rows",
     """SELECT d.adjustment_mode, COUNT(*), COUNT(DISTINCT d.symbol) FROM daily_bar_cache d
        JOIN mh.instruments i ON i.symbol=d.symbol WHERE i.asset_type='stock'
          AND d.trade_date BETWEEN ? AND ? GROUP BY 1 ORDER BY 2 DESC""", (W0, W1))
show("cache: the 'none'/'unknown' adjustment rows - which symbols/dates",
     """SELECT adjustment_mode, quality_status, source, COUNT(*), MIN(trade_date), MAX(trade_date),
               COUNT(DISTINCT symbol)
        FROM daily_bar_cache WHERE adjustment_mode<>'qfq' GROUP BY 1,2,3 ORDER BY 4 DESC""")
show("cache: volume=0 in window", "SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ? AND volume=0", (W0, W1))
show("mh: volume=0 in window", "SELECT COUNT(*) FROM mh.daily_bars WHERE trade_date BETWEEN ? AND ? AND volume=0", (W0, W1))
show("cache: zero-range bars in window (o=h=l=c)",
     """SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ?
        AND open=high AND high=low AND low=close""", (W0, W1))
show("cache: updated_at month histogram", "SELECT substr(updated_at,1,7), COUNT(*) FROM daily_bar_cache GROUP BY 1 ORDER BY 1")
show("mh: fetched_at month histogram", "SELECT substr(fetched_at,1,7), COUNT(*) FROM mh.daily_bars GROUP BY 1 ORDER BY 1")
show("mh: available_at vs trade_date lag sample",
     """SELECT COUNT(*), SUM(CASE WHEN available_at < trade_date THEN 1 ELSE 0 END) avail_before_trade
        FROM mh.daily_bars WHERE trade_date BETWEEN ? AND ?""", (W0, W1))
