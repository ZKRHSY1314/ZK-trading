import sqlite3

OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"


def ro(p):
    c = sqlite3.connect("file:" + p + "?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


op = ro(OP)
mh = ro(MH)


def show(title, sql, conn=None, params=()):
    conn = conn or op
    print("\n### " + title)
    print("SQL: " + " ".join(sql.split()))
    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception as e:
        print("  ERROR:", e)
        return []
    for r in rows[:60]:
        print("   ", dict(r))
    if len(rows) > 60:
        print("    ... %d rows total" % len(rows))
    return rows


print("=" * 100)
print("A. historical_backtest_runs - INDEPENDENT enumeration (not their GROUP BY)")
print("=" * 100)

show("A1 count + NULL + distinct-by-hex (catches whitespace/case/NULL)",
     """SELECT COUNT(*) AS n_runs,
               SUM(CASE WHEN data_source IS NULL THEN 1 ELSE 0 END) AS null_ds,
               COUNT(DISTINCT data_source) AS distinct_ds,
               COUNT(DISTINCT hex(data_source)) AS distinct_hex,
               MIN(id) AS min_id, MAX(id) AS max_id
        FROM historical_backtest_runs""")

show("A2 every distinct data_source verbatim with hex/typeof/length",
     """SELECT data_source, hex(data_source) AS hx, typeof(data_source) AS ty,
               length(data_source) AS len, COUNT(*) AS runs
        FROM historical_backtest_runs
        GROUP BY hex(data_source), typeof(data_source)""")

show("A3 runs whose data_source is NOT exactly 'daily_bar_cache'",
     """SELECT id, data_source, status, start_date, end_date, completed_at
        FROM historical_backtest_runs
        WHERE data_source IS NULL OR data_source <> 'daily_bar_cache'""")

show("A4 did these runs move money at all?",
     """SELECT COUNT(*) AS runs,
               SUM(CASE WHEN final_cash <> initial_cash THEN 1 ELSE 0 END) AS runs_pnl_changed,
               MIN(final_cash - initial_cash) AS min_pnl,
               MAX(final_cash - initial_cash) AS max_pnl
        FROM historical_backtest_runs""")

show("A5 per-run detail, row level",
     """SELECT r.id, r.status, r.start_date, r.end_date, r.benchmark_symbol,
               ROUND(r.initial_cash,2) AS init, ROUND(r.final_cash,2) AS fin,
               (SELECT COUNT(*) FROM historical_backtest_daily_equity e WHERE e.run_id=r.id) AS eq_rows,
               (SELECT COUNT(*) FROM historical_backtest_trades t WHERE t.run_id=r.id) AS trade_rows
        FROM historical_backtest_runs r ORDER BY r.id""")

show("A6 schema of the table (is data_source defaulted/constrained?)",
     """SELECT sql FROM sqlite_master WHERE type='table' AND name='historical_backtest_runs'""")

print("\n" + "=" * 100)
print("B. What the engine predicate ACTUALLY admits (quality_status='ready', NO date filter)")
print("=" * 100)

show("B1 quality_status census verbatim + hex",
     """SELECT quality_status, hex(quality_status) AS hx, typeof(quality_status) AS ty,
               COUNT(*) AS rows_, COUNT(DISTINCT symbol) AS syms
        FROM daily_bar_cache
        GROUP BY hex(quality_status), typeof(quality_status)
        ORDER BY rows_ DESC""")

show("B2 EXACT engine predicate: rows and DISTINCT symbols admitted",
     """SELECT COUNT(*) AS rows_admitted, COUNT(DISTINCT symbol) AS symbols_admitted
        FROM daily_bar_cache WHERE quality_status = 'ready'""")

show("B3 whole table for contrast",
     """SELECT COUNT(*) AS rows_total, COUNT(DISTINCT symbol) AS symbols_total
        FROM daily_bar_cache""")

show("B4 engine ALSO drops NULL-OHLC rows in pandas; what survives that too",
     """SELECT COUNT(*) AS rows_after_ohlc_dropna, COUNT(DISTINCT symbol) AS syms_after_ohlc_dropna
        FROM daily_bar_cache
        WHERE quality_status='ready'
          AND open IS NOT NULL AND high IS NOT NULL
          AND low IS NOT NULL AND close IS NOT NULL""")

print("\n" + "=" * 100)
print("C. Indices vs stocks inside the admitted set")
print("=" * 100)

show("C1 admitted symbols split by code shape",
     """SELECT CASE WHEN upper(symbol) LIKE 'SH000%' OR upper(symbol) LIKE 'SZ399%'
                     OR upper(symbol) LIKE 'BJ899%' THEN 'index_like' ELSE 'other' END AS kind,
               COUNT(DISTINCT symbol) AS syms, COUNT(*) AS rows_
        FROM daily_bar_cache WHERE quality_status='ready' GROUP BY kind""")

idxset = {r["symbol"] for r in mh.execute(
    "SELECT symbol FROM instruments WHERE exchange='INDEX' OR asset_type='index'")}
print("\n  market_history.instruments INDEX rows: %d" % len(idxset))
print("  SQL: SELECT symbol FROM instruments WHERE exchange='INDEX' OR asset_type='index'")

adm = {r["symbol"] for r in op.execute(
    "SELECT DISTINCT symbol FROM daily_bar_cache WHERE quality_status='ready'")}
admU = {s.upper() for s in adm}
idxU = {s.upper() for s in idxset}
print("  admitted distinct symbols (raw): %d" % len(adm))
print("  admitted distinct symbols (case-collapsed): %d  -> case-dup effect %d"
      % (len(admU), len(adm) - len(admU)))
print("  admitted symbols catalogued as INDEX: %d" % len(admU & idxU))
print("  admitted NON-index symbols: %d" % len(admU - idxU))

print("\n" + "=" * 100)
print("D. Research window scoping")
print("=" * 100)

show("D1 admitted rows/symbols INSIDE 2023-09-04..2026-09-04",
     """SELECT COUNT(*) AS rows_, COUNT(DISTINCT symbol) AS syms,
               MIN(trade_date) AS mn, MAX(trade_date) AS mx
        FROM daily_bar_cache
        WHERE quality_status='ready'
          AND trade_date >= '2023-09-04' AND trade_date <= '2026-09-04'""")

show("D2 admitted rows OUTSIDE the window (engine has NO date filter)",
     """SELECT COUNT(*) AS rows_outside, COUNT(DISTINCT symbol) AS syms_outside
        FROM daily_bar_cache
        WHERE quality_status='ready'
          AND (trade_date < '2023-09-04' OR trade_date > '2026-09-04')""")

show("D3 malformed trade_date that would break string comparison",
     """SELECT COUNT(*) AS bad_len_rows FROM daily_bar_cache WHERE length(trade_date) <> 10""")

print("\n" + "=" * 100)
print("E. Benchmark path also reads the cache")
print("=" * 100)

show("E1 default benchmark SH000300 under the benchmark predicate",
     """SELECT COUNT(*) AS rows_, MIN(trade_date) AS mn, MAX(trade_date) AS mx
        FROM daily_bar_cache
        WHERE upper(symbol)='SH000300' AND quality_status='ready'""")

print("\n" + "=" * 100)
print("F. Direction of the two stores: is market_history upstream or downstream?")
print("=" * 100)

show("F1 market_history.daily_bars provider census",
     """SELECT provider, adjustment_mode, COUNT(*) AS rows_, COUNT(DISTINCT symbol) AS syms
        FROM daily_bars GROUP BY provider, adjustment_mode ORDER BY rows_ DESC""", conn=mh)

show("F2 market_history.ingest_runs source labels",
     """SELECT source, COUNT(*) AS n FROM ingest_runs GROUP BY source""", conn=mh)

mhs = {r["symbol"].upper() for r in mh.execute("SELECT DISTINCT symbol FROM daily_bars")}
print("\n  market_history.daily_bars distinct symbols: %d" % len(mhs))
print("  in market_history but NOT admitted by engine predicate: %d" % len(mhs - admU))
print("  admitted by engine but NOT in market_history: %d" % len(admU - mhs))
