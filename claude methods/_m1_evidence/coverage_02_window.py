import sqlite3, pathlib, sys
sys.stdout.reconfigure(encoding="utf-8")
OP = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"
W0, W1 = "2023-09-04", "2026-09-04"
def ro(p):
    return sqlite3.connect("file:" + pathlib.Path(p).as_posix() + "?mode=ro", uri=True)
def show(c, label, sql, params=()):
    print("### " + label)
    print("SQL:", " ".join(sql.split()))
    for r in c.execute(sql, params):
        print("   ", r)
    print()
op = ro(OP); mh = ro(MH)

print(">>> ANY DATA BEFORE WINDOW-RELEVANT BOUNDARIES")
show(op, "cache rows before 2024-04-09", "SELECT COUNT(*) FROM daily_bar_cache WHERE length(trade_date)=10 AND trade_date < '2024-04-09'")
show(op, "cache rows in window [2023-09-04,2026-09-04]", "SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ?", (W0,W1))
show(op, "cache rows BEFORE window (warm-up)", "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM daily_bar_cache WHERE length(trade_date)=10 AND trade_date < ?", (W0,))
show(op, "cache rows AFTER window", "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM daily_bar_cache WHERE length(trade_date)=10 AND trade_date > ?", (W1,))
show(op, "cache: malformed trade_date rows", "SELECT id, symbol, trade_date, source, quality_status, close FROM daily_bar_cache WHERE length(trade_date)<>10 OR trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'")

show(mh, "mh rows in window", "SELECT COUNT(*) FROM daily_bars WHERE trade_date BETWEEN ? AND ?", (W0,W1))
show(mh, "mh rows BEFORE window (warm-up)", "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM daily_bars WHERE trade_date < ?", (W0,))
show(mh, "mh rows AFTER window", "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM daily_bars WHERE trade_date > ?", (W1,))
show(mh, "mh: malformed trade_date rows", "SELECT COUNT(*) FROM daily_bars WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'")

print(">>> VALIDITY IN WINDOW")
VALID_OP = """SELECT COUNT(*) FROM daily_bar_cache
 WHERE trade_date BETWEEN ? AND ?
   AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
   AND open IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL AND close IS NOT NULL
   AND close > 0"""
show(op, "cache VALID rows in window", VALID_OP, (W0,W1))
show(op, "cache in-window null-OHLC breakdown",
  """SELECT SUM(open IS NULL) o_null, SUM(high IS NULL) h_null, SUM(low IS NULL) l_null, SUM(close IS NULL) c_null,
            SUM(CASE WHEN close IS NOT NULL AND close<=0 THEN 1 ELSE 0 END) close_nonpos,
            SUM(volume IS NULL) vol_null, SUM(amount IS NULL) amt_null,
            SUM(CASE WHEN amount IS NOT NULL AND amount=0 THEN 1 ELSE 0 END) amt_zero
     FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ?""", (W0,W1))
show(op, "cache in-window OHLC-consistency violations",
  """SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ?
       AND open IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL AND close IS NOT NULL
       AND (high < low OR high < open OR high < close OR low > open OR low > close)""", (W0,W1))
show(mh, "mh VALID rows in window",
  """SELECT COUNT(*) FROM daily_bars WHERE trade_date BETWEEN ? AND ?
       AND open IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL AND close IS NOT NULL AND close > 0""", (W0,W1))
show(mh, "mh in-window close<=0 / null vol",
  """SELECT SUM(CASE WHEN close<=0 THEN 1 ELSE 0 END) close_nonpos, SUM(volume IS NULL) vol_null,
            SUM(amount IS NULL) amt_null, SUM(available_at IS NULL) avail_null
     FROM daily_bars WHERE trade_date BETWEEN ? AND ?""", (W0,W1))

print(">>> DATE EXTREMES IN WINDOW")
show(op, "cache first/last in window", "SELECT MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ? AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'", (W0,W1))
show(op, "cache MOST RECENT date held (any)", "SELECT MAX(trade_date) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'")
show(mh, "mh first/last in window", "SELECT MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date) FROM daily_bars WHERE trade_date BETWEEN ? AND ?", (W0,W1))
show(mh, "mh MOST RECENT date held (any)", "SELECT MAX(trade_date) FROM daily_bars")

print(">>> SYMBOLS PER DATE (junk-date detection), last 10 + first 10 of window")
show(op, "cache: symbols per date, first 12 dates", "SELECT trade_date, COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ? GROUP BY 1 ORDER BY 1 LIMIT 12", (W0,W1))
show(op, "cache: symbols per date, last 12 dates", "SELECT trade_date, COUNT(DISTINCT symbol) FROM (SELECT trade_date, symbol FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ?) GROUP BY 1 ORDER BY 1 DESC LIMIT 12", (W0,W1))
show(op, "cache: dates with <100 symbols", "SELECT trade_date, COUNT(DISTINCT symbol) n FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ? GROUP BY 1 HAVING n < 100 ORDER BY 1", (W0,W1))
show(mh, "mh: symbols per date, last 12 dates", "SELECT trade_date, COUNT(DISTINCT symbol) FROM (SELECT trade_date, symbol FROM daily_bars WHERE trade_date BETWEEN ? AND ?) GROUP BY 1 ORDER BY 1 DESC LIMIT 12", (W0,W1))
show(mh, "mh: dates with <100 symbols", "SELECT trade_date, COUNT(DISTINCT symbol) n FROM daily_bars WHERE trade_date BETWEEN ? AND ? GROUP BY 1 HAVING n < 100 ORDER BY 1", (W0,W1))
