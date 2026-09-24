import sqlite3
CACHE = r"D:/codex-A股交易/trading_local.sqlite3"
HIST  = r"D:/codex-A股交易/market_history.sqlite3"
con = sqlite3.connect(f"file:{HIST}?mode=ro", uri=True)
con.execute("ATTACH DATABASE ? AS cache", (f"file:{CACHE}?mode=ro",))
con.row_factory = sqlite3.Row
def q(label, sql, params=()):
    print("\n### "+label, flush=True)
    print("SQL:", " ".join(sql.split()), flush=True)
    for r in con.execute(sql, params).fetchall()[:80]:
        print("   ", dict(r), flush=True)

q("A adjustment_mode in market_history.daily_bars",
  "SELECT adjustment_mode, COUNT(*) n, COUNT(DISTINCT symbol) syms, MIN(trade_date) d0, MAX(trade_date) d1 FROM main.daily_bars GROUP BY 1")
q("B provider distribution in market_history.daily_bars",
  "SELECT provider, COUNT(*) n, COUNT(DISTINCT symbol) syms FROM main.daily_bars GROUP BY 1 ORDER BY n DESC")
q("B2 source distribution in cache.daily_bar_cache",
  "SELECT source, adjustment_mode, quality_status, COUNT(*) n FROM cache.daily_bar_cache GROUP BY 1,2,3 ORDER BY n DESC")
q("C distinct-symbol asymmetry",
  """SELECT
      (SELECT COUNT(*) FROM (SELECT DISTINCT symbol FROM main.daily_bars EXCEPT SELECT DISTINCT symbol FROM cache.daily_bar_cache)) AS syms_only_in_hist,
      (SELECT COUNT(*) FROM (SELECT DISTINCT symbol FROM cache.daily_bar_cache WHERE trade_date!='ERROR' EXCEPT SELECT DISTINCT symbol FROM main.daily_bars)) AS syms_only_in_cache,
      (SELECT COUNT(DISTINCT symbol) FROM main.daily_bars) AS hist_syms,
      (SELECT COUNT(DISTINCT symbol) FROM cache.daily_bar_cache WHERE trade_date!='ERROR') AS cache_syms""")
q("F row arithmetic closure",
  """SELECT (SELECT COUNT(*) FROM cache.daily_bar_cache) AS cache_rows,
            (SELECT COUNT(*) FROM cache.daily_bar_cache WHERE trade_date='ERROR') AS cache_error_rows,
            (SELECT COUNT(*) FROM main.daily_bars) AS hist_rows""")
q("G ingest_runs providers + dataset names",
  "SELECT provider, dataset_name, COUNT(*) runs, MIN(started_at) t0, MAX(started_at) t1 FROM main.ingest_runs GROUP BY 1,2 ORDER BY runs DESC")
con.close()
