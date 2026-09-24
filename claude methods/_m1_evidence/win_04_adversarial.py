import sqlite3, statistics
from collections import Counter
TL = r"D:/codex-A股交易/trading_local.sqlite3"; MH = r"D:/codex-A股交易/market_history.sqlite3"
W0,W1='2023-09-04','2026-09-04'
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True); c.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")
def q(sql,label,args=()):
    print("\n### "+label); print("SQL:"," ".join(sql.split()))
    for r in c.execute(sql,args): print("   ",r)

# A. index contamination check
q("""SELECT d.symbol, COUNT(*) , MIN(d.trade_date), MAX(d.trade_date), MIN(d.source)
     FROM daily_bar_cache d LEFT JOIN mh.instruments i ON i.symbol=d.symbol
     WHERE i.symbol IS NULL GROUP BY d.symbol""", "cache symbols with NO instrument row (would-be indices/fixtures)")
q("SELECT COUNT(*) FROM mh.instruments WHERE asset_type<>'stock' OR exchange NOT IN ('SH','SZ','BJ')",
  "instrument rows that are NOT SH/SZ/BJ stocks (index rows in the denominator?)")

# B. is there ANY bar of ANY kind anywhere before the first data session?
q("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date>=? AND trade_date<'2024-04-09' AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'",
  "cache rows in window BEFORE 2024-04-09 (the 7-month hole)", (W0,))
q("SELECT COUNT(*), COUNT(DISTINCT trade_date) FROM mh.daily_bars WHERE trade_date>=? AND trade_date<'2024-04-09'",
  "market_history rows in window BEFORE 2024-04-09", (W0,))
q("SELECT MIN(trade_date) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'",
  "earliest valid date ANYWHERE in cache (incl. pre-window warm-up)")
q("SELECT MIN(trade_date) FROM mh.daily_bars", "earliest date ANYWHERE in market_history")

# C. does a looser filter (drop close>0 / OHLC-not-null) change the picture?
for name, extra in (("strict OHLC+close>0","AND d.open IS NOT NULL AND d.high IS NOT NULL AND d.low IS NOT NULL AND d.close IS NOT NULL AND d.close>0"),
                    ("ANY row at all","")):
    sql = f"""SELECT MAX(n), AVG(n)*1.0 FROM (
        SELECT COUNT(DISTINCT d.trade_date) n FROM mh.instruments i JOIN daily_bar_cache d ON d.symbol=i.symbol
        WHERE d.trade_date BETWEEN '{W0}' AND '{W1}' AND d.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' {extra}
          AND i.list_date < '2024-04-09' GROUP BY i.symbol)"""
    q(sql, f"pre-existing cohort max/avg observed sessions -- filter='{name}'")
q("SELECT quality_status, COUNT(*) FROM daily_bar_cache GROUP BY 1 ORDER BY 2 DESC LIMIT 6","cache quality_status mix")

# D. the 501-cohort and the partial final session
q("""SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date='2026-09-04'""","rows on final session 2026-09-04")
q("""SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date='2026-09-03'""","rows on 2026-09-03 for comparison")

# E. INDEPENDENT CROSS-CHECK in market_history (different DB, different table, PK-constrained)
SQL_MH = """
SELECT observed, COUNT(*) FROM (
  SELECT i.symbol, COUNT(DISTINCT b.trade_date) AS observed
  FROM mh.instruments i JOIN mh.daily_bars b ON b.symbol=i.symbol AND b.adjustment_mode='none'
  WHERE b.trade_date BETWEEN ? AND ? AND i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ')
    AND i.list_date < '2024-04-09'
  GROUP BY i.symbol) GROUP BY observed ORDER BY COUNT(*) DESC LIMIT 6"""
q(SQL_MH, "market_history.daily_bars(none): observed-session histogram, pre-existing stocks", (W0,W1))
q("SELECT adjustment_mode, COUNT(*), COUNT(DISTINCT trade_date) FROM mh.daily_bars GROUP BY 1","MH adjustment_mode split")
c.close()
