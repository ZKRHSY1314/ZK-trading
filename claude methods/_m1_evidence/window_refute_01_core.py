# -*- coding: utf-8 -*-
import sqlite3
P_OPS = r"D:/codex-A股交易/trading_local.sqlite3"
P_HIST = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

def show(title, sql, conn, params=()):
    print("-"*90)
    print("Q:", " ".join(sql.split()))
    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception as e:
        print("   ERROR:", e); return None
    for r in rows[:40]:
        print("   ", r)
    if len(rows) > 40: print("    ... total rows", len(rows))
    return rows

ops = ro(P_OPS); hist = ro(P_HIST)

print("#"*100)
print("# A. NO-FILTER minima. If the prior agent's length(trade_date)=10 filter hid rows, this shows it.")
print("#"*100)
show("cache raw min/max NO filter", """
SELECT COUNT(*) AS n, MIN(trade_date) AS mn, MAX(trade_date) AS mx,
       COUNT(DISTINCT trade_date) AS ndates, COUNT(DISTINCT symbol) AS nsym
FROM daily_bar_cache""", ops)
show("bars raw min/max NO filter", """
SELECT COUNT(*) AS n, MIN(trade_date) AS mn, MAX(trade_date) AS mx,
       COUNT(DISTINCT trade_date) AS ndates, COUNT(DISTINCT symbol) AS nsym
FROM daily_bars""", hist)

print()
print("#"*100)
print("# B. FORMAT CENSUS of trade_date. Any non-10-char / non-ISO value would be invisible to their SQL.")
print("#"*100)
show("cache format census", """
SELECT length(trade_date) AS len, typeof(trade_date) AS ty, COUNT(*) AS n,
       MIN(trade_date) AS mn, MAX(trade_date) AS mx
FROM daily_bar_cache GROUP BY 1,2 ORDER BY 3 DESC""", ops)
show("bars format census", """
SELECT length(trade_date) AS len, typeof(trade_date) AS ty, COUNT(*) AS n,
       MIN(trade_date) AS mn, MAX(trade_date) AS mx
FROM daily_bars GROUP BY 1,2 ORDER BY 3 DESC""", hist)

print()
print("#"*100)
print("# C. ORDER BY ASC LIMIT (independent of MIN aggregate) + typed date() comparison")
print("#"*100)
show("cache 15 earliest by lexical asc", """
SELECT trade_date, symbol, source, adjustment_mode, close
FROM daily_bar_cache ORDER BY trade_date ASC LIMIT 15""", ops)
show("cache 15 earliest by date() cast asc", """
SELECT date(trade_date) AS d, trade_date, symbol
FROM daily_bar_cache WHERE date(trade_date) IS NOT NULL ORDER BY date(trade_date) ASC LIMIT 15""", ops)
show("bars 15 earliest by lexical asc", """
SELECT trade_date, symbol, adjustment_mode, provider, close
FROM daily_bars ORDER BY trade_date ASC LIMIT 15""", hist)

print()
print("#"*100)
print("# D. THE WINDOW. Count rows AND distinct dates AND distinct symbols in the three segments,")
print("#    using julianday() so string-vs-date is not the discriminator.")
print("#"*100)
for lbl, conn, tbl in (("trading_local.daily_bar_cache", ops, "daily_bar_cache"),
                       ("market_history.daily_bars",     hist, "daily_bars")):
    print("\n===", lbl)
    show("segments", f"""
SELECT CASE
         WHEN julianday(trade_date) IS NULL THEN 'Z_unparseable'
         WHEN julianday(trade_date) <  julianday('2023-09-04') THEN 'A_pre_window'
         WHEN julianday(trade_date) <= julianday('2024-04-08') THEN 'B_window_head_gap'
         WHEN julianday(trade_date) <= julianday('2026-09-04') THEN 'C_window_covered'
         ELSE 'D_post_window' END AS seg,
       COUNT(*) AS rows_, COUNT(DISTINCT trade_date) AS dates_, COUNT(DISTINCT symbol) AS syms_,
       MIN(trade_date) AS mn, MAX(trade_date) AS mx
FROM {tbl} GROUP BY 1 ORDER BY 1""", conn)

print()
print("#"*100)
print("# E. Is 2024-04-09 an artefact of one provider/source? Min per source/provider/adj mode.")
print("#"*100)
show("cache min per source", """
SELECT source, adjustment_mode, COUNT(*) n, MIN(trade_date) mn, MAX(trade_date) mx
FROM daily_bar_cache GROUP BY 1,2 ORDER BY 3 DESC""", ops)
show("bars min per provider/adj", """
SELECT provider, adjustment_mode, COUNT(*) n, MIN(trade_date) mn, MAX(trade_date) mx
FROM daily_bars GROUP BY 1,2 ORDER BY 3 DESC""", hist)

print()
print("#"*100)
print("# F. Min per exchange class in market_history (are indices deeper than stocks, or same floor?)")
print("#"*100)
show("bars min per instrument exchange", """
SELECT i.exchange, i.asset_type, COUNT(*) n, COUNT(DISTINCT b.symbol) syms,
       MIN(b.trade_date) mn, MAX(b.trade_date) mx
FROM daily_bars b LEFT JOIN instruments i ON i.symbol = b.symbol
GROUP BY 1,2 ORDER BY 3 DESC""", hist)
ops.close(); hist.close()
