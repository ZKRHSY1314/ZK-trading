import sqlite3, json, collections, sys

OPS = r"D:/codex-A股交易/trading_local.sqlite3"
RES = r"D:/codex-A股交易/market_history.sqlite3"

def ro(p):
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

print("="*78)
print("Q1  Which DBs contain a table named like forecast_evaluations?")
print("="*78)
for name, p in (("trading_local", OPS), ("market_history", RES)):
    c = ro(p)
    rows = c.execute(
        "SELECT type,name FROM sqlite_master WHERE name LIKE '%forecast%' ORDER BY name"
    ).fetchall()
    print(f"\n-- {name} --  SQL: SELECT type,name FROM sqlite_master WHERE name LIKE '%forecast%'")
    for t, n in rows:
        cnt = ""
        if t == "table":
            try:
                cnt = c.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0]
            except Exception as e:
                cnt = f"ERR {e}"
        print(f"   {t:6s} {n:45s} {cnt}")
    c.close()

print()
print("="*78)
print("Q2  Full DDL + column list of trading_local.forecast_evaluations")
print("="*78)
c = ro(OPS)
ddl = c.execute("SELECT sql FROM sqlite_master WHERE name='forecast_evaluations'").fetchone()
print("SQL: SELECT sql FROM sqlite_master WHERE name='forecast_evaluations'")
print(ddl[0] if ddl else "TABLE ABSENT")
print("\nSQL: PRAGMA table_info(forecast_evaluations)")
cols = c.execute("PRAGMA table_info(forecast_evaluations)").fetchall()
for cid, cname, ctype, notnull, dflt, pk in cols:
    print(f"   {cid:2d} {cname:32s} {ctype:10s} notnull={notnull} default={dflt!r} pk={pk}")
colnames = [r[1] for r in cols]

print("\nSQL: SELECT COUNT(*) FROM forecast_evaluations")
total = c.execute("SELECT COUNT(*) FROM forecast_evaluations").fetchone()[0]
print("   total rows =", total)

# per-column non-null census -- an independent way to find ANY provenance column
print("\nQ3  Non-null / distinct census for EVERY column (independent of their SQL)")
sel = ", ".join(f'COUNT("{n}")' for n in colnames)
counts = c.execute(f"SELECT {sel} FROM forecast_evaluations").fetchone()
sel2 = ", ".join(f'COUNT(DISTINCT "{n}")' for n in colnames)
dist = c.execute(f"SELECT {sel2} FROM forecast_evaluations").fetchone()
print(f"   SQL: SELECT {sel} FROM forecast_evaluations")
print(f"   {'column':32s} {'non_null':>9s} {'distinct':>9s}  sample")
for n, nn, dd in zip(colnames, counts, dist):
    smp = c.execute(
        f'SELECT "{n}" FROM forecast_evaluations WHERE "{n}" IS NOT NULL LIMIT 1'
    ).fetchone()
    s = smp[0] if smp else None
    if isinstance(s, str) and len(s) > 60:
        s = s[:60] + "..."
    print(f"   {n:32s} {nn:9d} {dd:9d}  {s!r}")
c.close()
