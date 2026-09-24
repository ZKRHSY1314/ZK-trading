import sqlite3, os, json, collections
ROOT=r"D:\codex-A股交易"
tl=sqlite3.connect(f"file:{os.path.join(ROOT,'trading_local.sqlite3')}?mode=ro",uri=True); tl.row_factory=sqlite3.Row
def q(sql,params=(),n=20):
    print("SQL:"," ".join(sql.split()))
    out=[dict(r) for r in tl.execute(sql,params).fetchall()]
    for r in out[:n]: print("   ",{k:(str(v)[:150]) for k,v in r.items()})
    if len(out)>n: print(f"    ... {len(out)} rows")
    print(); return out

print("### eastmoney reachability, measured from capital_flow_ingestion_runs")
q("""SELECT status, error_type, COUNT(*) runs, MIN(started_at) first, MAX(started_at) last
     FROM capital_flow_ingestion_runs GROUP BY status, error_type ORDER BY runs DESC""")
q("""SELECT COUNT(*) AS runs_total, SUM(CASE WHEN accepted_count>0 THEN 1 ELSE 0 END) AS runs_that_accepted_rows
     FROM capital_flow_ingestion_runs""")
q("""SELECT endpoint, provider, COUNT(*) FROM capital_flow_ingestion_runs GROUP BY endpoint, provider""")

print("### eastmoney bar path (akshare.stock_zh_a_hist) last successful write")
q("""SELECT source, MAX(trade_date) last_bar, MAX(updated_at) last_written, COUNT(*) rows
     FROM daily_bar_cache GROUP BY source ORDER BY last_written DESC""")

print("### which source served the most recent full sweep")
q("""SELECT source, COUNT(*) rows FROM daily_bar_cache
     WHERE substr(updated_at,1,10) >= '2026-09-03' GROUP BY source ORDER BY rows DESC""")

print("### price_readiness_reports (any recorded provider health)")
q("""SELECT * FROM price_readiness_reports""", n=3)
