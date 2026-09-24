# -*- coding: utf-8 -*-
import sqlite3
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
mh = ro(MH); mh.row_factory = sqlite3.Row
tl = ro(TL); tl.row_factory = sqlite3.Row

W0, W1 = '2023-09-04', '2026-09-04'

print("### G. bar-data extent per DB (establish the 'still trading' reference date)")
print("MH daily_bars:", dict(mh.execute(
  "SELECT MIN(trade_date) AS mn, MAX(trade_date) AS mx, COUNT(DISTINCT symbol) AS syms FROM daily_bars").fetchone()))
print("TL daily_bar_cache:", dict(tl.execute(
  "SELECT MIN(trade_date) AS mn, MAX(trade_date) AS mx, COUNT(DISTINCT symbol) AS syms FROM daily_bar_cache").fetchone()))

print("\n### H. the 5 'inactive' names: do they still have RECENT bars? (false-inactivation test)")
for sym in ('BJ920305','SH605081','SZ000004','SZ002808','SZ002898'):
    a = mh.execute("SELECT COUNT(*) n, MIN(trade_date) mn, MAX(trade_date) mx FROM daily_bars WHERE symbol=?", (sym,)).fetchone()
    # trading_local uses bare 6-digit codes
    bare = sym[2:]
    b = tl.execute("SELECT COUNT(*) n, MIN(trade_date) mn, MAX(trade_date) mx FROM daily_bar_cache WHERE symbol=?", (bare,)).fetchone()
    print(f"{sym}: MH bars={dict(a)}  TL[{bare}] bars={dict(b)}")

print("\n### I. TL daily_bar_cache: securities whose LAST bar falls INSIDE the window")
print("    (traded, then ceased -> candidate delisting/long-suspension events)")
rows = tl.execute(f"""
    SELECT last_bar_month, COUNT(*) AS n_symbols FROM (
        SELECT symbol, SUBSTR(MAX(trade_date),1,7) AS last_bar_month
        FROM daily_bar_cache
        WHERE LENGTH(symbol)=6 AND symbol GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]'
        GROUP BY symbol
        HAVING MAX(trade_date) BETWEEN '{W0}' AND '2026-08-01'
    ) GROUP BY last_bar_month ORDER BY last_bar_month
""").fetchall()
tot = sum(r['n_symbols'] for r in rows)
print(f"    TOTAL symbols whose last bar is in [{W0} .. 2026-08-01]: {tot}")
for r in rows: print("     ", r['last_bar_month'], r['n_symbols'])

print("\n### J. how many of those ceased symbols does instruments call 'active'?")
ceased = [r[0] for r in tl.execute(f"""
    SELECT symbol FROM daily_bar_cache
    WHERE LENGTH(symbol)=6 AND symbol GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]'
    GROUP BY symbol HAVING MAX(trade_date) BETWEEN '{W0}' AND '2026-08-01'
""").fetchall()]
inst = {}
for r in mh.execute("SELECT symbol, status FROM instruments").fetchall():
    inst[str(r['symbol'])[2:]] = r['status']
from collections import Counter
cnt = Counter(inst.get(s, '<ABSENT from instruments>') for s in ceased)
for k,v in cnt.most_common(): print(f"     {k}: {v}")
mh.close(); tl.close()
