import sqlite3, json
OP = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"

def ro(p):
    return sqlite3.connect(f"file:{p.replace(chr(92),'/')}?mode=ro", uri=True)

c = ro(OP)
print("=== daily_bar_cache DDL ===")
for (s,) in c.execute("SELECT sql FROM sqlite_master WHERE tbl_name='daily_bar_cache'"):
    print(s)

print("\n=== typeof/format of created_at & updated_at ===")
q = """SELECT typeof(created_at) t_c, typeof(updated_at) t_u, length(created_at) len_c,
       COUNT(*) n, MIN(created_at), MAX(created_at)
FROM daily_bar_cache GROUP BY 1,2,3 ORDER BY n DESC"""
print(q)
for r in c.execute(q): print(r)

print("\n=== NULL created_at? ===")
q2 = "SELECT SUM(created_at IS NULL) null_created, SUM(updated_at IS NULL) null_updated, COUNT(*) total FROM daily_bar_cache"
print(q2)
print(list(c.execute(q2)))

print("\n=== trade_date extremes and format anomalies ===")
q3 = """SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM daily_bar_cache"""
print(q3); print(list(c.execute(q3)))
q4 = """SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"""
print(q4); print(list(c.execute(q4)))
q4b = """SELECT trade_date, COUNT(*) FROM daily_bar_cache WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' GROUP BY 1"""
for r in c.execute(q4b): print(" bad:", r)

print("\n=== rows OUTSIDE the research window (both sides) ===")
q5 = """SELECT SUM(trade_date < '2023-09-04') before_window,
              SUM(trade_date > '2026-09-04') after_window,
              SUM(trade_date BETWEEN '2023-09-04' AND '2026-09-04') in_window,
              COUNT(*) total
FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"""
print(q5); print(list(c.execute(q5)))

print("\n=== created_at == updated_at ? (bulk-load signature) ===")
q6 = """SELECT CASE WHEN created_at = updated_at THEN 'identical' ELSE 'differ' END k,
       COUNT(*) n, MIN(created_at), MAX(created_at), MIN(updated_at), MAX(updated_at)
FROM daily_bar_cache GROUP BY 1"""
print(q6)
for r in c.execute(q6): print(r)

print("\n=== created_at by DAY (top 25) - is this a bulk load? ===")
q7 = """SELECT substr(created_at,1,10) d, COUNT(*) n, MIN(trade_date), MAX(trade_date),
        COUNT(DISTINCT symbol) syms
FROM daily_bar_cache GROUP BY 1 ORDER BY n DESC LIMIT 25"""
print(q7)
for r in c.execute(q7): print(r)
c.close()
