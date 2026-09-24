# -*- coding: utf-8 -*-
import sqlite3, datetime as dt
P_OPS = r"D:/codex-A股交易/trading_local.sqlite3"
P_HIST = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
def q(conn, sql, params=()):
    print("-"*88); print("Q:", " ".join(sql.split()))
    try:
        for r in conn.execute(sql, params).fetchall()[:30]: print("   ", r)
    except Exception as e: print("   ERROR:", e)

ops = ro(P_OPS); hist = ro(P_HIST)

print("#"*100)
print("# G. Does ANY other table in trading_local carry a pre-2024-04-09 market date?")
print("#    (a second source of truth would refute 'the window does not exist')")
print("#"*100)
cands = [("daily_bar_cache","trade_date"),("full_market_feature_state","trade_date"),
         ("capital_flow_snapshots","trade_date"),("auto_discovered_candidates","trade_date"),
         ("historical_backtest_daily_equity","trade_date"),("historical_backtest_trades","trade_date"),
         ("historical_backtest_closed_trades","entry_date"),("trade_records","trade_date"),
         ("trade_cases","trade_date"),("experience_events","event_date"),
         ("market_regime_snapshots","as_of_date"),("full_market_feature_runs","as_of_date"),
         ("sector_membership_snapshots","effective_date"),("dataset2_staging_records","signal_date"),
         ("stock_profiles","launch_date"),("price_readiness_reports","updated_at")]
for t,c in cands:
    try:
        r = ops.execute(f"SELECT COUNT(*), MIN({c}), MAX({c}), SUM(CASE WHEN {c} < '2024-04-09' AND length({c})=10 THEN 1 ELSE 0 END) FROM {t}").fetchone()
        print(f"   {t:38s}.{c:14s} n={r[0]:<9} min={str(r[1])[:19]:<20} max={str(r[2])[:19]:<20} pre_2024_04_09={r[3]}")
    except Exception as e:
        print(f"   {t:38s}.{c:14s} ERROR {e}")

print()
print("#"*100)
print("# H. Backtest runs: do they CLAIM a start_date before the data floor? (corroborates or refutes)")
print("#"*100)
q(ops, "SELECT start_date, end_date, COUNT(*) n FROM historical_backtest_runs GROUP BY 1,2 ORDER BY 1 LIMIT 30")
q(ops, "SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM historical_backtest_daily_equity")

print()
print("#"*100)
print("# I. market_history side-tables: does instruments/universe/manifest imply deeper history?")
print("#"*100)
q(hist, "SELECT MIN(snapshot_date), MAX(snapshot_date), COUNT(*) FROM universe_snapshots")
q(hist, "SELECT MIN(list_date), MAX(list_date), COUNT(*) FROM instruments WHERE list_date IS NOT NULL")
q(hist, "SELECT COUNT(*) FROM instruments WHERE list_date < '2023-09-04'")
q(hist, "SELECT MIN(source_min_trade_date), MAX(source_max_trade_date), COUNT(*) FROM training_dataset_manifests")
q(hist, "SELECT MIN(requested_start), MIN(requested_end), MAX(requested_end) FROM ingest_runs" )

print()
print("#"*100)
print("# J. PER-SYMBOL FLOOR. The '2024-04-09' floor may be held up by a couple of symbols.")
print("#    Distribution of each stock's FIRST bar date -- the real usable-history denominator.")
print("#"*100)
q(hist, """
WITH firsts AS (
  SELECT b.symbol, MIN(b.trade_date) AS first_bar
  FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
  WHERE i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ')
  GROUP BY b.symbol)
SELECT substr(first_bar,1,7) AS first_month, COUNT(*) AS n_stocks
FROM firsts GROUP BY 1 ORDER BY 1""")
q(hist, """
WITH firsts AS (
  SELECT b.symbol, MIN(b.trade_date) AS first_bar
  FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
  WHERE i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ')
  GROUP BY b.symbol)
SELECT COUNT(*) AS n_stocks,
       MIN(first_bar) AS earliest,
       MAX(first_bar) AS latest,
       SUM(CASE WHEN first_bar<='2024-04-30' THEN 1 ELSE 0 END) AS start_by_2024_04,
       SUM(CASE WHEN first_bar<='2024-12-31' THEN 1 ELSE 0 END) AS start_by_2024_12,
       SUM(CASE WHEN first_bar>='2025-11-01' THEN 1 ELSE 0 END) AS start_2025_11_or_later
FROM firsts""")

print()
print("#"*100)
print("# K. THEIR ARITHMETIC. Recompute weekday/calendar-day counts myself.")
print("#"*100)
def dr(a,b):
    a=dt.date.fromisoformat(a); b=dt.date.fromisoformat(b)
    days=(b-a).days+1
    wd=sum(1 for i in range(days) if (a+dt.timedelta(days=i)).weekday()<5)
    return days,wd
for lbl,a,b in (("FULL WINDOW 2023-09-04..2026-09-04",'2023-09-04','2026-09-04'),
                ("HEAD GAP  2023-09-04..2024-04-08",'2023-09-04','2024-04-08'),
                ("COVERED   2024-04-09..2026-09-04",'2024-04-09','2026-09-04')):
    d,w=dr(a,b); print(f"   {lbl}: calendar_days={d}  weekdays={w}")
print("   THEY CLAIMED: 785 weekdays in window; 156 weekdays / 213 calendar days in the gap.")

# observed sessions in covered part -> empirical sessions-per-weekday rate
r = ops.execute("SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE length(trade_date)=10 AND trade_date>='2024-04-09'").fetchone()[0]
d,w = dr('2024-04-09','2026-09-04')
print(f"   observed distinct trade_dates 2024-04-09..2026-09-04 (cache) = {r} over {w} weekdays -> rate {r/w:.4f}")
dg,wg = dr('2023-09-04','2024-04-08')
print(f"   => empirically-scaled missing sessions in head gap = {wg} * {r/w:.4f} = {wg*r/w:.1f}")
df,wf = dr('2023-09-04','2026-09-04')
print(f"   => implied full-window sessions = {wf} * {r/w:.4f} = {wf*r/w:.1f}")
ops.close(); hist.close()
