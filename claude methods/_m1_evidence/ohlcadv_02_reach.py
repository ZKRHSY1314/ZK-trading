import sqlite3, json
TL = r"file:D:/codex-A股交易/trading_local.sqlite3?mode=ro"
tl = sqlite3.connect(TL, uri=True); tl.row_factory = sqlite3.Row
def show(label, sql, p=(), limit=45):
    print("\n"+"="*100); print("### "+label); print("SQL: "+" ".join(sql.split()))
    rows=[dict(r) for r in tl.execute(sql,p).fetchall()]
    print("ROWS: %d"%len(rows))
    for r in rows[:limit]: print("   ", json.dumps(r,ensure_ascii=False,default=str))
    if len(rows)>limit: print("    ...(%d more)"%(len(rows)-limit))
    return rows

show("R0 columns of historical_backtest_runs",
 "SELECT name FROM pragma_table_info('historical_backtest_runs')")

show("R1 all 39 backtest runs: window, status - do any span 2024-11-06?",
 """SELECT id, start_date, end_date, status, data_source,
        CASE WHEN start_date <= '2024-11-06' AND end_date >= '2024-11-06' THEN 'SPANS_2024-11-06' ELSE 'no' END AS spans
    FROM historical_backtest_runs ORDER BY id""")

show("R2 count of runs spanning 2024-11-06, by status",
 """SELECT status, COUNT(*) n FROM historical_backtest_runs
    WHERE start_date <= '2024-11-06' AND end_date >= '2024-11-06' GROUP BY status""")

show("R3 do any daily_equity rows exist ON 2024-11-06 (i.e. a run actually processed that bar)?",
 """SELECT COUNT(*) n_rows, COUNT(DISTINCT run_id) n_runs FROM historical_backtest_daily_equity
    WHERE trade_date='2024-11-06'""")

show("R4 daily_equity rows spanning 2024-11-05..2024-11-07 by run",
 """SELECT run_id, trade_date, COUNT(*) n FROM historical_backtest_daily_equity
    WHERE trade_date BETWEEN '2024-11-04' AND '2024-11-08' GROUP BY run_id, trade_date ORDER BY run_id, trade_date""")

# --- REACHABILITY: could any of the 3 be a *fresh* candidate on the preceding global trade date? ---
show("S1 do the 3 symbols have a bar on 2024-11-05 (needed for a same-day fresh strong signal)?",
 """SELECT symbol, COUNT(*) n FROM daily_bar_cache
    WHERE symbol IN ('SH688089','SH688143','SH688173') AND trade_date='2024-11-05' GROUP BY symbol""")

show("S2 the LAST cache bar strictly before 2024-11-06 for each of the 3 (the only day a carry-over candidate could originate)",
 """SELECT symbol, MAX(trade_date) AS last_bar_before FROM daily_bar_cache
    WHERE symbol IN ('SH688089','SH688143','SH688173') AND trade_date < '2024-11-06'
      AND quality_status='ready' GROUP BY symbol""")

show("S3 that prior bar's data (does it look like a limit-up / strong-signal bar?)",
 """SELECT c.symbol, c.trade_date, c.open, c.high, c.low, c.close, c.volume, c.amount
    FROM daily_bar_cache c
    JOIN (SELECT symbol, MAX(trade_date) d FROM daily_bar_cache
          WHERE symbol IN ('SH688089','SH688143','SH688173') AND trade_date<'2024-11-06'
            AND quality_status='ready' GROUP BY symbol) m
      ON m.symbol=c.symbol AND m.d=c.trade_date""")

show("S4 pct move on that prior bar vs its own previous bar (limit-up screen ~ +20% on STAR)",
 """WITH b AS (SELECT symbol, trade_date, close,
        LAG(close) OVER (PARTITION BY symbol ORDER BY trade_date) prev_close
      FROM daily_bar_cache WHERE symbol IN ('SH688089','SH688143','SH688173') AND quality_status='ready')
    SELECT symbol, trade_date, prev_close, close,
           ROUND((close-prev_close)/prev_close*100, 3) AS pct_change
    FROM b WHERE trade_date BETWEEN '2024-10-25' AND '2024-11-06' ORDER BY symbol, trade_date""")

# --- how many gap/suspension-style bars exist generally (context for severity) ---
show("T1 zero-VOLUME 'ready' bars overall (suspension markers) - how common, and how many have open>0",
 """SELECT COUNT(*) n_zero_volume_rows, COUNT(DISTINCT symbol) n_syms,
           SUM(CASE WHEN CAST(open AS REAL)<=0 THEN 1 ELSE 0 END) with_zero_open,
           SUM(CASE WHEN CAST(open AS REAL)>0 THEN 1 ELSE 0 END) with_positive_open
    FROM daily_bar_cache WHERE quality_status='ready' AND CAST(volume AS REAL)=0""")

show("T2 zero-volume ready bars by source",
 """SELECT source, COUNT(*) n, SUM(CASE WHEN CAST(open AS REAL)<=0 THEN 1 ELSE 0 END) zero_open
    FROM daily_bar_cache WHERE quality_status='ready' AND CAST(volume AS REAL)=0 GROUP BY source ORDER BY n DESC""")

show("T3 are the 3 rows inside the fixed research window 2023-09-04..2026-09-04?",
 """SELECT symbol, trade_date,
      CASE WHEN trade_date BETWEEN '2023-09-04' AND '2026-09-04' THEN 'IN_WINDOW' ELSE 'OUT' END w
    FROM daily_bar_cache WHERE quality_status='ready' AND CAST(open AS REAL)<=0""")
tl.close()
