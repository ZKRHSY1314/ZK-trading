import sqlite3, io, time
CACHE=r"D:/codex-A股交易/trading_local.sqlite3"
OUT=r"D:/codex-A股交易/claude methods/_m1_evidence/lineage_reconcile6_output.txt"
buf=io.StringIO()
def P(*a):
    s=" ".join(str(x) for x in a); buf.write(s+"\n"); print(s.encode("ascii","replace").decode("ascii"))
c=sqlite3.connect(f"file:{CACHE}?mode=ro",uri=True); c.execute("PRAGMA query_only=ON"); c.row_factory=sqlite3.Row
def q(t,sql,p=(),lim=30):
    st=time.time(); rows=c.execute(sql,p).fetchall(); P("\n### "+t); P("SQL: "+" ".join(sql.split()))
    for r in rows[:lim]: P("   ",dict(r))
    P("    [%.1fs]"%(time.time()-st)); return rows
q("M54 cache inception: created_at floor vs trade_date floor", """
SELECT MIN(created_at) AS min_created_at, MAX(created_at) AS max_created_at,
       MIN(CASE WHEN trade_date!='ERROR' THEN trade_date END) AS min_trade_date
FROM daily_bar_cache""")
q("M55 no historical backfill: oldest trade_date reachable per created_at month", """
SELECT substr(created_at,1,7) AS created_month, COUNT(*) AS rows,
       MIN(trade_date) AS oldest_trade_date_written, MAX(trade_date) AS newest_trade_date_written
FROM daily_bar_cache WHERE trade_date!='ERROR' GROUP BY 1 ORDER BY 1""")
q("M56 stale rows: last updated_at bucket", """
SELECT substr(updated_at,1,7) AS updated_month, COUNT(*) AS rows FROM daily_bar_cache GROUP BY 1 ORDER BY 1""")
c.close(); open(OUT,"w",encoding="utf-8").write(buf.getvalue()); print("\nWROTE",OUT)
