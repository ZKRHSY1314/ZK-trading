import sqlite3, pathlib
OP = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"
def ro(p):
    return sqlite3.connect("file:" + pathlib.Path(p).as_posix() + "?mode=ro", uri=True)
def show(c, label, sql):
    print("### " + label)
    print("SQL:", " ".join(sql.split()))
    for r in c.execute(sql):
        print("   ", r)
    print()

op = ro(OP); mh = ro(MH)

show(op, "cache: sample symbols", "SELECT symbol FROM daily_bar_cache GROUP BY symbol ORDER BY symbol LIMIT 15")
show(op, "cache: sample symbols desc", "SELECT symbol FROM daily_bar_cache GROUP BY symbol ORDER BY symbol DESC LIMIT 15")
show(op, "cache: symbol length dist", "SELECT length(symbol) AS n, COUNT(DISTINCT symbol) FROM daily_bar_cache GROUP BY 1 ORDER BY 1")
show(op, "cache: distinct symbols total", "SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache")
show(op, "cache: min/max trade_date overall", "SELECT MIN(trade_date), MAX(trade_date) FROM daily_bar_cache")
show(op, "cache: trade_date length dist", "SELECT length(trade_date), COUNT(*) FROM daily_bar_cache GROUP BY 1 ORDER BY 1")
show(op, "cache: adjustment_mode dist", "SELECT adjustment_mode, COUNT(*) FROM daily_bar_cache GROUP BY 1 ORDER BY 2 DESC")
show(op, "cache: volume_unit dist", "SELECT volume_unit, COUNT(*) FROM daily_bar_cache GROUP BY 1 ORDER BY 2 DESC")
show(op, "cache: source dist", "SELECT source, COUNT(*) FROM daily_bar_cache GROUP BY 1 ORDER BY 2 DESC")
show(op, "cache: quality_status dist", "SELECT quality_status, COUNT(*) FROM daily_bar_cache GROUP BY 1 ORDER BY 2 DESC")

show(mh, "mh: sample symbols", "SELECT symbol FROM daily_bars GROUP BY symbol ORDER BY symbol LIMIT 15")
show(mh, "mh: symbol length dist", "SELECT length(symbol), COUNT(DISTINCT symbol) FROM daily_bars GROUP BY 1 ORDER BY 1")
show(mh, "mh: distinct symbols total", "SELECT COUNT(DISTINCT symbol) FROM daily_bars")
show(mh, "mh: min/max trade_date overall", "SELECT MIN(trade_date), MAX(trade_date) FROM daily_bars")
show(mh, "mh: adjustment_mode dist", "SELECT adjustment_mode, COUNT(*), COUNT(DISTINCT symbol) FROM daily_bars GROUP BY 1 ORDER BY 2 DESC")
show(mh, "mh: volume_unit dist", "SELECT volume_unit, COUNT(*) FROM daily_bars GROUP BY 1 ORDER BY 2 DESC")
show(mh, "mh: provider dist", "SELECT provider, COUNT(*) FROM daily_bars GROUP BY 1 ORDER BY 2 DESC")
show(mh, "mh: quality_status dist", "SELECT quality_status, COUNT(*) FROM daily_bars GROUP BY 1 ORDER BY 2 DESC")
show(mh, "instruments: exchange x asset_type", "SELECT exchange, asset_type, status, COUNT(*) FROM instruments GROUP BY 1,2,3 ORDER BY 4 DESC")
show(mh, "instruments: sample symbols", "SELECT symbol, name, exchange, asset_type, board, list_date, delist_date, status FROM instruments ORDER BY symbol LIMIT 10")
show(mh, "instruments: list_date null count", "SELECT COUNT(*) total, SUM(CASE WHEN list_date IS NULL OR trim(list_date)='' THEN 1 ELSE 0 END) null_list, SUM(CASE WHEN delist_date IS NOT NULL AND trim(delist_date)<>'' THEN 1 ELSE 0 END) has_delist FROM instruments")
