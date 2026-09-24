import sqlite3, datetime, json
OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c
op = ro(OP); mh = ro(MH)
def q(c, sql, args=()):
    return [dict(r) for r in c.execute(sql, args).fetchall()]
def show(t, rows, lim=40):
    print("\n### " + t)
    if not rows: print("  (no rows)"); return
    ks = list(rows[0].keys())
    print("  " + " | ".join(ks))
    for r in rows[:lim]:
        print("  " + " | ".join(str(r[k]) for k in ks))
    if len(rows) > lim: print(f"  ... {len(rows)-lim} more")

print("="*100); print("A. SOURCE BREAKDOWN — rows AND distinct symbols (their SQL counted rows only)")
show("A1 per-source", q(op, """
SELECT source,
       COUNT(*) rows,
       COUNT(DISTINCT symbol) distinct_symbols,
       MIN(trade_date) first_bar, MAX(trade_date) last_bar,
       MIN(updated_at) first_written, MAX(updated_at) last_written
FROM daily_bar_cache GROUP BY source ORDER BY rows DESC"""))

print("\n"+"="*100); print("B. ARE THE akshare.stock_zh_a_hist SYMBOLS STOCKS OR INDICES?")
show("B1 symbol shape", q(op, """
SELECT CASE
         WHEN symbol LIKE 'SH0000%' OR symbol LIKE 'SZ3990%' OR symbol LIKE '0000%' THEN 'index_like'
         ELSE 'other' END shape,
       COUNT(DISTINCT symbol) n
FROM daily_bar_cache WHERE source='akshare.stock_zh_a_hist' GROUP BY 1"""))
show("B2 sample symbols", q(op, """
SELECT DISTINCT symbol FROM daily_bar_cache WHERE source='akshare.stock_zh_a_hist'
ORDER BY symbol LIMIT 25"""))
# cross-join to instruments in market_history for asset_type
syms = [r['symbol'] for r in q(op, "SELECT DISTINCT symbol FROM daily_bar_cache WHERE source='akshare.stock_zh_a_hist'")]
print(f"\n  akshare.stock_zh_a_hist distinct symbols = {len(syms)}")
ph = ",".join("?"*len(syms))
show("B3 instruments classification (market_history)", q(mh, f"""
SELECT exchange, asset_type, status, COUNT(*) n FROM instruments
WHERE symbol IN ({ph}) GROUP BY exchange, asset_type, status ORDER BY n DESC""", syms))
unmatched = q(mh, f"SELECT COUNT(*) n FROM instruments WHERE symbol IN ({ph})", syms)[0]['n']
print(f"  matched in instruments: {unmatched} of {len(syms)}")

print("\n"+"="*100); print("C. IS `source` LAST-WRITER? (overwrite would understate historical akshare share)")
show("C1 UNIQUE + upsert check", q(op, """
SELECT COUNT(*) rows_where_created_ne_updated FROM daily_bar_cache
WHERE created_at IS NOT NULL AND updated_at IS NOT NULL AND created_at <> updated_at"""))
show("C2 akshare rows created vs updated", q(op, """
SELECT MIN(created_at) c_min, MAX(created_at) c_max, MIN(updated_at) u_min, MAX(updated_at) u_max,
       SUM(CASE WHEN created_at<>updated_at THEN 1 ELSE 0 END) rewritten
FROM daily_bar_cache WHERE source='akshare.stock_zh_a_hist'"""))
show("C3 rows created in the akshare era (2026-07) by CURRENT source", q(op, """
SELECT source, COUNT(*) rows, COUNT(DISTINCT symbol) syms
FROM daily_bar_cache WHERE substr(created_at,1,7)='2026-07'
GROUP BY source ORDER BY rows DESC"""))

print("\n"+"="*100); print("D. STALENESS ARITHMETIC")
r = q(op, "SELECT MAX(updated_at) u, MAX(trade_date) t FROM daily_bar_cache WHERE source='akshare.stock_zh_a_hist'")[0]
print("  last_written =", r['u'], " last_bar =", r['t'])
d = datetime.date.fromisoformat(r['u'][:10])
for ref in ("2026-09-04","2026-09-05"):
    print(f"  days from last_written to {ref}: {(datetime.date.fromisoformat(ref)-d).days}")
d2 = datetime.date.fromisoformat(r['t'])
for ref in ("2026-09-04","2026-09-05"):
    print(f"  days from last_bar({r['t']}) to {ref}: {(datetime.date.fromisoformat(ref)-d2).days}")

print("\n"+"="*100); print("E. CAPITAL FLOW RUNS — is this even the bar endpoint?")
cols = [c['name'] for c in q(op, "PRAGMA table_info(capital_flow_ingestion_runs)")]
print("  columns:", cols)
show("E1 by source/endpoint", q(op, """
SELECT source, endpoint, status, error_type, COUNT(*) n, MIN(started_at) f, MAX(started_at) l
FROM capital_flow_ingestion_runs GROUP BY source, endpoint, status, error_type ORDER BY n DESC"""))
show("E2 total + accepted", q(op, """
SELECT COUNT(*) total, SUM(CASE WHEN accepted_count>0 THEN 1 ELSE 0 END) accepted_gt0,
       MIN(started_at) first, MAX(started_at) last FROM capital_flow_ingestion_runs"""))
op.close(); mh.close()
