import sqlite3, io, time
CACHE = r"D:/codex-A股交易/trading_local.sqlite3"
HIST  = r"D:/codex-A股交易/market_history.sqlite3"
OUT   = r"D:/codex-A股交易/claude methods/_m1_evidence/lineage_reconcile3_output.txt"
buf = io.StringIO()
def P(*a):
    s=" ".join(str(x) for x in a); buf.write(s+"\n")
    print(s.encode("ascii","replace").decode("ascii"))
conn = sqlite3.connect(f"file:{HIST}?mode=ro", uri=True)
conn.execute("PRAGMA query_only=ON"); conn.row_factory = sqlite3.Row
conn.execute(f"ATTACH DATABASE 'file:{CACHE}?mode=ro' AS cache")
def q(t, sql, params=(), lim=40):
    st=time.time(); rows=conn.execute(sql,params).fetchall()
    P("\n### "+t); P("SQL: "+" ".join(sql.split()))
    for r in rows[:lim]: P("   ", dict(r))
    if len(rows)>lim: P("    ... (%d rows total)"%len(rows))
    P("    [%.1fs]"%(time.time()-st)); return rows

q("M25 hist daily_bars symbols split by instruments.exchange/asset_type", """
SELECT COALESCE(i.exchange,'<no instrument row>') AS exchange,
       COALESCE(i.asset_type,'<no instrument row>') AS asset_type,
       COUNT(DISTINCT b.symbol) AS symbols, COUNT(*) AS rows
FROM main.daily_bars b LEFT JOIN main.instruments i ON i.symbol=b.symbol
GROUP BY 1,2 ORDER BY symbols DESC""")

q("M26 cache daily_bar_cache symbols split by instruments.exchange/asset_type", """
SELECT COALESCE(i.exchange,'<no instrument row>') AS exchange,
       COALESCE(i.asset_type,'<no instrument row>') AS asset_type,
       COUNT(DISTINCT c.symbol) AS symbols, COUNT(*) AS rows
FROM cache.daily_bar_cache c LEFT JOIN main.instruments i ON i.symbol=c.symbol
WHERE c.trade_date!='ERROR'
GROUP BY 1,2 ORDER BY symbols DESC""")

q("M27 instruments table: exchange/asset_type/status breakdown", """
SELECT exchange, asset_type, status, COUNT(*) AS n FROM main.instruments GROUP BY 1,2,3 ORDER BY n DESC""")

q("M28 instruments with a delist_date (delisting evidence available at all?)", """
SELECT COUNT(*) AS instruments_total,
       SUM(CASE WHEN delist_date IS NOT NULL AND delist_date!='' THEN 1 ELSE 0 END) AS with_delist_date,
       SUM(CASE WHEN list_date IS NOT NULL AND list_date!='' THEN 1 ELSE 0 END) AS with_list_date,
       SUM(CASE WHEN status!='active' THEN 1 ELSE 0 END) AS non_active
FROM main.instruments""")

q("M29 point-in-time: available_at vs trade_date lag distribution (hist)", """
SELECT CASE
   WHEN available_at IS NULL THEN 'z:null'
   WHEN julianday(substr(available_at,1,10)) - julianday(trade_date) < 0 THEN 'a:negative(before bar)'
   WHEN julianday(substr(available_at,1,10)) - julianday(trade_date) <= 1 THEN 'b:0-1 day'
   WHEN julianday(substr(available_at,1,10)) - julianday(trade_date) <= 7 THEN 'c:2-7 days'
   WHEN julianday(substr(available_at,1,10)) - julianday(trade_date) <= 30 THEN 'd:8-30 days'
   WHEN julianday(substr(available_at,1,10)) - julianday(trade_date) <= 180 THEN 'e:31-180 days'
   ELSE 'f:>180 days' END AS lag_bucket,
   COUNT(*) AS rows, MIN(trade_date) AS min_td, MAX(trade_date) AS max_td
FROM main.daily_bars GROUP BY 1 ORDER BY 1""")

q("M30 hist available_at distinct dates (how many distinct ingest vintages)", """
SELECT substr(available_at,1,10) AS available_date, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS symbols
FROM main.daily_bars GROUP BY 1 ORDER BY rows DESC LIMIT 25""", lim=25)

q("M31 ingest_runs summary", """
SELECT status, adjustment_mode, provider, COUNT(*) AS runs, MIN(requested_at) AS first_run, MAX(requested_at) AS last_run,
       SUM(inserted_row_count) AS inserted, SUM(updated_row_count) AS updated, SUM(rejected_row_count) AS rejected
FROM main.ingest_runs GROUP BY 1,2,3 ORDER BY runs DESC""")

q("M32 universe_snapshots (survivorship evidence)", """
SELECT id, universe_name, snapshot_date, provider, member_count, fetched_at FROM main.universe_snapshots ORDER BY snapshot_date""")

q("M33 cache: OHLC nullability / invalid rows (no CHECK constraints)", """
SELECT SUM(CASE WHEN open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL THEN 1 ELSE 0 END) AS null_ohlc_rows,
       SUM(CASE WHEN high < low THEN 1 ELSE 0 END) AS high_lt_low,
       SUM(CASE WHEN high < open OR high < close THEN 1 ELSE 0 END) AS high_lt_open_or_close,
       SUM(CASE WHEN low > open OR low > close THEN 1 ELSE 0 END) AS low_gt_open_or_close,
       SUM(CASE WHEN close <= 0 THEN 1 ELSE 0 END) AS nonpositive_close,
       SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) AS null_amount,
       SUM(CASE WHEN volume IS NULL THEN 1 ELSE 0 END) AS null_volume,
       SUM(CASE WHEN length(trade_date)!=10 THEN 1 ELSE 0 END) AS bad_date_len
FROM cache.daily_bar_cache""")

q("M34 hist: same nullability checks (constraints should make these zero)", """
SELECT SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) AS null_amount,
       SUM(CASE WHEN volume IS NULL THEN 1 ELSE 0 END) AS null_volume,
       COUNT(*) AS rows
FROM main.daily_bars""")

q("M35 backtest reachable universe: cache rows the engine would actually load (quality_status='ready', NO adjustment_mode filter)", """
SELECT COUNT(*) AS rows_engine_sees, COUNT(DISTINCT symbol) AS symbols_engine_sees,
       SUM(CASE WHEN adjustment_mode!='qfq' THEN 1 ELSE 0 END) AS non_qfq_rows_engine_sees,
       SUM(CASE WHEN open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL THEN 1 ELSE 0 END) AS null_price_rows
FROM cache.daily_bar_cache WHERE quality_status='ready'""")

q("M36 the non-qfq cache rows the backtest silently mixes in", """
SELECT symbol, adjustment_mode, quality_status, source, COUNT(*) AS rows, MIN(trade_date) AS first_bar, MAX(trade_date) AS last_bar
FROM cache.daily_bar_cache WHERE adjustment_mode!='qfq' GROUP BY 1,2,3,4 ORDER BY rows DESC LIMIT 30""", lim=30)

q("M37 trading-session coverage in window: distinct trade_dates per calendar month (cache)", """
SELECT substr(trade_date,1,7) AS ym, COUNT(DISTINCT trade_date) AS sessions, COUNT(DISTINCT symbol) AS symbols, COUNT(*) AS rows
FROM cache.daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'
GROUP BY 1 ORDER BY 1""", lim=45)

conn.close()
open(OUT,"w",encoding="utf-8").write(buf.getvalue()); print("\nWROTE",OUT)
