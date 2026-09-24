import sqlite3, os
ROOT = r"D:\codex-A股交易"
TL = sqlite3.connect(f"file:{os.path.join(ROOT,'trading_local.sqlite3')}?mode=ro", uri=True)
MH = sqlite3.connect(f"file:{os.path.join(ROOT,'market_history.sqlite3')}?mode=ro", uri=True)
TL.row_factory = sqlite3.Row; MH.row_factory = sqlite3.Row

def q(c, tag, sql, params=()):
    print(f"--- {tag}")
    print("SQL: " + " ".join(sql.split()))
    rows = [dict(r) for r in c.execute(sql, params).fetchall()]
    for r in rows[:25]:
        print("     ", r)
    if len(rows) > 25:
        print(f"      ... {len(rows)} rows")
    print()
    return rows

print("=" * 78)
print("R9. The 16 symbols with 501 rows - does the cap leak, or is it accumulation?")
print("=" * 78)
q(TL, "501-row symbols: span, and created_at spread (accumulation leaves 2 ingest days)",
  """WITH per AS (SELECT symbol, COUNT(*) n FROM daily_bar_cache
                  WHERE source='tonghuasun.local.quotes.candle' GROUP BY symbol
                 HAVING n = 501)
     SELECT b.symbol, COUNT(*) n, MIN(b.trade_date) mn, MAX(b.trade_date) mx,
            COUNT(DISTINCT substr(b.created_at,1,10)) distinct_created_days,
            MIN(substr(b.created_at,1,10)) first_created,
            MAX(substr(b.created_at,1,10)) last_created
       FROM daily_bar_cache b JOIN per USING (symbol)
      WHERE b.source='tonghuasun.local.quotes.candle'
      GROUP BY b.symbol LIMIT 8""")
q(TL, "501-row symbol BJ920058: rows created on each ingest day (2 calls => 500 + 1 new)",
  """SELECT substr(created_at,1,10) created_day, COUNT(*) rows,
            MIN(trade_date) mn, MAX(trade_date) mx
       FROM daily_bar_cache
      WHERE symbol='BJ920058' AND source='tonghuasun.local.quotes.candle'
      GROUP BY created_day ORDER BY created_day""")

print("=" * 78)
print("R10. Does ANY table on either DB hold a real session date before 2024-04-09?")
print("     (If not, the 146-sessions head-gap denominator is an ESTIMATE, not a count.)")
print("=" * 78)
for name, con in (("trading_local", TL), ("market_history", MH)):
    tabs = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    hits = []
    for t in tabs:
        cols = [r[1] for r in con.execute(f'PRAGMA table_info("{t}")').fetchall()]
        dcols = [c for c in cols if any(k in c.lower() for k in
                 ("trade_date", "session_date", "as_of", "date"))]
        for c in dcols:
            try:
                sql = (f'SELECT MIN("{c}") mn, COUNT(*) n FROM "{t}" '
                       f'WHERE length("{c}")=10 AND "{c}" >= \'2023-09-04\' '
                       f'AND "{c}" < \'2024-04-09\'')
                r = con.execute(sql).fetchone()
                if r and r["n"]:
                    hits.append((t, c, r["mn"], r["n"]))
            except sqlite3.Error:
                pass
    print(f"  {name}: tables scanned={len(tabs)}")
    if hits:
        for h in sorted(hits, key=lambda x: -x[3])[:20]:
            print(f"     table={h[0]:40s} col={h[1]:22s} min={h[2]} rows={h[3]}")
    else:
        print("     NO row on any date column falls in 2023-09-04..2024-04-08")
    print()

print("=" * 78)
print("R11. Head-gap symbol denominator: where does 5,167 come from, and is it right?")
print("=" * 78)
q(TL, "distinct symbols with any bar in the window (cache)",
  """SELECT COUNT(DISTINCT symbol) syms FROM daily_bar_cache
      WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04' AND length(trade_date)=10""")
q(MH, "instruments listed on/before the head-gap end and not delisted before it",
  """SELECT COUNT(*) tradable_through_head_gap FROM instruments
      WHERE exchange IN ('SH','SZ','BJ')
        AND list_date IS NOT NULL AND list_date <= '2024-04-08'
        AND (delist_date IS NULL OR delist_date >= '2023-09-04')""")

print("=" * 78)
print("R12. Throughput: is tonghuasun really 'the slowest source by design'?")
print("     Compare the tonghuasun min_request_interval floor (1.0s = 1.0 sym/s ceiling)")
print("     against the OTHER sources' measured cache write rates on the same DB.")
print("=" * 78)
q(TL, "symbols ingested per created-minute, by source (observed throughput)",
  """WITH m AS (SELECT source, substr(created_at,1,16) minute,
                     COUNT(DISTINCT symbol) syms
                FROM daily_bar_cache WHERE created_at IS NOT NULL
               GROUP BY source, minute)
     SELECT source, COUNT(*) minutes, ROUND(AVG(syms)/60.0,3) avg_symbols_per_sec,
            ROUND(MAX(syms)/60.0,3) peak_symbols_per_sec
       FROM m GROUP BY source ORDER BY avg_symbols_per_sec DESC""")
