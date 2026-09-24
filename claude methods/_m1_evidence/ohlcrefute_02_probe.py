# -*- coding: utf-8 -*-
"""ADVERSARIAL VERIFY part 2. READ-ONLY."""
import sqlite3, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OPS = r"D:/codex-A股交易/trading_local.sqlite3"
HIS = r"D:/codex-A股交易/market_history.sqlite3"


def ro(p):
    c = sqlite3.connect("file:{}?mode=ro".format(p), uri=True)
    c.row_factory = sqlite3.Row
    return c


def show(title, sql, conn, params=(), lim=60):
    print("\n" + "=" * 100)
    print("## " + title)
    print("SQL: " + " ".join(sql.split()))
    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception as exc:
        print("  ERROR: %r" % (exc,))
        return []
    if not rows:
        print("  (no rows)")
        return rows
    print("  cols: " + " | ".join(rows[0].keys()))
    for r in rows[:lim]:
        print("  " + " | ".join("NULL" if v is None else repr(v) for v in tuple(r)))
    if len(rows) > lim:
        print("  ... {} more rows".format(len(rows) - lim))
    return rows


ops = ro(OPS)
his = ro(HIS)

print("#" * 100)
print("# G. THE 'ERROR' TRADE_DATE -- a malformed date the OHLC/date audit did not report")
print("#" * 100)

show("G1 every trade_date value that is not a well-formed YYYY-MM-DD", """
SELECT trade_date, COUNT(*) AS rows_, COUNT(DISTINCT symbol) AS syms,
       GROUP_CONCAT(DISTINCT quality_status) AS qs, GROUP_CONCAT(DISTINCT source) AS sources
FROM daily_bar_cache
WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
GROUP BY trade_date ORDER BY rows_ DESC
""", ops)

show("G2 full row dump of the malformed-date rows", """
SELECT symbol, trade_date, open, high, low, close, volume, amount, source,
       quality_status, adjustment_mode, volume_unit, created_at, updated_at
FROM daily_bar_cache
WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
ORDER BY symbol LIMIT 40
""", ops)

show("G3 does the string window filter silently mis-bucket them?", """
SELECT SUM(CASE WHEN trade_date BETWEEN '2023-09-04' AND '2026-09-04' THEN 1 ELSE 0 END) AS in_window,
       SUM(CASE WHEN trade_date > '2026-09-04' THEN 1 ELSE 0 END) AS after_window_lexical,
       SUM(CASE WHEN trade_date < '2023-09-04' THEN 1 ELSE 0 END) AS before_window_lexical,
       COUNT(*) AS malformed_rows
FROM daily_bar_cache
WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
""", ops)

show("G4 real max trade_date once malformed values are excluded", """
SELECT MIN(trade_date) AS real_min, MAX(trade_date) AS real_max, COUNT(*) AS rows_
FROM daily_bar_cache
WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
""", ops)

print("\n" + "#" * 100)
print("# H. WHAT ARE THE 2 EXTRA CACHE SYMBOLS vs instruments? (indices masquerading as stocks)")
print("#" * 100)

cache_syms = {r[0] for r in ops.execute(
    "SELECT DISTINCT symbol FROM daily_bar_cache WHERE LENGTH(symbol)=8").fetchall()}
inst_syms = {r[0] for r in his.execute("SELECT DISTINCT symbol FROM instruments").fetchall()}
hist_syms = {r[0] for r in his.execute("SELECT DISTINCT symbol FROM daily_bars").fetchall()}
print("SQL(a): SELECT DISTINCT symbol FROM daily_bar_cache WHERE LENGTH(symbol)=8   -> %d" % len(cache_syms))
print("SQL(b): SELECT DISTINCT symbol FROM instruments                              -> %d" % len(inst_syms))
print("SQL(c): SELECT DISTINCT symbol FROM daily_bars                               -> %d" % len(hist_syms))
print("\nH1 cache prefixed symbols NOT in market_history.instruments (set difference a-b): %d"
      % len(cache_syms - inst_syms))
print("   " + ", ".join(sorted(cache_syms - inst_syms)))
print("\nH2 instruments NOT in cache (b-a): %d" % len(inst_syms - cache_syms))
print("   " + ", ".join(sorted(inst_syms - cache_syms)[:40]))
print("\nH3 instruments NOT in market_history.daily_bars (b-c): %d" % len(inst_syms - hist_syms))
print("   " + ", ".join(sorted(inst_syms - hist_syms)[:40]))

show("H4 the two non-instrument cache symbols in detail", """
SELECT symbol, COUNT(*) AS rows_, MIN(trade_date) AS min_d, MAX(trade_date) AS max_d,
       GROUP_CONCAT(DISTINCT source) AS sources, GROUP_CONCAT(DISTINCT quality_status) AS qs,
       GROUP_CONCAT(DISTINCT adjustment_mode) AS adjm, GROUP_CONCAT(DISTINCT volume_unit) AS vunit,
       ROUND(AVG(close),2) AS avg_close, SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) AS null_amount
FROM daily_bar_cache WHERE symbol IN ('SH000001','SH000300') GROUP BY symbol
""", ops)

print("\n" + "#" * 100)
print("# I. HOW MANY 'READY' CACHE SYMBOLS WOULD A FULL-UNIVERSE BACKTEST LOAD?")
print("#" * 100)

show("I1 engine's own predicate: quality_status='ready' with NO symbol filter", """
SELECT COUNT(DISTINCT symbol) AS symbols_engine_would_load, COUNT(*) AS rows_
FROM daily_bar_cache WHERE quality_status='ready'
""", ops)

show("I2 breakdown of that load: real stocks vs shadow spellings vs indices", """
SELECT CASE
         WHEN LENGTH(symbol)=6 THEN 'bare_shadow_spelling'
         WHEN symbol IN ('SH000001','SH000300') THEN 'index_not_a_stock'
         ELSE 'prefixed_stock' END AS bucket,
       COUNT(DISTINCT symbol) AS syms, COUNT(*) AS rows_
FROM daily_bar_cache WHERE quality_status='ready' GROUP BY 1 ORDER BY 2 DESC
""", ops)

print("\n" + "#" * 100)
print("# J. IS THE BARE SPELLING EVER REQUESTED? (does the alias have a live consumer?)")
print("#" * 100)

for tbl in ("forecast_decisions", "forecast_outcomes", "historical_backtest_runs",
            "universe_members", "positions", "orders"):
    for db, conn in (("ops", ops), ("his", his)):
        cols = [r[1] for r in conn.execute("PRAGMA table_info(%s)" % tbl).fetchall()]
        if not cols:
            continue
        symcol = next((c for c in cols if c.lower() in ("symbol", "code", "ticker", "instrument")), None)
        print("\n-- %s.%s cols=%s symcol=%s" % (db, tbl, cols[:14], symcol))
        if symcol:
            sql = ("SELECT LENGTH({c}) AS len, COUNT(*) AS rows_, COUNT(DISTINCT {c}) AS syms, "
                   "MIN({c}) AS ex FROM {t} GROUP BY 1 ORDER BY 1").format(c=symcol, t=tbl)
            print("   SQL: " + sql)
            for r in conn.execute(sql).fetchall():
                print("   " + " | ".join(repr(v) for v in tuple(r)))

ops.close()
his.close()
print("\nDONE")
