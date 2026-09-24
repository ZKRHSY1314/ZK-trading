import sqlite3
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
W0, FLOOR = "2023-09-04", "2024-04-09"

# tables/columns that carry a real market/trade date
TARGETS = [
 (TL,"auto_discovered_candidates","trade_date"),
 (TL,"capital_flow_snapshots","trade_date"),
 (TL,"full_market_feature_state","trade_date"),
 (TL,"full_market_feature_state","as_of_date"),
 (TL,"historical_backtest_daily_equity","trade_date"),
 (TL,"historical_backtest_trades","trade_date"),
 (TL,"historical_backtest_closed_trades","entry_date"),
 (TL,"trade_records","trade_date"),
 (TL,"trade_cases","trade_date"),
 (TL,"experience_events","event_date"),
 (TL,"market_regime_snapshots","as_of_date"),
 (TL,"sector_membership_snapshots","effective_date"),
 (TL,"dataset2_staging_records","signal_date"),
 (TL,"full_market_feature_runs","as_of_date"),
 (MH,"universe_snapshots","snapshot_date"),
 (MH,"bar_quality_issues","trade_date"),
]
print("### I. IS ANY PRE-FLOOR MARKET DATE PRESENT ANYWHERE? ###")
print(f"{'table.column':52s} {'rows':>9s} {'min':>12s} {'max':>12s} {'<2024-04-09':>12s} {'<2023-09-04':>12s}")
for path,tbl,col in TARGETS:
    c = ro(path)
    try:
        q=(f"SELECT COUNT(*),MIN({col}),MAX({col}),"
           f"SUM(CASE WHEN {col} < '{FLOOR}' THEN 1 ELSE 0 END),"
           f"SUM(CASE WHEN {col} < '{W0}' THEN 1 ELSE 0 END) FROM {tbl}")
        n,mn,mx,pre,prew = c.execute(q).fetchone()
        print(f"{tbl+'.'+col:52s} {n:>9d} {str(mn):>12s} {str(mx):>12s} {str(pre):>12s} {str(prew):>12s}")
    except Exception as e:
        print(f"{tbl+'.'+col:52s} ERR {e}")
    c.close()

print()
print("### J. DO BACKTESTS CLAIM TO COVER PERIODS WITH NO BARS? (lineage cross-check) ###")
c = ro(TL)
q = ("SELECT MIN(start_date),MAX(start_date),MIN(end_date),MAX(end_date),COUNT(*),"
     "SUM(CASE WHEN start_date < '2024-04-09' THEN 1 ELSE 0 END) FROM historical_backtest_runs")
print("  historical_backtest_runs:", c.execute(q).fetchone())
print("  SQL:", q)
q2 = ("SELECT start_date,end_date,COUNT(*) FROM historical_backtest_runs "
      "GROUP BY 1,2 ORDER BY 1 LIMIT 15")
for r in c.execute(q2).fetchall(): print("   run window:", r)
q3 = ("SELECT COUNT(*),MIN(trade_date),MAX(trade_date), "
      "SUM(CASE WHEN trade_date<'2024-04-09' THEN 1 ELSE 0 END) FROM historical_backtest_daily_equity")
print("  historical_backtest_daily_equity:", c.execute(q3).fetchone())
c.close()

print()
print("### K. IS THE FLOOR A LISTING ARTIFACT? (instruments list_date distribution) ###")
c = ro(MH)
q=("SELECT SUM(list_date<'2023-09-04'),SUM(list_date>='2023-09-04' AND list_date<'2024-04-09'),"
   "SUM(list_date>='2024-04-09'),SUM(list_date IS NULL),COUNT(*) FROM instruments")
print("  instruments listed pre-window / in-gap / post-floor / null / total:", c.execute(q).fetchone())
print("  SQL:", q)
q2=("SELECT COUNT(*) FROM instruments WHERE list_date < '2023-09-04' AND (delist_date IS NULL OR delist_date > '2024-04-09')")
print("  instruments that WERE tradable before the floor and still alive at floor:", c.execute(q2).fetchone()[0])
print("  -> these securities HAD real market history in the gap; the store simply lacks it.")
c.close()
