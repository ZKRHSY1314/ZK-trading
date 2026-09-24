import sqlite3, sys
c = sqlite3.connect("file:D:/codex-A股交易/trading_local.sqlite3?mode=ro", uri=True)
sql = open(r"D:\codex-A股交易\claude methods\_m1_evidence\benchref_v08_decisive.sql", encoding="utf-8").read()
cols = ["store_first_day","first_usable_session","usable_sessions","usable_with_bench",
        "missing_at_thr100","interior_gaps","bench_days_before_20240618"]
row = c.execute(sql).fetchone()
for k,v in zip(cols,row): print(f"   {k:28s} = {v}"); sys.stdout.flush()
