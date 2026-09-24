import sqlite3, json
OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c
op = ro(OP); mh = ro(MH)
def q(c, sql, p=()):
    return [dict(r) for r in c.execute(sql, p).fetchall()]
def show(t, rows, n=40):
    print("="*90); print(t)
    for r in rows[:n]: print("   ", r)
    if len(rows) > n: print(f"    ... {len(rows)-n} more")

# ---- A. DDL / collation: does symbol have COLLATE NOCASE? ----
show("A1 DDL daily_bar_cache", q(op, "SELECT sql FROM sqlite_master WHERE name='daily_bar_cache'"))
show("A2 indexes on daily_bar_cache", q(op, "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='daily_bar_cache'"))

# ---- B. FULL length + shape distribution of symbol (not assuming 6 or 8) ----
show("B1 length distribution of symbol (rows + distinct symbols)", q(op, """
SELECT LENGTH(symbol) AS len,
       COUNT(*) AS n_rows,
       COUNT(DISTINCT symbol) AS n_symbols,
       MIN(symbol) AS min_sym, MAX(symbol) AS max_sym
FROM daily_bar_cache GROUP BY LENGTH(symbol) ORDER BY len"""))

show("B2 prefix shape census (first 2 chars when len=8)", q(op, """
SELECT substr(symbol,1,2) AS pfx, COUNT(DISTINCT symbol) AS n_syms, COUNT(*) AS n_rows
FROM daily_bar_cache WHERE LENGTH(symbol)=8
GROUP BY substr(symbol,1,2) ORDER BY n_syms DESC"""))

# is every len-8 symbol really 2 alpha + 6 digit?
show("B3 len-8 symbols NOT matching 2alpha+6digit", q(op, """
SELECT symbol, COUNT(*) n FROM daily_bar_cache
WHERE LENGTH(symbol)=8
  AND NOT (substr(symbol,1,2) GLOB '[A-Za-z][A-Za-z]' AND substr(symbol,3) GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]')
GROUP BY symbol"""))

show("B4 len-6 symbols NOT pure 6 digits", q(op, """
SELECT symbol, COUNT(*) n FROM daily_bar_cache
WHERE LENGTH(symbol)=6 AND NOT symbol GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]'
GROUP BY symbol"""))

# ---- C. The bare symbols themselves ----
show("C1 every symbol whose length <> 8 (full enumeration)", q(op, """
SELECT symbol, LENGTH(symbol) AS len, COUNT(*) AS n_rows,
       MIN(trade_date) AS d0, MAX(trade_date) AS d1,
       COUNT(DISTINCT quality_status) AS n_qs, MIN(quality_status) AS qs_min, MAX(quality_status) AS qs_max,
       MIN(adjustment_mode) AS am_min, MAX(adjustment_mode) AS am_max,
       MIN(source) AS src_min, MAX(source) AS src_max,
       MIN(created_at) AS created_min, MAX(created_at) AS created_max
FROM daily_bar_cache WHERE LENGTH(symbol) <> 8
GROUP BY symbol ORDER BY symbol"""))

# ---- D. Denominators, computed independently ----
show("D1 spelling / code denominators", q(op, """
SELECT
 (SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache) AS distinct_spellings,
 (SELECT COUNT(DISTINCT CASE WHEN LENGTH(symbol)=8 THEN substr(symbol,3) ELSE symbol END) FROM daily_bar_cache) AS distinct_codes_collapsed,
 (SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE LENGTH(symbol)=8) AS distinct_prefixed,
 (SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE LENGTH(symbol)<>8) AS distinct_nonprefixed,
 (SELECT COUNT(*) FROM daily_bar_cache WHERE LENGTH(symbol)<>8) AS rows_nonprefixed,
 (SELECT COUNT(*) FROM daily_bar_cache) AS total_rows
"""))

# CRITICAL: how many 6-digit codes are legitimately carried by >1 exchange prefix?
show("D2 codes carried by MORE THAN ONE prefix (these are REAL distinct securities, not aliases)", q(op, """
SELECT substr(symbol,3) AS code, COUNT(DISTINCT symbol) AS n_spellings,
       GROUP_CONCAT(DISTINCT symbol) AS spellings
FROM daily_bar_cache WHERE LENGTH(symbol)=8
GROUP BY substr(symbol,3) HAVING COUNT(DISTINCT symbol) > 1 ORDER BY code"""))

# ---- E. Bare-vs-prefixed overlap, counted per (bare, prefixed) pair, DISTINCT DATES not rows ----
show("E1 bare<->prefixed overlap, distinct trade_date, independent formulation", q(op, """
SELECT b.symbol AS bare, p.symbol AS prefixed,
       COUNT(DISTINCT b.trade_date) AS shared_dates,
       SUM(CASE WHEN b.close IS NOT NULL AND p.close IS NOT NULL AND ABS(b.close-p.close) > 1e-9 THEN 1 ELSE 0 END) AS closes_differ_any,
       SUM(CASE WHEN b.close IS NOT NULL AND p.close IS NOT NULL AND ABS(b.close-p.close) > 0.005 THEN 1 ELSE 0 END) AS closes_differ_gt_half_cent,
       ROUND(MAX(ABS(b.close-p.close)),4) AS max_abs_diff,
       ROUND(AVG(b.close),4) AS avg_bare_close, ROUND(AVG(p.close),4) AS avg_pref_close
FROM daily_bar_cache b
JOIN daily_bar_cache p
  ON p.trade_date = b.trade_date AND LENGTH(p.symbol)=8 AND substr(p.symbol,3)=b.symbol
WHERE LENGTH(b.symbol)=6
GROUP BY b.symbol, p.symbol ORDER BY b.symbol, p.symbol"""))

# date span of each bare symbol vs its prefixed partner over the SAME span
show("E2 per-bare date span, and prefixed partner rows inside that same span", q(op, """
WITH bare AS (SELECT symbol, MIN(trade_date) d0, MAX(trade_date) d1, COUNT(*) n FROM daily_bar_cache WHERE LENGTH(symbol)=6 GROUP BY symbol)
SELECT bare.symbol AS bare, bare.n AS bare_rows, bare.d0, bare.d1,
       p.symbol AS prefixed,
       (SELECT COUNT(*) FROM daily_bar_cache x WHERE x.symbol=p.symbol AND x.trade_date BETWEEN bare.d0 AND bare.d1) AS pref_rows_in_span
FROM bare JOIN (SELECT DISTINCT symbol FROM daily_bar_cache WHERE LENGTH(symbol)=8) p
  ON substr(p.symbol,3)=bare.symbol
ORDER BY bare.symbol, p.symbol"""))
