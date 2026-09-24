import sqlite3
OP=r"D:/codex-A股交易/trading_local.sqlite3"
c=sqlite3.connect(f"file:{OP}?mode=ro",uri=True); c.row_factory=sqlite3.Row
def q(s,a=()): return [dict(r) for r in c.execute(s,a).fetchall()]
def show(t,rows):
    print("\n### "+t)
    if not rows: print(" (none)");return
    ks=list(rows[0].keys()); print("  "+" | ".join(ks))
    for r in rows: print("  "+" | ".join(str(r[k]) for k in ks))

print("I. AMOUNT NULLITY BY SOURCE — the actual harm of falling through to Tencent")
show("I1", q("""
SELECT source, COUNT(*) rows, COUNT(DISTINCT symbol) syms,
       SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) amount_null,
       ROUND(100.0*SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END)/COUNT(*),2) pct_null
FROM daily_bar_cache GROUP BY source ORDER BY rows DESC"""))

print("\nJ. WINDOW-SCOPED (2023-09-04..2026-09-04) — does eastmoney matter in-window at all?")
show("J1", q("""
SELECT source, COUNT(*) rows, COUNT(DISTINCT symbol) syms
FROM daily_bar_cache
WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'
GROUP BY source ORDER BY rows DESC"""))

print("\nK. Do the 123 eastmoney symbols have ANY non-eastmoney coverage? (is the loss real?)")
show("K1", q("""
WITH em AS (SELECT DISTINCT symbol FROM daily_bar_cache WHERE source='akshare.stock_zh_a_hist')
SELECT COUNT(DISTINCT d.symbol) em_symbols_with_other_source_rows
FROM daily_bar_cache d JOIN em ON d.symbol=em.symbol
WHERE d.source<>'akshare.stock_zh_a_hist'"""))
show("K2 max trade_date for those 123 symbols overall", q("""
WITH em AS (SELECT DISTINCT symbol FROM daily_bar_cache WHERE source='akshare.stock_zh_a_hist')
SELECT MIN(mx) min_last, MAX(mx) max_last, COUNT(*) n FROM
 (SELECT d.symbol, MAX(d.trade_date) mx FROM daily_bar_cache d JOIN em ON d.symbol=em.symbol GROUP BY d.symbol)"""))
c.close()
