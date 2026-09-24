import sqlite3
MH = "D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)
q = lambda s,a=(): c.execute(s,a).fetchall()

print("### K. global span + distinct trade dates in daily_bars")
print("   ", q("SELECT MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date) FROM daily_bars")[0])
print("   distinct dates from 2024-06-24 onward:",
      q("SELECT COUNT(DISTINCT trade_date) FROM daily_bars WHERE trade_date>='2024-06-24'")[0])
print("   distinct dates 2024-04-09..2024-06-21:",
      q("SELECT COUNT(DISTINCT trade_date) FROM daily_bars WHERE trade_date<='2024-06-21'")[0])

print("\n### L. FIRST-BAR-DATE distribution (top 12) -- distinct symbols")
for r in q("""SELECT ft, COUNT(*) FROM (SELECT symbol, MIN(trade_date) ft FROM daily_bars GROUP BY symbol)
              GROUP BY ft ORDER BY COUNT(*) DESC LIMIT 12"""):
    print("   first_bar=%s  syms=%s"%r)

print("\n### M. cumulative: symbols whose FIRST bar <= date, at key dates")
for d in ('2024-04-09','2024-04-30','2024-06-21','2024-06-24','2024-12-31','2026-09-03'):
    print("   <=",d, q("SELECT COUNT(*) FROM (SELECT symbol, MIN(trade_date) ft FROM daily_bars GROUP BY symbol) WHERE ft<=?",(d,))[0][0])

print("\n### N. breadth (distinct symbols with a bar) on specific dates")
for d in ('2024-04-09','2024-06-20','2024-06-21','2024-06-24','2024-06-25','2025-01-02','2026-09-03'):
    print("   ",d, q("SELECT COUNT(DISTINCT symbol) FROM daily_bars WHERE trade_date=?",(d,))[0][0])

print("\n### O. denominators -- population at risk")
tot = q("SELECT COUNT(DISTINCT symbol) FROM daily_bars")[0][0]
print("   bar-carrying symbols:", tot)
for cut in ('2024-04-09','2024-04-30','2024-06-24'):
    a = q("""SELECT COUNT(*) FROM (SELECT DISTINCT symbol s FROM daily_bars) x
             JOIN instruments i ON i.symbol=x.s WHERE i.list_date IS NOT NULL AND i.list_date < ?""",(cut,))[0][0]
    print("   bar-carrying symbols listed BEFORE %s : %d"%(cut,a))
print("   bar-carrying symbols listed before window start 2023-09-04:",
      q("""SELECT COUNT(*) FROM (SELECT DISTINCT symbol s FROM daily_bars) x JOIN instruments i ON i.symbol=x.s
           WHERE i.list_date IS NOT NULL AND i.list_date < '2023-09-04'""")[0][0])
print("   bar-carrying symbols with NULL list_date:",
      q("""SELECT COUNT(*) FROM (SELECT DISTINCT symbol s FROM daily_bars) x JOIN instruments i ON i.symbol=x.s
           WHERE i.list_date IS NULL""")[0][0])

print("\n### P. THEIR headline predicate, my own reconstruction")
n = q("""SELECT COUNT(*) FROM (SELECT symbol, MIN(trade_date) ft, COUNT(DISTINCT trade_date) nd FROM daily_bars GROUP BY symbol) f
         JOIN instruments i ON i.symbol=f.symbol
         WHERE i.list_date < '2024-04-09' AND f.ft > '2024-04-30' AND f.nd >= 480""")[0][0]
print("   listed<2024-04-09 AND first_bar>2024-04-30 AND >=480 distinct dates:", n)
n2 = q("""SELECT COUNT(*) FROM (SELECT symbol, MIN(trade_date) ft FROM daily_bars GROUP BY symbol) f
          JOIN instruments i ON i.symbol=f.symbol
          WHERE i.list_date < '2024-04-09' AND f.ft > '2024-04-30'""")[0][0]
print("   same WITHOUT the >=480 filter:", n2)

print("\n### Q. STRICTER: symbols whose first bar is LATER than their own list_date+grace, i.e. truly truncated")
n3 = q("""SELECT COUNT(*) FROM (SELECT symbol, MIN(trade_date) ft FROM daily_bars GROUP BY symbol) f
          JOIN instruments i ON i.symbol=f.symbol
          WHERE i.list_date IS NOT NULL AND i.list_date < '2024-04-09'""")[0][0]
print("   ALL bar-carrying symbols listed before the table's own global min (2024-04-09):", n3)
print("   of those, how many have first_bar = 2024-04-09 exactly:",
   q("""SELECT COUNT(*) FROM (SELECT symbol, MIN(trade_date) ft FROM daily_bars GROUP BY symbol) f
        JOIN instruments i ON i.symbol=f.symbol
        WHERE i.list_date < '2024-04-09' AND f.ft='2024-04-09'""")[0][0])
c.close()
