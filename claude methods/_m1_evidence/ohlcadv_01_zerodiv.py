import sqlite3, json
TL = r"file:D:/codex-A股交易/trading_local.sqlite3?mode=ro"
MH = r"file:D:/codex-A股交易/market_history.sqlite3?mode=ro"
tl = sqlite3.connect(TL, uri=True); tl.row_factory = sqlite3.Row
mh = sqlite3.connect(MH, uri=True); mh.row_factory = sqlite3.Row

def q(c, sql, p=()):
    return [dict(r) for r in c.execute(sql, p).fetchall()]

def show(label, sql, c=tl, p=(), limit=30):
    print("\n" + "="*100)
    print("### " + label)
    print("SQL: " + " ".join(sql.split()))
    rows = q(c, sql, p)
    print("ROWS: %d" % len(rows))
    for r in rows[:limit]:
        print("   ", json.dumps(r, ensure_ascii=False, default=str))
    if len(rows) > limit: print("    ... (%d more)" % (len(rows)-limit))
    return rows

# ---------- 0. DENOMINATORS ----------
show("D0 total rows / ready rows / distinct symbols in daily_bar_cache",
 "SELECT COUNT(*) AS total_rows, SUM(CASE WHEN quality_status='ready' THEN 1 ELSE 0 END) AS ready_rows, COUNT(DISTINCT symbol) AS distinct_symbols FROM daily_bar_cache")

show("D1 quality_status distribution",
 "SELECT quality_status, COUNT(*) n FROM daily_bar_cache GROUP BY quality_status ORDER BY n DESC")

# ---------- 1. THE ACTUAL FAILURE PREDICATE: open that makes buy_price round to 0 ----------
# engine.py:231-233  reference_price=float(bar['open']); buy_price=round(rp*(1+slip),4); int(alloc/buy_price)
# ZeroDivisionError iff buy_price == 0.0  <=>  |open*(1+slip)| < 0.00005
show("A1 rows where OPEN is zero/negative/sub-tick (the true ZeroDivisionError predicate), quality_status='ready'",
 """SELECT COUNT(*) AS n_rows, COUNT(DISTINCT symbol) AS n_symbols, COUNT(DISTINCT trade_date) AS n_dates,
           MIN(trade_date) AS first_date, MAX(trade_date) AS last_date
    FROM daily_bar_cache
    WHERE quality_status='ready' AND open IS NOT NULL AND CAST(open AS REAL) < 0.00005""")

show("A2 same, ALL quality_status values (is 'ready' the only bucket carrying it?)",
 """SELECT quality_status, COUNT(*) n_rows, COUNT(DISTINCT symbol) n_symbols
    FROM daily_bar_cache WHERE open IS NOT NULL AND CAST(open AS REAL) < 0.00005
    GROUP BY quality_status""")

show("A3 FULL LIST of every open<0.00005 'ready' row",
 """SELECT symbol, trade_date, open, high, low, close, volume, amount, source, quality_status,
           adjustment_mode, volume_unit, created_at, updated_at
    FROM daily_bar_cache WHERE quality_status='ready' AND open IS NOT NULL AND CAST(open AS REAL) < 0.00005
    ORDER BY symbol, trade_date""", limit=60)

# ---------- 2. Does the OHLC-ordering query (theirs) actually capture the same set? ----------
show("B1 rows violating market_history OHLC ORDERING checks (their predicate), ALL quality_status",
 """SELECT quality_status, COUNT(*) n, COUNT(DISTINCT symbol) syms FROM daily_bar_cache
    WHERE open IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL AND close IS NOT NULL
      AND (high<low OR high<open OR high<close OR low>open OR low>close)
    GROUP BY quality_status""")

show("B2 set difference: rows with open<=0 that do NOT violate any OHLC ordering check",
 """SELECT symbol, trade_date, open, high, low, close, volume, amount, quality_status
    FROM daily_bar_cache
    WHERE quality_status='ready' AND open IS NOT NULL AND CAST(open AS REAL) <= 0.0
      AND NOT (high<low OR high<open OR high<close OR low>open OR low>close)
    ORDER BY trade_date""", limit=60)

# ---------- 3. Other zero-price fields that divide ----------
show("C1 zero/negative CLOSE (feeds pct_change / previous_close divisions, _snapshot line ~493)",
 """SELECT COUNT(*) n_rows, COUNT(DISTINCT symbol) n_syms, COUNT(DISTINCT trade_date) n_dates
    FROM daily_bar_cache WHERE quality_status='ready' AND close IS NOT NULL AND CAST(close AS REAL) <= 0.0""")
show("C2 zero/negative HIGH or LOW among ready rows",
 """SELECT SUM(CASE WHEN CAST(high AS REAL)<=0 THEN 1 ELSE 0 END) zero_high,
           SUM(CASE WHEN CAST(low AS REAL)<=0 THEN 1 ELSE 0 END) zero_low,
           SUM(CASE WHEN CAST(open AS REAL)<=0 THEN 1 ELSE 0 END) zero_open,
           SUM(CASE WHEN CAST(close AS REAL)<=0 THEN 1 ELSE 0 END) zero_close
    FROM daily_bar_cache WHERE quality_status='ready'""")
show("C3 NULL price fields among ready rows (dropna DOES remove these -> not a crash)",
 """SELECT SUM(open IS NULL) null_open, SUM(high IS NULL) null_high, SUM(low IS NULL) null_low,
           SUM(close IS NULL) null_close, COUNT(*) ready_total
    FROM daily_bar_cache WHERE quality_status='ready'""")

# ---------- 4. Are the 3 symbols stocks or indices? ----------
show("E1 instrument metadata for the 3 named symbols (market_history.instruments)",
 """SELECT symbol, name, exchange, asset_type, board, status, list_date, delist_date
    FROM instruments WHERE symbol IN ('SH688089','SH688143','SH688173')""", c=mh)

# ---------- 5. Cross-db: are those rows really absent from market_history? ----------
show("F1 market_history.daily_bars for the 3 symbols on 2024-11-06 (any adjustment_mode)",
 """SELECT symbol, trade_date, adjustment_mode, open, high, low, close, volume, amount, provider, quality_status
    FROM daily_bars WHERE trade_date='2024-11-06' AND symbol IN ('SH688089','SH688143','SH688173')""", c=mh)

show("F2 market_history.daily_bars neighbouring dates for SH688089 (did the bar just move?)",
 """SELECT symbol, trade_date, adjustment_mode, open, high, low, close, volume
    FROM daily_bars WHERE symbol='SH688089' AND trade_date BETWEEN '2024-11-04' AND '2024-11-08'
    ORDER BY trade_date, adjustment_mode""", c=mh)

show("F3 how many distinct symbols have a 2024-11-06 bar in market_history",
 """SELECT COUNT(DISTINCT symbol) n_symbols, COUNT(*) n_rows FROM daily_bars WHERE trade_date='2024-11-06'""", c=mh)

# ---------- 6. Is 2024-11-06 a normal trading day in the cache? ----------
show("G1 daily_bar_cache row counts around 2024-11-06",
 """SELECT trade_date, COUNT(*) n_rows, COUNT(DISTINCT symbol) n_syms,
           SUM(CASE WHEN CAST(open AS REAL)<=0 THEN 1 ELSE 0 END) zero_open_rows
    FROM daily_bar_cache WHERE trade_date BETWEEN '2024-11-01' AND '2024-11-12'
    GROUP BY trade_date ORDER BY trade_date""")

# ---------- 7. Neighbouring cache bars for the 3 symbols (context: IPO? suspension?) ----------
show("H1 daily_bar_cache bars for the 3 symbols 2024-10-28..2024-11-15",
 """SELECT symbol, trade_date, open, high, low, close, volume, amount, source, adjustment_mode, quality_status
    FROM daily_bar_cache WHERE symbol IN ('SH688089','SH688143','SH688173')
      AND trade_date BETWEEN '2024-10-28' AND '2024-11-15' ORDER BY symbol, trade_date""", limit=60)

show("H2 total cache bars per the 3 symbols + earliest/latest",
 """SELECT symbol, COUNT(*) n_bars, MIN(trade_date) first_bar, MAX(trade_date) last_bar,
           SUM(CASE WHEN CAST(open AS REAL)<=0 THEN 1 ELSE 0 END) zero_open_bars
    FROM daily_bar_cache WHERE symbol IN ('SH688089','SH688143','SH688173') GROUP BY symbol""")

tl.close(); mh.close()
