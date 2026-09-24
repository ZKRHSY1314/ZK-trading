# -*- coding: utf-8 -*-
import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
W0, W1 = "2023-09-04", "2026-09-04"

def q(path, sql, params=()):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()

def show(title, sql, path=TL, params=()):
    print("\n### " + title)
    print("SQL: " + " ".join(sql.split()))
    for r in q(path, sql, params):
        print("   ", r)

show("A1 cache adjustment_mode distribution (all rows)",
 "SELECT adjustment_mode, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS syms, MIN(trade_date), MAX(trade_date) FROM daily_bar_cache GROUP BY adjustment_mode ORDER BY rows DESC")

show("A2 cache volume_unit distribution (all rows)",
 "SELECT volume_unit, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS syms, MIN(trade_date), MAX(trade_date) FROM daily_bar_cache GROUP BY volume_unit ORDER BY rows DESC")

show("A3 cache adjustment_mode x volume_unit x source",
 "SELECT adjustment_mode, volume_unit, source, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS syms FROM daily_bar_cache GROUP BY 1,2,3 ORDER BY rows DESC")

show("A4 cache source distribution overall",
 "SELECT source, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS syms, MIN(trade_date), MAX(trade_date) FROM daily_bar_cache GROUP BY source ORDER BY rows DESC")

show("A5 cache source distribution WITHIN window 2023-09-04..2026-09-04",
 "SELECT source, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS syms, MIN(trade_date), MAX(trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04' GROUP BY source ORDER BY rows DESC")

show("A6 cache adjustment_mode WITHIN window",
 "SELECT adjustment_mode, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS syms FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04' GROUP BY 1 ORDER BY rows DESC")

show("A7 cache volume_unit WITHIN window",
 "SELECT volume_unit, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS syms FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04' GROUP BY 1 ORDER BY rows DESC")

show("A8 cache quality_status distribution",
 "SELECT quality_status, adjustment_mode, COUNT(*) FROM daily_bar_cache GROUP BY 1,2 ORDER BY 3 DESC")

show("B1 market_history daily_bars adjustment_mode distribution",
 "SELECT adjustment_mode, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS syms, MIN(trade_date), MAX(trade_date) FROM daily_bars GROUP BY 1 ORDER BY rows DESC", MH)

show("B2 market_history volume_unit x provider",
 "SELECT adjustment_mode, volume_unit, provider, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS syms FROM daily_bars GROUP BY 1,2,3 ORDER BY rows DESC", MH)

show("B3 market_history fetched_at distribution (distinct dates)",
 "SELECT substr(fetched_at,1,10) AS fetch_day, COUNT(*) AS rows, COUNT(DISTINCT symbol) AS syms FROM daily_bars GROUP BY 1 ORDER BY 1", MH)

show("B4 market_history available_at nullness",
 "SELECT CASE WHEN available_at IS NULL THEN 'NULL' ELSE 'present' END AS av, COUNT(*), COUNT(DISTINCT substr(available_at,1,10)) FROM daily_bars GROUP BY 1", MH)

show("B5 market_history available_at vs trade_date relation sample",
 "SELECT substr(available_at,1,10) AS av_day, COUNT(*) FROM daily_bars GROUP BY 1 ORDER BY 2 DESC LIMIT 20", MH)

show("B6 ingest_runs summary",
 "SELECT dataset_name, provider, adjustment_mode, status, COUNT(*) AS runs, MIN(requested_at), MAX(requested_at), SUM(inserted_row_count), SUM(updated_row_count) FROM ingest_runs GROUP BY 1,2,3,4 ORDER BY runs DESC", MH)

show("B7 ingest_runs full listing (id, mode, times)",
 "SELECT id, dataset_name, provider, adjustment_mode, status, requested_at, completed_at, requested_symbol_count, processed_symbol_count, inserted_row_count, updated_row_count FROM ingest_runs ORDER BY id", MH)
