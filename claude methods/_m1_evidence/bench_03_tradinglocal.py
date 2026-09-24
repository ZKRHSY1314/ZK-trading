# -*- coding: utf-8 -*-
import sqlite3, re, sys
sys.stdout.reconfigure(encoding="utf-8")
TL = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
t = ro(TL)

print("### H. trading_local.global_market_bars — what is actually in it? (416 rows)")
q = "SELECT asset_class, symbol, COUNT(*) n, MIN(bar_time), MAX(bar_time), source FROM global_market_bars GROUP BY asset_class,symbol,source ORDER BY n DESC"
print("  SQL:", q)
for r in t.execute(q).fetchall(): print("      ", r)

print("\n### I. trading_local.daily_bar_cache — index-shaped symbols? (the store the backtest ACTUALLY reads)")
dsyms = [r[0] for r in t.execute("SELECT DISTINCT symbol FROM daily_bar_cache").fetchall()]
print("      distinct symbols:", len(dsyms))
stock_re = re.compile(r"^(SH6[0-9]{5}|SZ(00|30)[0-9]{4}|BJ[0-9]{6})$")
idx_re   = re.compile(r"^(SH(000|950)[0-9]{3}|SZ399[0-9]{3}|BJ899[0-9]{3})$")
nonstock = [s for s in dsyms if not stock_re.match(s)]
idxs     = [s for s in dsyms if idx_re.match(s)]
print("      index-shaped:", idxs)
print("      NOT stock-shaped:", len(nonstock), nonstock[:40])

print("\n### J. daily_bar_cache index bars inside research window 2023-09-04..2026-09-04")
q = ("SELECT symbol, COUNT(*) , MIN(trade_date), MAX(trade_date) FROM daily_bar_cache "
     "WHERE (symbol LIKE 'SH000%' OR symbol LIKE 'SZ399%' OR symbol LIKE 'BJ899%' OR symbol LIKE 'SH950%') "
     "AND trade_date BETWEEN '2023-09-04' AND '2026-09-04' GROUP BY symbol ORDER BY 2 DESC LIMIT 40")
print("  SQL:", q)
rows = t.execute(q).fetchall()
print("      rows:", len(rows))
for r in rows: print("      ", r)

print("\n### K. Is market-cap / free-float available anywhere for a cap-weighted composite?")
cols = [r[1] for r in t.execute("PRAGMA table_info(symbol_fundamental_snapshot)").fetchall()]
print("      symbol_fundamental_snapshot cols:", cols)
cap = [c for c in cols if re.search(r"cap|mv|market_value|float|share", c, re.I)]
print("      cap-like cols:", cap)
for cc in cap:
    q = f"SELECT COUNT(*), COUNT({cc}) FROM symbol_fundamental_snapshot"
    print(f"      SQL: {q} ->", t.execute(q).fetchone())

print("\n### L. Does any OTHER trading_local table carry an index/benchmark series?")
for name, in t.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
    cols = [r[1] for r in t.execute(f"PRAGMA table_info('{name}')").fetchall()]
    if any(re.search(r"^(benchmark|index_|idx_)|benchmark", c, re.I) for c in cols):
        n = t.execute(f"SELECT COUNT(*) FROM '{name}'").fetchone()[0]
        print(f"      {name} rows={n} cols={[c for c in cols if re.search('benchmark|index_|idx_', c, re.I)]}")
t.close()
