# -*- coding: utf-8 -*-
"""ADVERSARIAL VERIFICATION of: 'Tonghuashun adapter cannot backfill; tail-500 only'.
READ-ONLY. Every connection uses mode=ro."""
import sqlite3, bisect, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OPS = r"D:\codex-A股交易\trading_local.sqlite3"
RES = r"D:\codex-A股交易\market_history.sqlite3"
W0, W1 = "2023-09-04", "2026-09-04"
THS = "tonghuasun.local.quotes.candle"

def ro(p):
    return sqlite3.connect("file:" + p.replace("\\", "/") + "?mode=ro", uri=True)

def show(t, sql, rows):
    print("\n" + "=" * 78)
    print("[" + t + "]")
    print("SQL: " + " ".join(sql.split()))
    for r in rows:
        print("   ", r)

c = ro(OPS)
c.execute("ATTACH DATABASE ? AS mh", ["file:" + RES.replace("\\", "/") + "?mode=ro"])
# verify the attach really is read-only
try:
    c.execute("CREATE TABLE mh.__probe__(x)")
    print("!!! ATTACH IS WRITABLE - ABORT"); sys.exit(1)
except sqlite3.OperationalError as e:
    print("attach read-only confirmed:", e)

# ---------- 1. Date hygiene: is trade_date really lexicographic-safe? ----------
q = """SELECT length(trade_date) L, COUNT(*) n, MIN(trade_date), MAX(trade_date)
       FROM daily_bar_cache GROUP BY L ORDER BY n DESC"""
show("1a cache trade_date format (string-vs-date bug check)", q, c.execute(q).fetchall())

q = """SELECT COUNT(*) FROM daily_bar_cache
       WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"""
show("1b malformed dates anywhere in cache", q, c.execute(q).fetchall())

# ---------- 2. THS footprint, my own cut, EXCLUDING indices ----------
q = """SELECT COUNT(*) rows, COUNT(DISTINCT symbol) syms,
              MIN(trade_date) mn, MAX(trade_date) mx
       FROM daily_bar_cache WHERE source = ?"""
show("2a my recount of THS footprint in cache", q, c.execute(q, [THS]).fetchall())

# index contamination: join to instruments
q = """SELECT COALESCE(i.exchange,'<no instrument row>') exch,
              COALESCE(i.asset_type,'?') atype,
              COUNT(DISTINCT d.symbol) syms, COUNT(*) rows
       FROM daily_bar_cache d
       LEFT JOIN mh.instruments i
         ON substr(i.symbol, 1, 6) = substr(d.symbol, 1, 6)
        OR i.symbol = d.symbol
       WHERE d.source = ?
       GROUP BY exch, atype ORDER BY rows DESC"""
show("2b are any of the THS symbols indices, not stocks?", q, c.execute(q, [THS]).fetchall())

# raw symbol shapes
q = """SELECT substr(symbol,1,3) pfx, COUNT(DISTINCT symbol) syms, COUNT(*) rows
       FROM daily_bar_cache WHERE source=? GROUP BY pfx ORDER BY syms DESC LIMIT 25"""
show("2c THS symbol prefixes (index codes would show as 000/399/899 idx)", q,
     c.execute(q, [THS]).fetchall())

# ---------- 3. THE CORE TEST: does any symbol EVER exceed 500 sessions? ----------
q = """SELECT MIN(n), MAX(n), AVG(n), COUNT(*) FROM (
         SELECT symbol, COUNT(DISTINCT trade_date) n
         FROM daily_bar_cache WHERE source=? GROUP BY symbol)"""
show("3a per-symbol THS session count: min/max/avg/#symbols", q, c.execute(q, [THS]).fetchall())

q = """SELECT CASE WHEN n>500 THEN 'OVER 500 (would refute the cap)'
                   WHEN n=500 THEN 'exactly 500'
                   WHEN n>=400 THEN '400-499'
                   WHEN n>=100 THEN '100-399'
                   WHEN n>=10  THEN '10-99'
                   ELSE '1-9' END bucket,
              COUNT(*) symbols, SUM(n) rows
       FROM (SELECT symbol, COUNT(DISTINCT trade_date) n
             FROM daily_bar_cache WHERE source=? GROUP BY symbol)
       GROUP BY bucket ORDER BY symbols DESC"""
show("3b distribution of per-symbol THS depth vs the 500 cap", q, c.execute(q, [THS]).fetchall())

# same test in the research store, independently
q = """SELECT MIN(n), MAX(n), AVG(n), COUNT(*) FROM (
         SELECT symbol, COUNT(DISTINCT trade_date) n
         FROM mh.daily_bars WHERE provider=? GROUP BY symbol)"""
show("3c per-symbol THS depth in market_history.daily_bars", q, c.execute(q, [THS]).fetchall())

# ---------- 4. MECHANISM: does 500 trading days back from the THS max land on the THS min? ----------
cal = [r[0] for r in c.execute(
    """SELECT trade_date FROM daily_bar_cache
       GROUP BY trade_date HAVING COUNT(DISTINCT symbol) >= 200
       ORDER BY trade_date""").fetchall()]
print("\n" + "=" * 78)
print("[4 trading calendar built from the cache itself]")
print("SQL: SELECT trade_date FROM daily_bar_cache GROUP BY trade_date "
      "HAVING COUNT(DISTINCT symbol)>=200 ORDER BY trade_date")
print("    sessions total:", len(cal), " first:", cal[0], " last:", cal[-1])

ths_mn, ths_mx = c.execute(
    "SELECT MIN(trade_date), MAX(trade_date) FROM daily_bar_cache WHERE source=?",
    [THS]).fetchone()
i_mx = bisect.bisect_right(cal, ths_mx) - 1
i_mn = bisect.bisect_left(cal, ths_mn)
print("    THS min/max in cache:", ths_mn, ths_mx)
print("    sessions inclusive between THS min and THS max:", i_mx - i_mn + 1,
      " <-- compare to the hard cap 500")
if i_mx - 499 >= 0:
    print("    calendar date exactly 500 sessions back from", ths_mx, "=", cal[i_mx - 499])

# window boundaries in session terms
i_w0 = bisect.bisect_left(cal, W0)
print("    sessions in the research window %s..%s: %d" % (W0, W1, i_mx - i_w0 + 1))
print("    => a tail-500 fetch on %s reaches back only to %s; window start is %s"
      % (ths_mx, cal[max(0, i_mx - 499)], W0))

# ---------- 5. Was the floor set once and never moved? (accumulation direction) ----------
q = """SELECT MIN(date(created_at)) first_created, MAX(date(created_at)) last_created,
              MIN(date(updated_at)), MAX(date(updated_at)), COUNT(*)
       FROM daily_bar_cache WHERE source=?"""
show("5a THS ingest timestamps", q, c.execute(q, [THS]).fetchall())

q = """SELECT date(created_at) d, COUNT(*) rows, COUNT(DISTINCT symbol) syms,
              MIN(trade_date) oldest_bar_written, MAX(trade_date) newest_bar_written
       FROM daily_bar_cache WHERE source=? GROUP BY d ORDER BY d"""
show("5b per ingest-day: did any later run ever write an OLDER bar?", q,
     c.execute(q, [THS]).fetchall())

# ---------- 6. Any THS row at all before 2024-07-30, in either DB? ----------
q = "SELECT COUNT(*) FROM daily_bar_cache WHERE source=? AND trade_date < '2024-07-30'"
show("6a cache THS rows before 2024-07-30", q, c.execute(q, [THS]).fetchall())
q = "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM mh.daily_bars WHERE provider=?"
show("6b research-store THS span (their AFFECTED line says 'none earlier than 2024-07-30')", q,
     c.execute(q, [THS]).fetchall())
q = """SELECT COUNT(*) FROM mh.daily_bars WHERE provider=? AND trade_date < '2024-07-30'"""
show("6c research-store THS rows before 2024-07-30", q, c.execute(q, [THS]).fetchall())

# ---------- 7. Is the 341-symbol research set a subset of the 613? (cross-DB conflation) ----------
q = """SELECT
   (SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE source=?) cache_syms,
   (SELECT COUNT(DISTINCT symbol) FROM mh.daily_bars WHERE provider=?) res_syms,
   (SELECT COUNT(*) FROM (SELECT DISTINCT substr(symbol,1,6) s FROM mh.daily_bars WHERE provider=?
      INTERSECT SELECT DISTINCT substr(symbol,1,6) FROM daily_bar_cache WHERE source=?)) overlap"""
show("7 do the two DBs describe the same symbols or is this double counting?", q,
     c.execute(q, [THS, THS, THS, THS]).fetchall())
c.close()
