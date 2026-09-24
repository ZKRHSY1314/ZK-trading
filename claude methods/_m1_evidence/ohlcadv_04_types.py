import sqlite3, json
tl = sqlite3.connect(r"file:D:/codex-A股交易/trading_local.sqlite3?mode=ro", uri=True); tl.row_factory=sqlite3.Row
def show(l,s,p=(),lim=20):
    print("\n"+"="*90); print("### "+l); print("SQL: "+" ".join(s.split()))
    r=[dict(x) for x in tl.execute(s,p).fetchall()]; print("ROWS: %d"%len(r))
    for x in r[:lim]: print("   ",json.dumps(x,ensure_ascii=False,default=str))
    return r
show("X1 storage typeof() census for price columns (text-stored prices would defeat numeric predicates)",
 """SELECT typeof(open) t_open, typeof(high) t_high, typeof(low) t_low, typeof(close) t_close, COUNT(*) n
    FROM daily_bar_cache GROUP BY 1,2,3,4 ORDER BY n DESC""")
show("X2 belt-and-braces: any row whose open is text/blob/empty (would not be caught by CAST<0.00005)",
 """SELECT symbol, trade_date, open, typeof(open) t, quality_status FROM daily_bar_cache
    WHERE typeof(open) NOT IN ('real','integer') LIMIT 20""")
show("X3 exhaustive: min(open) over ready rows and the count at that minimum",
 """SELECT MIN(CAST(open AS REAL)) min_open, MIN(CAST(low AS REAL)) min_low,
           MIN(CAST(high AS REAL)) min_high, MIN(CAST(close AS REAL)) min_close
    FROM daily_bar_cache WHERE quality_status='ready'""")
show("X4 next-smallest opens above zero (is 0.0 an isolated cliff or a tail?)",
 """SELECT symbol, trade_date, open FROM daily_bar_cache WHERE quality_status='ready'
    ORDER BY CAST(open AS REAL) ASC LIMIT 12""")
show("X5 duplicate (symbol,trade_date) pairs in daily_bar_cache",
 """SELECT COUNT(*) n_dup_groups FROM (SELECT symbol, trade_date FROM daily_bar_cache
    GROUP BY symbol, trade_date HAVING COUNT(*)>1)""")
show("X6 invalid trade_date strings among ready rows",
 """SELECT COUNT(*) bad_len_or_format FROM daily_bar_cache
    WHERE quality_status='ready' AND (length(trade_date)<>10 OR trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')""")
tl.close()
