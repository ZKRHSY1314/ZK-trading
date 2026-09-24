import sqlite3, os, glob
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

print("### L. don't overstate 5167: how many instruments actually have a delist_date? ###")
c = ro(MH)
q="SELECT COUNT(*), SUM(delist_date IS NULL), SUM(delist_date IS NOT NULL) FROM instruments"
print("  instruments total / delist NULL / delist set:", c.execute(q).fetchone())
q2=("SELECT COUNT(*) FROM instruments WHERE list_date<'2023-09-04' AND asset_type IS NOT NULL "
    "AND exchange IN ('SH','SZ','BJ')")
print("  pre-window-listed, NON-INDEX exchanges (SH/SZ/BJ) only:", c.execute(q2).fetchone()[0])
print("  SQL:", q2)
q3="SELECT exchange, COUNT(*) FROM instruments WHERE list_date<'2023-09-04' GROUP BY 1 ORDER BY 2 DESC"
print("  breakdown of the 5167 by exchange:", c.execute(q3).fetchall())
c.close()

print()
print("### M. stocks-only floor (exclude indices) - does excluding indices change the floor? ###")
c = ro(MH)
q=("SELECT MIN(b.trade_date), COUNT(*) FROM daily_bars b JOIN instruments i USING(symbol) "
   "WHERE i.exchange IN ('SH','SZ','BJ')")
print("  non-index bars: min_trade_date, n =", c.execute(q).fetchone())
q2=("SELECT MIN(b.trade_date) FROM daily_bars b JOIN instruments i USING(symbol) WHERE i.exchange='INDEX'")
print("  index bars min_trade_date =", c.execute(q2).fetchone()[0])
c.close()

print()
print("### N. any OTHER sqlite on disk holding pre-floor bars? ###")
seen=set()
for pat in (r"D:/codex-A股交易/*.sqlite3", r"D:/codex-A股交易/backend/*.sqlite3",
            r"D:/codex-A股交易/data/*.sqlite3", r"D:/codex-A股交易/logs/*.sqlite3",
            r"D:/codex-A股交易/backend/**/*.sqlite3"):
    for f in glob.glob(pat, recursive=True):
        f=os.path.abspath(f)
        if f in seen: continue
        seen.add(f)
        try:
            c=ro(f)
            tabs=[r[0] for r in c.execute(
              "SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%daily_bar%' OR name LIKE '%bars%')").fetchall()]
            for t in tabs:
                mn,n = c.execute(f"SELECT MIN(trade_date),COUNT(*) FROM {t}").fetchone()
                flag = "  <<< PRE-FLOOR DATA" if (mn and mn < '2024-04-09') else ""
                print(f"  {os.path.basename(f):32s} {t:22s} min={mn} n={n}{flag}")
            c.close()
        except Exception as e:
            print(f"  {os.path.basename(f):32s} ERR {type(e).__name__}")
