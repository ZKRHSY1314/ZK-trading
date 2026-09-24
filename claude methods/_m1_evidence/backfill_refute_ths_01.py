import sqlite3, os
ROOT = r"D:\codex-A股交易"
TL = sqlite3.connect(f"file:{os.path.join(ROOT,'trading_local.sqlite3')}?mode=ro", uri=True)
MH = sqlite3.connect(f"file:{os.path.join(ROOT,'market_history.sqlite3')}?mode=ro", uri=True)
TL.row_factory = sqlite3.Row; MH.row_factory = sqlite3.Row

def q(c, tag, sql, params=()):
    print(f"--- {tag}")
    print("SQL: " + " ".join(sql.split()))
    rows = [dict(r) for r in c.execute(sql, params).fetchall()]
    for r in rows[:30]:
        print("     ", r)
    if len(rows) > 30:
        print(f"      ... {len(rows)} rows")
    print()
    return rows

print("=" * 78)
print("R1. Every source label containing tongh/ths - catch alternate labels")
print("=" * 78)
q(TL, "cache: fuzzy tonghuasun match",
  """SELECT source, COUNT(*) n, COUNT(DISTINCT symbol) syms,
            MIN(trade_date) mn, MAX(trade_date) mx
       FROM daily_bar_cache
      WHERE lower(source) LIKE '%tongh%' OR lower(source) LIKE '%ths%'
      GROUP BY source ORDER BY n DESC""")
q(TL, "cache: FULL source inventory",
  """SELECT COALESCE(source,'<NULL>') source, COUNT(*) n, COUNT(DISTINCT symbol) syms,
            MIN(trade_date) mn, MAX(trade_date) mx
       FROM daily_bar_cache GROUP BY source ORDER BY n DESC""")

print("=" * 78)
print("R2. Footprint recomputed: DISTINCT securities, indices split out")
print("=" * 78)
q(TL, "tonghuasun rows split index vs stock",
  """SELECT CASE
             WHEN substr(symbol,1,2)='SH' AND substr(symbol,3,3)='000' THEN 'index_SH000'
             WHEN substr(symbol,1,2)='SZ' AND substr(symbol,3,3)='399' THEN 'index_SZ399'
             ELSE 'stock_or_other' END AS bucket,
           COUNT(*) rows, COUNT(DISTINCT symbol) securities,
           MIN(trade_date) mn, MAX(trade_date) mx
      FROM daily_bar_cache
     WHERE source = 'tonghuasun.local.quotes.candle'
     GROUP BY bucket""")
q(TL, "tonghuasun totals + malformed-date probe",
  """SELECT COUNT(DISTINCT symbol) AS ths_distinct_symbols,
            COUNT(*) AS ths_rows,
            MIN(trade_date) AS earliest, MAX(trade_date) AS latest,
            MIN(length(trade_date)) AS min_len, MAX(length(trade_date)) AS max_len
       FROM daily_bar_cache WHERE source='tonghuasun.local.quotes.candle'""")

print("=" * 78)
print("R3. STRUCTURAL TEST: per-symbol depth. A 500 cap => max <= 500, spike at 500")
print("=" * 78)
q(TL, "tonghuasun per-symbol depth stats",
  """WITH per AS (SELECT symbol, COUNT(*) n FROM daily_bar_cache
                  WHERE source='tonghuasun.local.quotes.candle' GROUP BY symbol)
     SELECT MAX(n) max_bars, MIN(n) min_bars, ROUND(AVG(n),1) avg_bars,
            SUM(CASE WHEN n=500 THEN 1 ELSE 0 END) symbols_at_exactly_500,
            SUM(CASE WHEN n>500 THEN 1 ELSE 0 END) symbols_over_500,
            COUNT(*) symbols FROM per""")
q(TL, "tonghuasun depth histogram",
  """WITH per AS (SELECT symbol, COUNT(*) n FROM daily_bar_cache
                  WHERE source='tonghuasun.local.quotes.candle' GROUP BY symbol)
     SELECT n bars_per_symbol, COUNT(*) symbols FROM per
     GROUP BY n ORDER BY symbols DESC LIMIT 10""")

print("=" * 78)
print("R4. Is 2024-07-30 ~500 observed sessions before the tonghuasun max?")
print("=" * 78)
q(TL, "observed sessions 2024-07-30 .. 2026-09-04",
  """SELECT COUNT(*) AS observed_sessions
       FROM (SELECT DISTINCT trade_date FROM daily_bar_cache
              WHERE length(trade_date)=10 AND trade_date >= '2024-07-30'
                AND trade_date <= '2026-09-04')""")
q(TL, "deepest tonghuasun symbols and their spans",
  """WITH per AS (SELECT symbol, COUNT(*) n, MIN(trade_date) mn, MAX(trade_date) mx
                    FROM daily_bar_cache WHERE source='tonghuasun.local.quotes.candle'
                   GROUP BY symbol)
     SELECT symbol, n, mn, mx FROM per ORDER BY n DESC LIMIT 5""")

print("=" * 78)
print("R5. DENOMINATOR recomputed independently: the head gap")
print("=" * 78)
q(TL, "cache-wide earliest / latest / session count",
  """SELECT MIN(trade_date) earliest, MAX(trade_date) latest,
            COUNT(DISTINCT trade_date) sessions
       FROM daily_bar_cache WHERE length(trade_date)=10""")
q(TL, "cache rows inside head-gap span 2023-09-04..2024-04-08",
  """SELECT COUNT(*) rows_in_head_gap, COUNT(DISTINCT symbol) syms
       FROM daily_bar_cache
      WHERE trade_date >= '2023-09-04' AND trade_date <= '2024-04-08'
        AND length(trade_date)=10""")
q(MH, "market_history rows inside head-gap span",
  """SELECT COUNT(*) rows_in_head_gap, COUNT(DISTINCT symbol) syms, MIN(trade_date) mn
       FROM daily_bars
      WHERE trade_date >= '2023-09-04' AND trade_date <= '2024-04-08'""")

print("=" * 78)
print("R6. Earliest date a 500-bar request can reach, on the real observed calendar")
print("=" * 78)
sql6 = ("SELECT trade_date FROM (SELECT DISTINCT trade_date FROM daily_bar_cache "
        "WHERE length(trade_date)=10 AND trade_date <= '2026-09-04' "
        "ORDER BY trade_date DESC LIMIT 500) ORDER BY trade_date LIMIT 1")
print("SQL: " + sql6)
row = TL.execute(sql6).fetchone()
reach = row[0] if row else None
print("      500th-most-recent observed session =", reach)
print("      head gap ENDS 2024-04-08 -> reachable by a 500-bar request?",
      (reach <= "2024-04-08") if reach else None)
print()

print("=" * 78)
print("R7. market_history provider footprint - independent formulation")
print("=" * 78)
q(MH, "mh: all providers",
  """SELECT provider, COUNT(*) n, COUNT(DISTINCT symbol) syms,
            MIN(trade_date) mn, MAX(trade_date) mx
       FROM daily_bars GROUP BY provider ORDER BY n DESC""")
q(MH, "mh: tonghuasun rows by adjustment_mode (double counting across modes?)",
  """SELECT adjustment_mode, COUNT(*) n, COUNT(DISTINCT symbol) syms,
            MIN(trade_date) mn, MAX(trade_date) mx
       FROM daily_bars WHERE provider LIKE '%tongh%'
      GROUP BY adjustment_mode""")

print("=" * 78)
print("R8. Is tonghuasun useful for anything OTHER than the head gap?")
print("=" * 78)
q(TL, "per-symbol first bar date buckets",
  """WITH per AS (SELECT symbol, MIN(trade_date) mn FROM daily_bar_cache
                  WHERE length(trade_date)=10 GROUP BY symbol)
     SELECT CASE WHEN mn <= '2024-04-08' THEN 'a_at_or_before_cache_head'
                 WHEN mn <= '2024-07-29' THEN 'b_before_ths_reach'
                 ELSE 'c_inside_ths_reach' END AS bucket,
            COUNT(*) symbols FROM per GROUP BY bucket ORDER BY bucket""")
q(TL, "rows the window holds inside the ths reach",
  """SELECT COUNT(*) rows_inside_ths_reach
       FROM daily_bar_cache
      WHERE trade_date BETWEEN '2024-07-30' AND '2026-09-04' AND length(trade_date)=10""")
