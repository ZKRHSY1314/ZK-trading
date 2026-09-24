# -*- coding: utf-8 -*-
"""ADVERSARIAL pass 2: is 2024-04-09 a real coverage start, or a 1-row artifact?
Plus: hunt EVERY table in BOTH dbs for any bar-like date < 2024-04-09. STRICT READ-ONLY."""
import sqlite3, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
OP = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
def show(t, sql, con, params=()):
    print("="*78); print(t); print("SQL:", " ".join(sql.split()))
    try:
        cur=con.execute(sql,params); rows=cur.fetchall()
        print("COLS:", [d[0] for d in cur.description])
        for r in rows[:80]: print("   ", r)
        if len(rows)>80: print(f"    ...{len(rows)-80} more")
    except Exception as e: print("  ERROR:", e)
    print()
op=ro(OP); mh=ro(MH)

print("#### F. BREADTH CURVE — how many symbols actually trade on each early session? ####")
show("F1 symbols-per-session at monthly checkpoints, plus the max breadth ever reached",
 """WITH b AS (SELECT trade_date, COUNT(DISTINCT symbol) syms FROM daily_bar_cache
             WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' GROUP BY trade_date)
    SELECT substr(trade_date,1,7) ym, MIN(syms) min_syms, MAX(syms) max_syms,
           CAST(AVG(syms) AS INT) avg_syms, COUNT(*) sessions
    FROM b GROUP BY ym ORDER BY ym""", op)

show("F2 FIRST session reaching each breadth threshold (peak breadth = denominator)",
 """WITH b AS (SELECT trade_date, COUNT(DISTINCT symbol) syms FROM daily_bar_cache
             WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' GROUP BY trade_date),
      pk AS (SELECT MAX(syms) p FROM b)
    SELECT (SELECT p FROM pk) AS peak_breadth,
      (SELECT MIN(trade_date) FROM b WHERE syms >= 0.10*(SELECT p FROM pk)) AS first_10pct,
      (SELECT MIN(trade_date) FROM b WHERE syms >= 0.50*(SELECT p FROM pk)) AS first_50pct,
      (SELECT MIN(trade_date) FROM b WHERE syms >= 0.90*(SELECT p FROM pk)) AS first_90pct,
      (SELECT MIN(trade_date) FROM b WHERE syms >= 0.95*(SELECT p FROM pk)) AS first_95pct""", op)

show("F3 bars-per-symbol distribution — is there a fixed rolling cap?",
 """SELECT n_bars, COUNT(*) n_symbols FROM
      (SELECT symbol, COUNT(*) n_bars FROM daily_bar_cache
       WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' GROUP BY symbol)
    GROUP BY n_bars ORDER BY n_symbols DESC LIMIT 20""", op)

show("F4 summary stats of bars-per-symbol",
 """SELECT COUNT(*) symbols, MIN(n) min_bars, MAX(n) max_bars, CAST(AVG(n) AS INT) avg_bars,
           SUM(CASE WHEN n>=500 THEN 1 ELSE 0 END) ge500,
           SUM(CASE WHEN n<250 THEN 1 ELSE 0 END) lt250
    FROM (SELECT symbol, COUNT(*) n FROM daily_bar_cache
          WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' GROUP BY symbol)""", op)

print("#### G. Were these stocks LISTED before 2023-09-04? (missing history vs new listing) ####")
show("G1 instruments listed on/before 2023-09-04 that are equities, vs what daily_bar_cache holds",
 """SELECT asset_type, exchange, status, COUNT(*) n
    FROM instruments WHERE list_date IS NOT NULL AND list_date <= '2023-09-04'
    GROUP BY 1,2,3 ORDER BY n DESC LIMIT 30""", mh)

show("G2 how many instruments were listed and NOT delisted across the whole window start",
 """SELECT COUNT(*) AS listed_and_alive_on_2023_09_04
    FROM instruments
    WHERE list_date IS NOT NULL AND list_date <= '2023-09-04'
      AND (delist_date IS NULL OR delist_date > '2023-09-04')
      AND exchange IN ('SH','SZ','BJ')""", mh)

print("#### H. GLOBAL HUNT: any table in EITHER db with a date-ish column holding < 2024-04-09 bars ####")
for name, con in (("trading_local", op), ("market_history", mh)):
    print(f"--- scanning {name} ---")
    tabs=[r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    for t in tabs:
        try: cols=[(r[1],r[2]) for r in con.execute(f'PRAGMA table_info("{t}")')]
        except Exception: continue
        dcols=[c for c,_ in cols if any(k in c.lower() for k in
               ('trade_date','bar_date','session_date','as_of','date'))]
        for c in dcols:
            try:
                r=con.execute(f'SELECT MIN("{c}"), MAX("{c}"), COUNT(*) FROM "{t}" '
                              f'WHERE "{c}" GLOB \'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]\'').fetchone()
            except Exception: continue
            if r and r[0] and r[0] < '2024-04-09':
                n_old=con.execute(f'SELECT COUNT(*) FROM "{t}" WHERE "{c}" GLOB '
                    f"'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND \"{c}\" < '2024-04-09'").fetchone()[0]
                n_pre=con.execute(f'SELECT COUNT(*) FROM "{t}" WHERE "{c}" GLOB '
                    f"'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND \"{c}\" < '2023-09-04'").fetchone()[0]
                print(f"  HIT {t}.{c}: min={r[0]} max={r[1]} total={r[2]} rows_lt_2024_04_09={n_old} rows_lt_2023_09_04={n_pre}")
    print()

show("H2 global_market_bars — is this an A-share rescue store?",
 """SELECT COUNT(*) n, COUNT(DISTINCT symbol) syms, MIN(trade_date), MAX(trade_date)
    FROM global_market_bars""", op)

show("H3 global_market_bars symbol sample",
 "SELECT symbol, COUNT(*) n, MIN(trade_date), MAX(trade_date) FROM global_market_bars GROUP BY symbol ORDER BY n DESC LIMIT 20", op)

print("#### I. Are indices being counted as stocks in the 5,567? ####")
show("I1 the SH0-prefix symbols (index-shaped) present in daily_bar_cache",
 "SELECT symbol, COUNT(*) n, MIN(trade_date), MAX(trade_date) FROM daily_bar_cache WHERE symbol LIKE 'SH0%' OR symbol LIKE 'SZ399%' GROUP BY symbol ORDER BY symbol LIMIT 30", op)

show("I2 join daily_bar_cache symbols to instruments.asset_type (cross-db not possible; list distinct prefixes)",
 """SELECT CASE WHEN symbol GLOB 'SH6*' THEN 'SH main'
                WHEN symbol GLOB 'SH68*' THEN 'STAR'
                WHEN symbol GLOB 'SH0*' THEN 'SH index-shaped'
                WHEN symbol GLOB 'SZ0*' THEN 'SZ main'
                WHEN symbol GLOB 'SZ3*' THEN 'SZ ChiNext'
                WHEN symbol GLOB 'BJ*' THEN 'BSE'
                ELSE 'bare/other' END AS cls,
           COUNT(DISTINCT symbol) syms, COUNT(*) rows, MIN(trade_date) min_td
    FROM daily_bar_cache GROUP BY 1 ORDER BY syms DESC""", op)
op.close(); mh.close()
