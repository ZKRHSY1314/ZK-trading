import sqlite3, json, collections
OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True); c.row_factory = sqlite3.Row; return c
op, mh = ro(OP), ro(MH)
def q(c,s,a=()): return [dict(r) for r in c.execute(s,a).fetchall()]
def show(t,rows,lim=60):
    print("\n### "+t)
    if not rows: print("  (none)"); return
    ks=list(rows[0].keys()); print("  "+" | ".join(ks))
    for r in rows[:lim]: print("  "+" | ".join(str(r[k]) for k in ks))
    if len(rows)>lim: print(f"  ...{len(rows)-lim} more")

print("="*100); print("E. CAPITAL FLOW RUNS (corrected columns)")
show("E1 provider/endpoint x status x error", q(op,"""
SELECT provider, endpoint, status, error_type, COUNT(*) n,
       MIN(started_at) first, MAX(started_at) last
FROM capital_flow_ingestion_runs GROUP BY provider,endpoint,status,error_type ORDER BY n DESC"""))
show("E2 totals", q(op,"""
SELECT COUNT(*) total, COUNT(DISTINCT date(started_at)) distinct_days,
       SUM(CASE WHEN accepted_count>0 THEN 1 ELSE 0 END) accepted_gt0,
       SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END) status_ok,
       MIN(started_at) first, MAX(started_at) last FROM capital_flow_ingestion_runs"""))
show("E3 the one that accepted", q(op,"""
SELECT id,scope,symbol,status,endpoint,started_at,fetched_count,accepted_count,error_type
FROM capital_flow_ingestion_runs WHERE accepted_count>0"""))
show("E4 per-day timeline", q(op,"""
SELECT date(started_at) d, COUNT(*) runs,
       SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) failed,
       SUM(CASE WHEN status='degraded' THEN 1 ELSE 0 END) degraded,
       SUM(CASE WHEN status NOT IN('failed','degraded') THEN 1 ELSE 0 END) other
FROM capital_flow_ingestion_runs GROUP BY 1 ORDER BY 1"""))

print("\n"+"="*100); print("F. DIRECT BAR-PATH EVIDENCE (market_history.ingest_runs)")
cols=[c['name'] for c in q(mh,"PRAGMA table_info(ingest_runs)")]; print("  cols:", cols)
show("F1 recent runs", q(mh,"""
SELECT * FROM ingest_runs ORDER BY id DESC LIMIT 6"""),6)

print("\n"+"="*100); print("G. WHICH SOURCE ACTUALLY SERVED BARS, BY WEEK (created_at)")
show("G1", q(op,"""
SELECT substr(created_at,1,10) day, source, COUNT(*) rows, COUNT(DISTINCT symbol) syms
FROM daily_bar_cache WHERE created_at >= '2026-07-10'
GROUP BY 1,2 ORDER BY 1,rows DESC"""),80)

print("\n"+"="*100); print("H. eastmoney-reaching sources in cache (which akshare fns hit push2his?)")
print("  akshare.stock_zh_a_hist  -> push2his.eastmoney.com/api/qt/stock/kline/get   (CONFIRMED in venv)")
print("  akshare.stock_zh_a_daily -> Sina (stock_zh_a_daily)                          ")
print("  akshare.stock_zh_index_daily -> Sina                                         ")
show("H1 rows by eastmoney-vs-not", q(op,"""
SELECT CASE WHEN source='akshare.stock_zh_a_hist' THEN 'eastmoney_push2his' ELSE 'not_eastmoney' END grp,
       COUNT(*) rows, COUNT(DISTINCT symbol) syms,
       ROUND(100.0*COUNT(*)/(SELECT COUNT(*) FROM daily_bar_cache),4) pct_rows
FROM daily_bar_cache GROUP BY 1"""))
op.close(); mh.close()
