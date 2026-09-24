import sqlite3
OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

c = ro(OP)
print("### daily_bar_cache DDL")
print(c.execute("SELECT sql FROM sqlite_master WHERE name='daily_bar_cache'").fetchone()[0])
print()
print("### forecast_decisions DDL")
print(c.execute("SELECT sql FROM sqlite_master WHERE name='forecast_decisions'").fetchone()[0])
print()
print("### forecast_outcomes DDL")
print(c.execute("SELECT sql FROM sqlite_master WHERE name='forecast_outcomes'").fetchone()[0])
print()
print("### forecast_decision_days DDL")
print(c.execute("SELECT sql FROM sqlite_master WHERE name='forecast_decision_days'").fetchone()[0])
c.close()

m = ro(MH)
print()
print("### daily_bars DDL")
print(m.execute("SELECT sql FROM sqlite_master WHERE name='daily_bars'").fetchone()[0])
print()
print("### ingest_runs DDL")
print(m.execute("SELECT sql FROM sqlite_master WHERE name='ingest_runs'").fetchone()[0])
m.close()
