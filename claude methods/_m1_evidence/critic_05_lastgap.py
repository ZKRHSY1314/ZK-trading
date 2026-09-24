# -*- coding: utf-8 -*-
"""Close the last two escape hatches. STRICT READ-ONLY."""
import sqlite3,sys,io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
op=sqlite3.connect(r"file:D:\codex-A股交易\trading_local.sqlite3?mode=ro",uri=True)
def show(t,sql):
    print("="*78);print(t);print("SQL:"," ".join(sql.split()))
    try:
        c=op.execute(sql);rows=c.fetchall();print("COLS:",[d[0] for d in c.description])
        for r in rows[:30]:print("   ",r)
    except Exception as e:print("  ERROR:",e)
    print()

print("K1 global_market_bars full schema (the last plausible rescue table)")
for r in op.execute('PRAGMA table_info(global_market_bars)'): print("   ",r)
print()
show("K2 global_market_bars content extent",
 "SELECT COUNT(*) n FROM global_market_bars")

# find its date column dynamically
cols=[r[1] for r in op.execute('PRAGMA table_info(global_market_bars)')]
cand=[c for c in cols if any(k in c.lower() for k in ('date','time','dt','day'))]
print("   date-ish cols:",cand)
for c in cand:
    show(f"K3 global_market_bars extent on {c}",
      f'SELECT MIN("{c}") mn, MAX("{c}") mx, COUNT(*) n, COUNT(DISTINCT symbol) syms FROM global_market_bars')

show("K4 ROLLING-WINDOW PROOF: when were the OLDEST bars written? "
     "(created_at of rows at the 2024 floor vs 2026 tip)",
 """SELECT CASE WHEN trade_date < '2024-07-01' THEN 'A: trade_date 2024-04..06'
                WHEN trade_date < '2025-07-01' THEN 'B: trade_date 2024-07..2025-06'
                ELSE 'C: trade_date 2025-07+' END AS bucket,
           COUNT(*) n, MIN(created_at) min_created, MAX(created_at) max_created,
           MIN(updated_at) min_updated, MAX(updated_at) max_updated
    FROM daily_bar_cache WHERE date(trade_date) IS NOT NULL GROUP BY 1 ORDER BY 1""")

show("K5 source mix — which fetcher produced the store, and does any source reach further back?",
 """SELECT source, COUNT(*) n, COUNT(DISTINCT symbol) syms, MIN(trade_date) min_td, MAX(trade_date) max_td
    FROM daily_bar_cache WHERE date(trade_date) IS NOT NULL GROUP BY source ORDER BY n DESC""")
op.close()
