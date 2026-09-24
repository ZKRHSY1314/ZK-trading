# -*- coding: utf-8 -*-
"""ADVERSARIAL independent re-derivation of 3-year window coverage. READ-ONLY."""
import sqlite3, pathlib, sys, collections, datetime, statistics

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
OP = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"
W0, W1 = "2023-09-04", "2026-09-04"

def ro(p): return "file:" + pathlib.Path(p).as_posix() + "?mode=ro"

op = sqlite3.connect(ro(OP), uri=True)
mh = sqlite3.connect(ro(MH), uri=True)
def Q(c, sql, p=()): return list(c.execute(sql, p))

print("="*100)
print("STEP 0 -- SANITY: date typing, symbol typing, join integrity")
print("="*100)
# SQL: are trade_date values TEXT and 10 chars? A non-TEXT type would break BETWEEN string compare.
sql = """SELECT typeof(trade_date), length(trade_date), COUNT(*) FROM daily_bar_cache GROUP BY 1,2 ORDER BY 3 DESC"""
print("[SQL-A] "+sql)
for r in Q(op, sql): print("   typeof=%-8s len=%-4s rows=%d" % r)

sql = """SELECT typeof(symbol), COUNT(*), COUNT(DISTINCT symbol) FROM daily_bar_cache GROUP BY 1"""
print("[SQL-B] "+sql)
for r in Q(op, sql): print("   typeof=%-8s rows=%d distinct=%d" % r)

# distinct symbols in cache overall and inside window
sql = """SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache"""
print("[SQL-C] "+sql, "->", Q(op, sql)[0][0])
sql = """SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE trade_date>=? AND trade_date<=?"""
print("[SQL-D] "+sql, "->", Q(op, sql, (W0,W1))[0][0])

print()
print("="*100)
print("STEP 1 -- INSTRUMENT UNIVERSE (market_history.instruments), my own classification")
print("="*100)
sql = """SELECT asset_type, exchange, status, COUNT(*) FROM instruments GROUP BY 1,2,3 ORDER BY 4 DESC"""
print("[SQL-E] "+sql)
for r in Q(mh, sql)[:25]: print("   asset=%-10s exch=%-7s status=%-10s n=%d" % r)

sql = """SELECT COUNT(*) FROM instruments WHERE asset_type='stock' AND exchange IN ('SH','SZ','BJ')"""
n_stock = Q(mh, sql)[0][0]
print("[SQL-F] "+sql, "->", n_stock)

# ADVERSARIAL: any 'stock' rows that are really indices by symbol prefix?
sql = """SELECT substr(symbol,1,3) p, COUNT(*) FROM instruments
         WHERE asset_type='stock' AND exchange IN ('SH','SZ','BJ') GROUP BY 1 ORDER BY 2 DESC"""
print("[SQL-G] "+sql)
print("   prefixes:", ", ".join("%s:%d"%r for r in Q(mh, sql)))

sql = """SELECT symbol,name,exchange,asset_type,board,list_date,delist_date,status FROM instruments
         WHERE asset_type='stock' AND exchange IN ('SH','SZ','BJ')
           AND (symbol GLOB '00000[0-9]' OR symbol GLOB '399*' OR symbol GLOB '000300' OR symbol GLOB '88*')"""
try:
    rows = Q(mh, sql)
    print("[SQL-H] index-looking symbols classified as stock:", len(rows))
    for r in rows[:12]: print("   ", r)
except Exception as e:
    print("[SQL-H] failed:", e)

print()
print("="*100)
print("STEP 2 -- THREE INDEPENDENT TRADING-CALENDAR SPINES")
print("="*100)
# Spine-1: from INDEX instruments only (indices print every session; fully independent of stock rows)
sql = """SELECT DISTINCT d.trade_date FROM daily_bar_cache d
         WHERE d.symbol IN (SELECT symbol FROM inst_index)
           AND d.trade_date>=? AND d.trade_date<=?"""
idx_syms = [r[0] for r in Q(mh, "SELECT symbol FROM instruments WHERE exchange='INDEX'")]
print("   INDEX instruments in market_history:", len(idx_syms))
spine_idx = set()
if idx_syms:
    ph = ",".join("?"*len(idx_syms))
    s = "SELECT DISTINCT trade_date FROM daily_bar_cache WHERE symbol IN (%s) AND trade_date>=? AND trade_date<=?" % ph
    spine_idx = {r[0] for r in Q(op, s, tuple(idx_syms)+(W0,W1))}
print("[SPINE-1 index-only, trading_local] sessions =", len(spine_idx))

# Spine-2: market_history.daily_bars, ALL symbols, any adjustment_mode
sql2 = "SELECT DISTINCT trade_date FROM daily_bars WHERE trade_date>=? AND trade_date<=?"
spine_mh = {r[0] for r in Q(mh, sql2, (W0,W1))}
print("[SPINE-2 market_history.daily_bars all symbols] "+sql2, "-> sessions =", len(spine_mh))

# Spine-3: trading_local cache, ALL symbols
sql3 = "SELECT DISTINCT trade_date FROM daily_bar_cache WHERE trade_date>=? AND trade_date<=?"
spine_cache = {r[0] for r in Q(op, sql3, (W0,W1))}
print("[SPINE-3 trading_local all symbols] "+sql3, "-> sessions =", len(spine_cache))

# Spine-4: calendar-theoretic upper bound = weekdays in window
d0 = datetime.date.fromisoformat(W0); d1 = datetime.date.fromisoformat(W1)
wd = sum(1 for i in range((d1-d0).days+1) if (d0+datetime.timedelta(days=i)).weekday() < 5)
print("[SPINE-4 weekday upper bound %s..%s] = %d weekdays (A-share reality ~ minus 3-4%% holidays)" % (W0,W1,wd))

union = spine_cache | spine_mh | spine_idx
print("UNION of all observed spines =", len(union))
print("cache-only:", len(spine_cache-spine_mh), " mh-only:", len(spine_mh-spine_cache))
su = sorted(union)
print("first=%s last=%s" % (su[0], su[-1]))
