import sqlite3, pathlib, sys
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
MH = r"D:\codex-A股交易\market_history.sqlite3"
def ro(p):
    return sqlite3.connect("file:" + pathlib.Path(p).as_posix() + "?mode=ro", uri=True)
def show(c, label, sql, params=()):
    print("### " + label); print("SQL:", " ".join(sql.split()))
    for r in c.execute(sql, params): print("   ", r)
    print(flush=True)
mh = ro(MH)
show(mh, "instruments: distinct asset_type", "SELECT asset_type, COUNT(*) FROM instruments GROUP BY 1")
show(mh, "instruments: board dist", "SELECT board, exchange, COUNT(*) FROM instruments GROUP BY 1,2 ORDER BY 3 DESC")
show(mh, "instruments: status dist", "SELECT status, COUNT(*) FROM instruments GROUP BY 1")
show(mh, "instruments: symbol prefix dist", "SELECT substr(symbol,1,2), COUNT(*) FROM instruments GROUP BY 1")
show(mh, "instruments: list_date range", "SELECT MIN(list_date), MAX(list_date), COUNT(*) FROM instruments WHERE list_date IS NOT NULL AND trim(list_date)<>''")
show(mh, "instruments: list_date malformed", "SELECT COUNT(*) FROM instruments WHERE list_date IS NOT NULL AND list_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'")
show(mh, "instruments: NULL list_date rows", "SELECT symbol, name, exchange, board, status, provider FROM instruments WHERE list_date IS NULL OR trim(list_date)='' ORDER BY symbol")
show(mh, "instruments: list_date >= window start (new listings within window)", "SELECT COUNT(*) FROM instruments WHERE list_date >= '2023-09-04'")
show(mh, "instruments: list_date >= 2024-04-09 (after data start)", "SELECT COUNT(*) FROM instruments WHERE list_date >= '2024-04-09'")
show(mh, "instruments: inactive rows", "SELECT symbol, name, exchange, status, list_date, delist_date FROM instruments WHERE status<>'active'")
show(mh, "instruments: provider", "SELECT provider, COUNT(*), MIN(fetched_at), MAX(fetched_at) FROM instruments GROUP BY 1")
show(mh, "universe_snapshots", "SELECT id, universe_name, snapshot_date, provider, member_count, fetched_at FROM universe_snapshots ORDER BY snapshot_date")
show(mh, "ingest_runs summary", "SELECT COUNT(*), MIN(started_at), MAX(started_at) FROM ingest_runs")
