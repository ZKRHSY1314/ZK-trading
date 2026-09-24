import sqlite3
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

W0, W1 = "2023-09-04", "2026-09-04"

print("### A. RAW FLOOR, NO FILTERS AT ALL (no length(), no WHERE) ###")
for db,(path,tbl) in {"trading_local.daily_bar_cache":(TL,"daily_bar_cache"),
                      "market_history.daily_bars":(MH,"daily_bars")}.items():
    c = ro(path)
    q = f"SELECT COUNT(*), MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date), SUM(trade_date IS NULL) FROM {tbl}"
    print(db, "->", c.execute(q).fetchone())
    print("   SQL:", q)
    c.close()

print()
print("### B. FORMAT-BUG HUNT: distribution of length(trade_date) and typeof() ###")
for db,(path,tbl) in {"trading_local.daily_bar_cache":(TL,"daily_bar_cache"),
                      "market_history.daily_bars":(MH,"daily_bars")}.items():
    c = ro(path)
    q = (f"SELECT typeof(trade_date), length(trade_date), COUNT(*), MIN(trade_date), MAX(trade_date) "
         f"FROM {tbl} GROUP BY 1,2 ORDER BY 3 DESC")
    print(db)
    for r in c.execute(q).fetchall():
        print("   typeof=%-8s len=%-5s n=%-10d min=%s max=%s" % r)
    print("   SQL:", q)
    c.close()

print()
print("### C. ORDER-BY floor (immune to MIN() over mixed types) - 5 smallest distinct dates ###")
for db,(path,tbl) in {"trading_local.daily_bar_cache":(TL,"daily_bar_cache"),
                      "market_history.daily_bars":(MH,"daily_bars")}.items():
    c = ro(path)
    q = f"SELECT DISTINCT trade_date FROM {tbl} ORDER BY trade_date ASC LIMIT 5"
    print(db, "->", [r[0] for r in c.execute(q).fetchall()])
    # also numeric-cast ordering in case of '20230904' style
    q2 = f"SELECT DISTINCT trade_date FROM {tbl} ORDER BY replace(trade_date,'-','') ASC LIMIT 5"
    print("   (normalized ordering) ->", [r[0] for r in c.execute(q2).fetchall()])
    c.close()

print()
print("### D. DATE-TYPED comparison, not string comparison (julianday) ###")
for db,(path,tbl) in {"trading_local.daily_bar_cache":(TL,"daily_bar_cache"),
                      "market_history.daily_bars":(MH,"daily_bars")}.items():
    c = ro(path)
    q = (f"SELECT COUNT(*) FROM {tbl} WHERE julianday(trade_date) < julianday('2024-04-09')")
    q2= (f"SELECT COUNT(*) FROM {tbl} WHERE julianday(trade_date) IS NULL")
    print(db, "rows with julianday(trade_date)<2024-04-09 ->", c.execute(q).fetchone()[0],
          "| unparseable-as-date rows ->", c.execute(q2).fetchone()[0])
    c.close()
