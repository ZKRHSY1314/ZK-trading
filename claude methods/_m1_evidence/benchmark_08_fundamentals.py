import sqlite3, sys, json
sys.stdout.reconfigure(encoding='utf-8')
OP = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
op=ro(OP)

print("### Q23 symbol_fundamental_snapshot: as_of / available_at distribution")
q="SELECT as_of, source, COUNT(*) n, COUNT(DISTINCT symbol) syms, MIN(available_at), MAX(available_at), MIN(created_at), MAX(created_at) FROM symbol_fundamental_snapshot GROUP BY as_of, source ORDER BY as_of"
print("SQL:", q)
for r in op.execute(q): print("   ", r)
q="SELECT COUNT(*) rows, COUNT(DISTINCT symbol) syms, COUNT(DISTINCT as_of) dates, MIN(as_of), MAX(as_of) FROM symbol_fundamental_snapshot"
print("SQL:", q, "->", op.execute(q).fetchone())
q="SELECT SUM(total_share_billion IS NULL), SUM(book_value_per_share IS NULL), SUM(pb IS NULL), SUM(market_cap_billion IS NULL) FROM symbol_fundamental_snapshot"
print("SQL(nulls tot_share,bvps,pb,mcap):", q, "->", op.execute(q).fetchone())
print("   sample:", op.execute("SELECT * FROM symbol_fundamental_snapshot LIMIT 2").fetchall())

print("\n### Q24 fundamentals visible at each run's END date (point-in-time)")
q="""SELECT r.id, r.start_date, r.end_date,
 (SELECT COUNT(DISTINCT s.symbol) FROM symbol_fundamental_snapshot s
    WHERE s.as_of <= r.end_date AND substr(s.available_at,1,10) <= r.end_date) AS visible_at_end,
 (SELECT COUNT(DISTINCT s.symbol) FROM symbol_fundamental_snapshot s
    WHERE s.as_of <= r.start_date AND substr(s.available_at,1,10) <= r.start_date) AS visible_at_start
FROM historical_backtest_runs r GROUP BY r.start_date, r.end_date ORDER BY r.id"""
print("SQL:", q.replace("\n"," "))
for r in op.execute(q): print("   ", r)

print("\n### Q25 stock_profiles: dates and point-in-time-ness")
q="SELECT dataset_name, source_file, COUNT(*) n, COUNT(DISTINCT symbol) syms FROM stock_profiles GROUP BY dataset_name, source_file ORDER BY 3 DESC"
print("SQL:", q)
for r in op.execute(q): print("   ", r)
q="SELECT MIN(main_entry_date), MAX(main_entry_date), MIN(launch_date), MAX(launch_date), SUM(main_entry_date IS NULL), SUM(launch_date IS NULL) FROM stock_profiles"
print("SQL:", q, "->", op.execute(q).fetchone())
print("   columns:", [d[1] for d in op.execute("PRAGMA table_info(stock_profiles)")])
r=op.execute("SELECT symbol,name,current_price,pct_change,main_entry_date,launch_date,dataset_name,source_file,substr(raw_json,1,400) FROM stock_profiles LIMIT 3").fetchall()
for x in r: print("   sample:", x)
q="SELECT COUNT(DISTINCT symbol) FROM stock_profiles"
print("SQL:", q, "->", op.execute(q).fetchone()[0])
op.close()
