import sqlite3, os
ROOT=r"D:\codex-A股交易"
tl=sqlite3.connect(f"file:{os.path.join(ROOT,'trading_local.sqlite3')}?mode=ro",uri=True); tl.row_factory=sqlite3.Row
def q(c,sql,params=(),n=30):
    print("SQL:"," ".join(sql.split()))
    out=[dict(r) for r in c.execute(sql,params).fetchall()]
    for r in out[:n]: print("   ",r)
    if len(out)>n: print(f"    ... {len(out)} rows total")
    print(); return out

print("### rogue / unnormalized symbols")
q(tl,"""SELECT symbol, COUNT(*) rows, MIN(trade_date) mn, MAX(trade_date) mx, MAX(source) src
        FROM daily_bar_cache WHERE symbol NOT LIKE 'SH%' AND symbol NOT LIKE 'SZ%' AND symbol NOT LIKE 'BJ%'
        GROUP BY symbol""")

print("### interior holes: sessions inside each symbol's own observed span that are absent")
q(tl,"""WITH sess AS (SELECT DISTINCT trade_date d FROM daily_bar_cache WHERE length(trade_date)=10),
        span AS (SELECT symbol, MIN(trade_date) s, MAX(trade_date) e, COUNT(*) n
                 FROM daily_bar_cache WHERE length(trade_date)=10 GROUP BY symbol),
        expect AS (SELECT sp.symbol, COUNT(*) AS expected
                   FROM span sp JOIN sess ON sess.d BETWEEN sp.s AND sp.e GROUP BY sp.symbol)
        SELECT SUM(e.expected - sp.n) AS interior_missing_rows,
               COUNT(*) AS symbols,
               SUM(CASE WHEN e.expected > sp.n THEN 1 ELSE 0 END) AS symbols_with_holes
        FROM expect e JOIN span sp USING(symbol)""")

print("### head gap sized on the covered period start (all symbols must gain 2023-09-04..2024-04-08)")
q(tl,"""SELECT COUNT(DISTINCT symbol) AS symbols_needing_head_backfill
        FROM daily_bar_cache WHERE length(trade_date)=10""")

print("### last update recency (staleness of the operational cache)")
q(tl,"""SELECT substr(updated_at,1,10) AS updated_day, COUNT(*) AS rows
        FROM daily_bar_cache GROUP BY updated_day ORDER BY updated_day DESC LIMIT 12""")

print("### average bytes per row, measured")
q(tl,"""SELECT (SELECT SUM(pgsize) FROM dbstat WHERE name='daily_bar_cache') AS table_bytes,
               (SELECT SUM(pgsize) FROM dbstat WHERE name LIKE '%daily_bar_cache%') AS table_plus_index_bytes,
               (SELECT COUNT(*) FROM daily_bar_cache) AS rows""")
