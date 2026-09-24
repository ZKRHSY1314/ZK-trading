# -*- coding: utf-8 -*-
"""ADVERSARIAL: independent test of the '2024-04-09 floor' claim.
STRICT READ-ONLY."""
import sqlite3, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

OP = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"

def ro(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    return c

def show(title, sql, con, params=()):
    print("=" * 78)
    print(title)
    print("SQL:", " ".join(sql.split()))
    try:
        cur = con.execute(sql, params)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        print("COLS:", cols)
        for r in rows[:60]:
            print("   ", r)
        if len(rows) > 60:
            print(f"    ... {len(rows)-60} more rows")
    except Exception as e:
        print("  ERROR:", e)
    print()

op = ro(OP); mh = ro(MH)

print("#### A. Does ANY other table in trading_local carry bar-like dates? ####")
show("A1 tables in trading_local",
     "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name", op)

print("#### B. RAW floor without any GLOB filter — string min/max AND the odd row ####")
show("B1 raw MIN/MAX/COUNT with NO date filter at all (string ordering)",
     "SELECT MIN(trade_date), MAX(trade_date), COUNT(*), COUNT(DISTINCT trade_date), COUNT(DISTINCT symbol) FROM daily_bar_cache", op)

show("B2 every trade_date that FAILS the 10-char ISO shape (the 1 excluded row)",
     """SELECT trade_date, typeof(trade_date), length(trade_date), COUNT(*) AS n,
               COUNT(DISTINCT symbol) AS syms, MIN(symbol), MAX(symbol)
        FROM daily_bar_cache
        WHERE trade_date IS NULL OR trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
        GROUP BY 1,2,3 ORDER BY n DESC""", op)

show("B3 typeof census of trade_date (int-stored dates would sort BEFORE any text)",
     "SELECT typeof(trade_date) AS t, COUNT(*) n, MIN(trade_date), MAX(trade_date) FROM daily_bar_cache GROUP BY 1", op)

show("B4 alternate encodings: 8-digit YYYYMMDD, slash-separated, or with time suffix",
     """SELECT CASE
              WHEN trade_date GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN 'YYYYMMDD'
              WHEN trade_date GLOB '[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]' THEN 'slash'
              WHEN trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*' AND length(trade_date)>10 THEN 'iso+suffix'
              WHEN trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' THEN 'iso10'
              ELSE 'other' END AS shape,
            COUNT(*) n, MIN(trade_date), MAX(trade_date)
        FROM daily_bar_cache GROUP BY 1 ORDER BY n DESC""", op)

print("#### C. Floor by exchange/asset class — is the floor uniform, or an artifact of one segment? ####")
show("C1 floor per symbol-prefix bucket (stocks vs index-ish prefixes)",
     """SELECT substr(symbol,1,3) AS pfx, COUNT(*) n, COUNT(DISTINCT symbol) syms,
               MIN(trade_date) min_td, MAX(trade_date) max_td
        FROM daily_bar_cache
        GROUP BY 1 ORDER BY min_td ASC, n DESC LIMIT 40""", op)

show("C2 the 40 SYMBOLS with the earliest first bar (is 2024-04-09 truly global?)",
     """SELECT symbol, MIN(trade_date) first_td, MAX(trade_date) last_td, COUNT(*) n
        FROM daily_bar_cache GROUP BY symbol ORDER BY first_td ASC LIMIT 40""", op)

print("#### D. market_history.daily_bars — per adjustment_mode, and are there OTHER bar tables? ####")
show("D1 tables in market_history",
     "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name", mh)

show("D2 daily_bars floor per adjustment_mode + provider",
     """SELECT adjustment_mode, provider, COUNT(*) n, COUNT(DISTINCT symbol) syms,
               MIN(trade_date) min_td, MAX(trade_date) max_td
        FROM daily_bars GROUP BY 1,2 ORDER BY min_td ASC""", mh)

show("D3 40 earliest-starting symbols in market_history.daily_bars",
     """SELECT symbol, adjustment_mode, MIN(trade_date) first_td, COUNT(*) n
        FROM daily_bars GROUP BY symbol, adjustment_mode ORDER BY first_td ASC LIMIT 40""", mh)

print("#### E. Session count / calendar reality check in the window ####")
show("E1 distinct sessions inside 2023-09-04..2026-09-04 and inside 2024-04-09..2026-09-04",
     """SELECT
          (SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache
             WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04') AS sessions_full_window,
          (SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache
             WHERE trade_date BETWEEN '2024-04-09' AND '2026-09-04') AS sessions_from_floor,
          (SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache
             WHERE trade_date < '2024-04-09') AS sessions_before_floor,
          (SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date > '2026-09-04') AS rows_after_window_end,
          (SELECT MAX(trade_date) FROM daily_bar_cache) AS abs_max""", op)

show("E2 first 15 distinct sessions ascending (confirm no isolated pre-floor session)",
     """SELECT trade_date, COUNT(*) n, COUNT(DISTINCT symbol) syms
        FROM daily_bar_cache GROUP BY trade_date ORDER BY trade_date ASC LIMIT 15""", op)

op.close(); mh.close()
