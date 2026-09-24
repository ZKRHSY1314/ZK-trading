import sqlite3, sys, time
sys.stdout.reconfigure(encoding='utf-8')
TL = r"D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
def q(sql, params=(), label=None, lim=400):
    t=time.time(); rows=c.execute(sql,params).fetchall()
    print(f"\n### {label}"); print("SQL:", " ".join(sql.split()))
    for r in rows[:lim]: print("   ", r)
    if len(rows)>lim: print(f"    ...({len(rows)} rows)")
    print(f"    [{time.time()-t:.1f}s]"); return rows
W0,W1="2023-09-04","2026-09-04"
VALID = "trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'"

q(f"SELECT COUNT(*) FROM daily_bar_cache WHERE NOT (trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')", label="D0 rows with a non-ISO / invalid trade_date")
q(f"SELECT id, symbol, trade_date, source, quality_status, created_at FROM daily_bar_cache WHERE NOT (trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')", label="D0b those rows")

q(f"""SELECT CASE
   WHEN substr(created_at,1,10) = trade_date THEN 'A_same_day_LIVE'
   WHEN julianday(substr(created_at,1,10)) - julianday(trade_date) <= 3 THEN 'B_1to3_days'
   WHEN julianday(substr(created_at,1,10)) - julianday(trade_date) <= 30 THEN 'C_4to30_days'
   WHEN julianday(substr(created_at,1,10)) - julianday(trade_date) <= 90 THEN 'D_31to90_days'
   WHEN julianday(substr(created_at,1,10)) - julianday(trade_date) <= 365 THEN 'E_91to365_days'
   WHEN julianday(substr(created_at,1,10)) - julianday(trade_date) <= 730 THEN 'F_1to2_years'
   ELSE 'G_over_2_years' END AS bucket,
  COUNT(*) n, MIN(trade_date) min_td, MAX(trade_date) max_td
 FROM daily_bar_cache WHERE {VALID} GROUP BY bucket ORDER BY bucket""",
  label="D1 created_at MINUS trade_date lag buckets, window rows (backfill vs live)")

q(f"SELECT COUNT(*) FROM daily_bar_cache WHERE {VALID} AND substr(created_at,1,10) < trade_date", label="D2 IMPOSSIBLE: created_at BEFORE trade_date")
q(f"SELECT id,symbol,trade_date,source,created_at,updated_at FROM daily_bar_cache WHERE {VALID} AND substr(created_at,1,10) < trade_date LIMIT 20", label="D2b examples of created_at < trade_date")

q(f"SELECT substr(trade_date,1,7) ym, COUNT(*) n, SUM(substr(created_at,1,10)=trade_date) live_same_day, MIN(created_at) first_created, MAX(created_at) last_created FROM daily_bar_cache WHERE {VALID} GROUP BY ym ORDER BY ym",
  label="D3 per trade-month: rows and how many were created same-day (live)")

q(f"SELECT COUNT(*) FROM daily_bar_cache WHERE {VALID} AND updated_at IS NOT NULL AND substr(updated_at,1,10) <> substr(created_at,1,10)", label="D4 rows revised on a later day than created (restatement evidence)")
q(f"SELECT substr(created_at,1,10) cd, substr(updated_at,1,10) ud, COUNT(*) n FROM daily_bar_cache WHERE {VALID} GROUP BY cd,ud ORDER BY n DESC LIMIT 40", label="D5 created-day x updated-day matrix (restatement map)")

q(f"SELECT adjustment_mode, COUNT(*) n FROM daily_bar_cache GROUP BY adjustment_mode", label="D6 adjustment_mode distribution (vintage question)")
q(f"SELECT volume_unit, COUNT(*) n FROM daily_bar_cache GROUP BY volume_unit", label="D7 volume_unit distribution")
q(f"SELECT quality_status, COUNT(*) n FROM daily_bar_cache GROUP BY quality_status", label="D8 quality_status")
c.close()
