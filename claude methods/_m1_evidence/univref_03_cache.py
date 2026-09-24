import sqlite3
TL = "D:/codex-A股交易/trading_local.sqlite3"
MH = "D:/codex-A股交易/market_history.sqlite3"
t = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
m = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)
q  = lambda s,a=(): t.execute(s,a).fetchall()
qm = lambda s,a=(): m.execute(s,a).fetchall()

print("### R. daily_bar_cache global span / symbols / dates")
print("   ", q("SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date) FROM daily_bar_cache")[0])

print("\n### S. daily_bar_cache rows and symbols INSIDE the research window 2023-09-04..2026-09-04")
print("   ", q("""SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date), MAX(trade_date)
                  FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'""")[0])
print("   rows BEFORE window start:", q("SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date) FROM daily_bar_cache WHERE trade_date<'2023-09-04'")[0])

print("\n### T. daily_bar_cache breadth by month (distinct symbols) 2023-06 .. 2024-09")
for r in q("""SELECT substr(trade_date,1,7) ym, COUNT(DISTINCT symbol), COUNT(DISTINCT trade_date)
              FROM daily_bar_cache WHERE trade_date BETWEEN '2023-06-01' AND '2024-10-01'
              GROUP BY ym ORDER BY ym"""):
    print("   %s  syms=%-6s dates=%s"%r)

print("\n### U. daily_bar_cache first-bar-date distribution (top 12)")
for r in q("""SELECT ft, COUNT(*) FROM (SELECT symbol, MIN(trade_date) ft FROM daily_bar_cache GROUP BY symbol)
              GROUP BY ft ORDER BY COUNT(*) DESC LIMIT 12"""):
    print("   first_bar=%s  syms=%s"%r)

print("\n### V. daily_bar_cache bar-count distribution (top 10)")
for r in q("""SELECT n, COUNT(*) FROM (SELECT symbol, COUNT(*) n FROM daily_bar_cache GROUP BY symbol)
              GROUP BY n ORDER BY COUNT(*) DESC LIMIT 10"""):
    print("   n=%-6s syms=%s"%r)

print("\n### W. are there INDEX/non-stock symbols in daily_bar_cache? (classify via market_history.instruments)")
cs = set(x[0] for x in q("SELECT DISTINCT symbol FROM daily_bar_cache"))
inst = dict((x[0],(x[1],x[2])) for x in qm("SELECT symbol, exchange, asset_type FROM instruments"))
from collections import Counter
cc = Counter(inst.get(s,('NOT_IN_INSTRUMENTS','-'))[0] for s in cs)
print("   ", dict(cc))
notin = sorted(s for s in cs if s not in inst)
print("   sample symbols not in market_history.instruments:", notin[:20], "... total", len(notin))

print("\n### X. symbol-set overlap between the two stores")
ms = set(x[0] for x in qm("SELECT DISTINCT symbol FROM daily_bars"))
print("   cache-only:", len(cs-ms), " mh-only:", len(ms-cs), " both:", len(cs&ms))
t.close(); m.close()
