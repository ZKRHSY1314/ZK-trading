import sqlite3, sys, time
sys.stdout.reconfigure(encoding='utf-8')
TL = r"D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
c.execute("PRAGMA temp_store=MEMORY")
def q(sql, params=(), label=None, lim=400):
    t=time.time(); rows=c.execute(sql,params).fetchall()
    print(f"\n### {label}"); print("SQL:", " ".join(sql.split()))
    for r in rows[:lim]: print("   ", r)
    if len(rows)>lim: print(f"    ...({len(rows)} rows)")
    print(f"    [{time.time()-t:.1f}s]"); return rows
W0,W1="2023-09-04","2026-09-04"

q("SELECT COUNT(*) total, SUM(created_at IS NULL) null_created, SUM(updated_at IS NULL) null_updated, MIN(trade_date), MAX(trade_date) FROM daily_bar_cache", label="C1 daily_bar_cache totals")
q("SELECT MIN(created_at), MAX(created_at), MIN(updated_at), MAX(updated_at) FROM daily_bar_cache", label="C2 created_at / updated_at wall-clock range (ALL rows)")
q("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ?", (W0,W1), label="C3 rows inside research window 2023-09-04..2026-09-04")
q("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date < ?", (W0,), label="C4 rows BEFORE window (warm-up region)")
q("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date > ?", (W1,), label="C5 rows AFTER window")
q("SELECT substr(created_at,1,10) d, COUNT(*) n, COUNT(DISTINCT symbol) syms, MIN(trade_date), MAX(trade_date) FROM daily_bar_cache GROUP BY d ORDER BY d", label="C6 created_at ingestion calendar (ALL rows)")
q("SELECT substr(updated_at,1,10) d, COUNT(*) n FROM daily_bar_cache GROUP BY d ORDER BY d", label="C7 updated_at calendar (ALL rows)")
q("SELECT source, COUNT(*) n, MIN(trade_date), MAX(trade_date), MIN(created_at), MAX(created_at) FROM daily_bar_cache GROUP BY source ORDER BY n DESC", label="C8 by source")
c.close()
