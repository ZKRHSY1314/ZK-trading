import sqlite3, sys, time
sys.stdout.reconfigure(encoding='utf-8')
MH = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)
def q(sql, params=(), label=None, lim=500):
    t=time.time(); rows = c.execute(sql, params).fetchall()
    print(f"\n### {label}"); print("SQL:", " ".join(sql.split()))
    for r in rows[:lim]: print("   ", r)
    if len(rows)>lim: print(f"    ... ({len(rows)} rows)")
    print(f"    [{time.time()-t:.1f}s]"); return rows

q("SELECT provider, adjustment_mode, COUNT(*) n, MIN(trade_date), MAX(trade_date), MIN(fetched_at), MAX(fetched_at), MIN(available_at), MAX(available_at) FROM daily_bars GROUP BY provider, adjustment_mode ORDER BY n DESC",
  label="A8 provider x adjustment_mode")
q("SELECT COUNT(*) FROM daily_bars WHERE available_at <> fetched_at", label="A8b rows where available_at != fetched_at")
q("SELECT COUNT(*) FROM daily_bars WHERE substr(available_at,1,10) <> substr(fetched_at,1,10)", label="A8c rows where available_at DAY != fetched_at DAY")
q("SELECT substr(fetched_at,1,10) fetch_day, COUNT(*) n, COUNT(DISTINCT symbol) syms, MIN(trade_date), MAX(trade_date) FROM daily_bars GROUP BY fetch_day ORDER BY fetch_day",
  label="A9 fetched_at collection calendar")
q("SELECT quality_status, COUNT(*) FROM daily_bars GROUP BY quality_status", label="A10 quality_status")
q("SELECT COUNT(*) FROM daily_bars WHERE substr(fetched_at,1,10) < trade_date", label="A12 fetched_at BEFORE trade_date (impossible)")
q("SELECT ingest_run_id, COUNT(*) n, COUNT(DISTINCT symbol) syms, MIN(trade_date), MAX(trade_date), MIN(fetched_at), MAX(fetched_at) FROM daily_bars GROUP BY ingest_run_id ORDER BY n DESC LIMIT 40",
  label="A14 rows per ingest_run_id")
c.close()
