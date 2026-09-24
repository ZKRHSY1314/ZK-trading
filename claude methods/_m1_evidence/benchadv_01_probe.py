# -*- coding: utf-8 -*-
import sqlite3, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"

def ro(p):
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

def q(c, sql, args=()):
    cur = c.execute(sql, args)
    return cur.fetchall()

print("="*100)
print("SECTION A: FULL TABLE INVENTORY OF market_history (is there a separate index/benchmark table?)")
print("="*100)
mh = ro(MH)
tabs = q(mh, "SELECT name, type FROM sqlite_master WHERE type IN ('table','view') ORDER BY name")
for name, typ in tabs:
    try:
        n = q(mh, f'SELECT COUNT(*) FROM "{name}"')[0][0]
    except Exception as e:
        n = f"ERR {e}"
    print(f"  {typ:5s} {name:45s} rows={n}")

print()
print("SECTION B: any table/column in EITHER db whose NAME mentions index/benchmark/bench/idx")
print("-"*100)
for label, path in (("market_history", MH), ("trading_local", TL)):
    c = ro(path)
    rows = q(c, "SELECT name FROM sqlite_master WHERE type IN ('table','view')")
    for (t,) in rows:
        lt = t.lower()
        if any(k in lt for k in ("index","bench","idx","csi","hs300","market_ret")):
            if lt.startswith("sqlite_autoindex") or lt.startswith("ix_") or lt.startswith("idx_"):
                continue
            try:
                n = q(c, f'SELECT COUNT(*) FROM "{t}"')[0][0]
            except Exception as e:
                n = f"ERR {e}"
            print(f"  TABLE {label}.{t}  rows={n}")
        try:
            cols = q(c, f'PRAGMA table_info("{t}")')
        except Exception:
            continue
        hits = [cc[1] for cc in cols if any(k in cc[1].lower() for k in ("benchmark","index_","_index","idx_sym","hs300","csi"))]
        if hits:
            print(f"  COLS  {label}.{t}: {hits}")
    c.close()
