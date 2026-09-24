import sqlite3
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True); c.row_factory = sqlite3.Row; return c
mh, tl = ro(MH), ro(TL)
def q(c,s,a=()): return c.execute(s,a).fetchall()
def p(t): print("\n"+"="*78+"\n"+t+"\n"+"="*78)

p("J. trading_local.daily_bar_cache extents  (THE store the backtest reads)")
print("SQL: SELECT COUNT(*),COUNT(DISTINCT symbol),MIN(trade_date),MAX(trade_date) FROM daily_bar_cache")
for r in q(tl,"SELECT COUNT(*) rows, COUNT(DISTINCT symbol) syms, MIN(trade_date) mn, MAX(trade_date) mx FROM daily_bar_cache"):
    print("   ->", dict(r))
print("SQL: SELECT source, adjustment_mode, COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date), MAX(trade_date) FROM daily_bar_cache GROUP BY 1,2")
for r in q(tl,"SELECT COALESCE(source,'<null>') src, COALESCE(adjustment_mode,'<null>') am, COUNT(*) n, COUNT(DISTINCT symbol) s, MIN(trade_date) mn, MAX(trade_date) mx FROM daily_bar_cache GROUP BY 1,2 ORDER BY n DESC"):
    print("   ->", dict(r))

p("K. daily_bar_cache: rows inside research window BEFORE 2024-04-09")
print("SQL: SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date), MAX(trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2024-04-08'")
for r in q(tl,"SELECT COUNT(*) rows, COUNT(DISTINCT symbol) syms, MIN(trade_date) mn, MAX(trade_date) mx FROM daily_bar_cache WHERE trade_date>='2023-09-04' AND trade_date<='2024-04-08'"):
    print("   ->", dict(r))
print("SQL: monthly breadth in daily_bar_cache over the full research window")
for r in q(tl,"SELECT substr(trade_date,1,7) ym, COUNT(DISTINCT symbol) syms, COUNT(DISTINCT trade_date) days, COUNT(*) rows FROM daily_bar_cache WHERE trade_date>='2023-09-04' AND trade_date<='2026-09-04' GROUP BY 1 ORDER BY 1 LIMIT 40"):
    print("   ->", dict(r))

p("L. daily_bar_cache bar-count histogram (top 12) + symbols NOT in market_history")
print("SQL: WITH c AS (SELECT symbol, COUNT(DISTINCT trade_date) n FROM daily_bar_cache GROUP BY symbol) SELECT n, COUNT(*) FROM c GROUP BY n ORDER BY COUNT(*) DESC LIMIT 12")
for r in q(tl,"WITH c AS (SELECT symbol, COUNT(DISTINCT trade_date) n FROM daily_bar_cache GROUP BY symbol) SELECT n, COUNT(*) syms FROM c GROUP BY n ORDER BY syms DESC LIMIT 12"):
    print("   ->", dict(r))

p("M. Symbol-set diff between the two stores (attach-free, via python sets)")
a = {r[0] for r in q(tl,"SELECT DISTINCT symbol FROM daily_bar_cache")}
b = {r[0] for r in q(mh,"SELECT DISTINCT symbol FROM daily_bars")}
inst = {r[0] for r in q(mh,"SELECT symbol FROM instruments")}
print(f"   daily_bar_cache symbols = {len(a)}; market_history.daily_bars symbols = {len(b)}; instruments = {len(inst)}")
print(f"   cache-only = {len(a-b)}  history-only = {len(b-a)}  both = {len(a&b)}")
print(f"   cache symbols with NO instruments row = {len(a-inst)}   sample: {sorted(a-inst)[:15]}")

p("N. The 186-bar cluster: who are they? (market_history)")
print("SQL: WITH c AS (SELECT symbol, COUNT(DISTINCT trade_date) n, MIN(trade_date) ft FROM daily_bars GROUP BY symbol) SELECT i.exchange, c.ft, COUNT(*) FROM c JOIN instruments i USING(symbol) WHERE c.n BETWEEN 180 AND 190 GROUP BY 1,2 ORDER BY 3 DESC LIMIT 8")
for r in q(mh,"WITH c AS (SELECT symbol, COUNT(DISTINCT trade_date) n, MIN(trade_date) ft FROM daily_bars GROUP BY symbol) SELECT i.exchange ex, c.ft, COUNT(*) syms FROM c JOIN instruments i ON i.symbol=c.symbol WHERE c.n BETWEEN 180 AND 190 GROUP BY 1,2 ORDER BY syms DESC LIMIT 8"):
    print("   ->", dict(r))

p("O. Survivorship evidence availability: delist_date / status in instruments")
print("SQL: SELECT COUNT(*), SUM(delist_date IS NULL OR delist_date=''), COUNT(DISTINCT status) FROM instruments")
for r in q(mh,"SELECT COUNT(*) n, SUM(CASE WHEN delist_date IS NULL OR delist_date='' THEN 1 ELSE 0 END) null_delist, MIN(list_date) min_list, MAX(list_date) max_list, SUM(CASE WHEN list_date IS NULL OR list_date='' THEN 1 ELSE 0 END) null_list FROM instruments"):
    print("   ->", dict(r))
print("SQL: universe_snapshots as-of dates and member counts")
for r in q(mh,"SELECT * FROM universe_snapshots ORDER BY rowid LIMIT 12"):
    print("   ->", {k: (str(r[k])[:110] if r[k] is not None else None) for k in r.keys()})

p("P. Does ANY table in either DB hold a bar dated inside 2023-09-04..2024-04-08?")
for name, conn in (("market_history", mh), ("trading_local", tl)):
    tabs = [r[0] for r in q(conn,"SELECT name FROM sqlite_master WHERE type='table'")]
    for t in tabs:
        cols = [c[1] for c in q(conn,f'PRAGMA table_info("{t}")')]
        dc = next((c for c in cols if c in ("trade_date","date","bar_date","dt")), None)
        if not dc: continue
        try:
            r = q(conn, f'SELECT COUNT(*) n, MIN("{dc}") mn, MAX("{dc}") mx FROM "{t}" WHERE "{dc}">=\'2023-09-04\' AND "{dc}"<=\'2024-04-08\'')[0]
        except Exception as e:
            continue
        if r["n"]:
            print(f"   {name}.{t} [{dc}]: rows={r['n']} range={r['mn']}..{r['mx']}")
