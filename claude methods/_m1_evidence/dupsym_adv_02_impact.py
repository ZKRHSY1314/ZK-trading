import sqlite3
OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True); c.row_factory = sqlite3.Row; return c
op = ro(OP); mh = ro(MH)
def q(c, sql, p=()):
    try: return [dict(r) for r in c.execute(sql, p).fetchall()]
    except Exception as e: return [{"ERR": str(e)}]
def show(t, rows, n=30):
    print("="*90); print(t)
    if not rows: print("    <empty>")
    for r in rows[:n]: print("   ", r)
    if len(rows) > n: print(f"    ... {len(rows)-n} more")

# ---- F. IS SH000001 AN INDEX, AND IS THE 'AMBIGUITY' REAL IN DATA? ----
show("F1 instruments rows for the 5 spellings (market_history)", q(mh, """
SELECT symbol, exchange, asset_type, board, status, list_date, delist_date
FROM instruments WHERE symbol IN ('SH000001','SZ000001','SH600519','SZ300750','BJ920099','000001','600519','300750','920099')
ORDER BY symbol"""))

show("F2 price-scale separation: bare 000001 vs each candidate (does the DATA disambiguate?)", q(op, """
SELECT p.symbol AS candidate,
       COUNT(*) AS shared_dates,
       ROUND(MIN(b.close),3) AS bare_min, ROUND(MAX(b.close),3) AS bare_max,
       ROUND(MIN(p.close),3) AS cand_min, ROUND(MAX(p.close),3) AS cand_max,
       ROUND(MAX(ABS(b.close-p.close)/NULLIF(p.close,0))*100,4) AS max_pct_diff
FROM daily_bar_cache b JOIN daily_bar_cache p ON p.trade_date=b.trade_date
WHERE b.symbol='000001' AND p.symbol IN ('SZ000001','SH000001')
GROUP BY p.symbol"""))

show("F3 how many of the 5 spellings actually carry a DUPLICATE bare twin (security-level count)", q(op, """
SELECT p.symbol AS prefixed,
       CASE WHEN EXISTS (SELECT 1 FROM daily_bar_cache b WHERE b.symbol=substr(p.symbol,3) AND LENGTH(b.symbol)=6) THEN 'code has a bare spelling' ELSE 'no bare spelling' END AS bare_exists,
       ROUND(MAX(ABS(p.close - (SELECT b.close FROM daily_bar_cache b WHERE b.symbol=substr(p.symbol,3) AND b.trade_date=p.trade_date))),4) AS max_diff_to_bare
FROM daily_bar_cache p WHERE p.symbol IN ('SH000001','SZ000001','SH600519','SZ300750','BJ920099')
GROUP BY p.symbol"""))

# ---- G. source breakdown of the bare rows ----
show("G1 bare rows by symbol x source x volume_unit", q(op, """
SELECT symbol, source, volume_unit, COUNT(*) n, MIN(trade_date) d0, MAX(trade_date) d1
FROM daily_bar_cache WHERE LENGTH(symbol)=6 GROUP BY symbol, source, volume_unit ORDER BY symbol, source"""))

show("G2 prefixed partners: source mix over the SAME span 2026-03-12..2026-09-03", q(op, """
SELECT symbol, source, COUNT(*) n FROM daily_bar_cache
WHERE symbol IN ('SZ000001','SH000001','SH600519','SZ300750','BJ920099')
  AND trade_date BETWEEN '2026-03-12' AND '2026-09-03'
GROUP BY symbol, source ORDER BY symbol, source"""))

# ---- H. DOES ANYTHING ACTUALLY CONSUME THEM? ----
show("H1 backtest run date ranges (do any cover the shadow span?)", q(op, """
SELECT COUNT(*) AS n_runs, MIN(start_date) AS min_start, MAX(end_date) AS max_end,
       SUM(CASE WHEN end_date >= '2026-03-12' THEN 1 ELSE 0 END) AS runs_touching_shadow_span
FROM historical_backtest_runs"""))
show("H1b backtest runs listing", q(op, "SELECT id, start_date, end_date, status, created_at FROM historical_backtest_runs ORDER BY id DESC LIMIT 15"))

for tbl, col in [("forecast_decisions","symbol"),("forecast_outcomes","symbol"),("universe_members","symbol")]:
    db = mh if tbl=="universe_members" else op
    show(f"H2 {tbl}: any bare 6-char symbols?", q(db, f"""
SELECT LENGTH({col}) AS len, COUNT(*) n, COUNT(DISTINCT {col}) n_sym, MIN({col}) mn, MAX({col}) mx
FROM {tbl} GROUP BY LENGTH({col}) ORDER BY len"""))

show("H3 market_history.daily_bars: any bare symbols there? (cross-DB conflation check)", q(mh, """
SELECT LENGTH(symbol) AS len, COUNT(*) n_rows, COUNT(DISTINCT symbol) n_sym
FROM daily_bars GROUP BY LENGTH(symbol) ORDER BY len"""))

show("H4 market_history.daily_bars rows for the 5 codes in the shadow span", q(mh, """
SELECT symbol, adjustment_mode, COUNT(*) n, MIN(trade_date) d0, MAX(trade_date) d1
FROM daily_bars WHERE symbol IN ('SH000001','SZ000001','SH600519','SZ300750','BJ920099','000001','600519','300750','920099')
  AND trade_date BETWEEN '2026-03-12' AND '2026-09-03'
GROUP BY symbol, adjustment_mode ORDER BY symbol"""))
