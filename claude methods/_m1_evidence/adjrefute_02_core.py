import sqlite3
TL=r"D:/codex-A股交易/trading_local.sqlite3"
MH=r"D:/codex-A股交易/market_history.sqlite3"
c=sqlite3.connect(f"file:{TL}?mode=ro",uri=True)
c.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")
q=lambda s,*a: c.execute(s,a).fetchall()
def P(t,s,*a):
    print("\n### "+t); print("SQL:",' '.join(s.split()))
    for r in q(s,*a): print("   ",r)

# ---------- A. available_at vs fetched_at identity ----------
P("A1 available_at NULL / identical-to-fetched_at / different",
  """SELECT COUNT(*) total,
            SUM(available_at IS NULL) null_avail,
            SUM(available_at = fetched_at) identical,
            SUM(available_at IS NOT NULL AND available_at <> fetched_at) differs
     FROM mh.daily_bars""")

P("A2 distinct available_at values (full string), and distinct DATE part",
  """SELECT COUNT(DISTINCT available_at) distinct_full,
            COUNT(DISTINCT substr(available_at,1,10)) distinct_day
     FROM mh.daily_bars""")

P("A3 available_at day cohorts x provider",
  """SELECT substr(available_at,1,10) d, provider, COUNT(*) n, COUNT(DISTINCT symbol) syms,
            MIN(trade_date), MAX(trade_date)
     FROM mh.daily_bars GROUP BY 1,2 ORDER BY 1,3 DESC""")

# ---------- B. PIT retrievability, date-safe (avoid string 'T' off-by-one) ----------
P("B1 PIT counts using DATE-SAFE compare substr(available_at,1,10)<=as_of  (mine, not theirs)",
  """SELECT
      (SELECT COUNT(*) FROM mh.daily_bars WHERE substr(available_at,1,10)<='2023-12-31' AND trade_date<='2023-12-31'),
      (SELECT COUNT(*) FROM mh.daily_bars WHERE substr(available_at,1,10)<='2024-06-30' AND trade_date<='2024-06-30'),
      (SELECT COUNT(*) FROM mh.daily_bars WHERE substr(available_at,1,10)<='2025-06-30' AND trade_date<='2025-06-30'),
      (SELECT COUNT(*) FROM mh.daily_bars WHERE substr(available_at,1,10)<='2026-06-30' AND trade_date<='2026-06-30'),
      (SELECT COUNT(*) FROM mh.daily_bars WHERE substr(available_at,1,10)<='2026-07-15' AND trade_date<='2026-07-15'),
      (SELECT COUNT(*) FROM mh.daily_bars WHERE substr(available_at,1,10)<='2026-09-04')""")

P("B2 distinct SECURITIES (not rows) retrievable at each as-of, excluding indices",
  """SELECT
      (SELECT COUNT(DISTINCT b.symbol) FROM mh.daily_bars b JOIN mh.instruments i ON i.symbol=b.symbol
         WHERE i.exchange<>'INDEX' AND substr(b.available_at,1,10)<='2024-06-30' AND b.trade_date<='2024-06-30'),
      (SELECT COUNT(DISTINCT b.symbol) FROM mh.daily_bars b JOIN mh.instruments i ON i.symbol=b.symbol
         WHERE i.exchange<>'INDEX' AND substr(b.available_at,1,10)<='2025-06-30' AND b.trade_date<='2025-06-30'),
      (SELECT COUNT(DISTINCT b.symbol) FROM mh.daily_bars b JOIN mh.instruments i ON i.symbol=b.symbol
         WHERE i.exchange<>'INDEX' AND substr(b.available_at,1,10)<='2026-06-30' AND b.trade_date<='2026-06-30')""")

P("B3 min/max available_at, min/max trade_date, and any available_at earlier than trade_date",
  """SELECT MIN(available_at),MAX(available_at),MIN(trade_date),MAX(trade_date),
            SUM(CASE WHEN substr(available_at,1,10) < trade_date THEN 1 ELSE 0 END) avail_before_trade
     FROM mh.daily_bars""")

P("B4 lag buckets (days between trade_date and available_at day)",
  """SELECT CASE
       WHEN julianday(substr(available_at,1,10))-julianday(trade_date) <= 1 THEN 'a<=1d'
       WHEN julianday(substr(available_at,1,10))-julianday(trade_date) <= 30 THEN 'b<=30d'
       WHEN julianday(substr(available_at,1,10))-julianday(trade_date) <= 365 THEN 'c<=1y'
       ELSE 'd>1y' END bucket, COUNT(*) n
     FROM mh.daily_bars GROUP BY 1 ORDER BY 1""")

# ---------- C. adjustment vintage capability ----------
P("C1 market_history adjustment_mode coverage (can raw/qfq pair yield a factor?)",
  """SELECT adjustment_mode, COUNT(*) FROM mh.daily_bars GROUP BY 1""")
P("C2 cache adjustment_mode coverage",
  """SELECT adjustment_mode, COUNT(*), COUNT(DISTINCT symbol) FROM daily_bar_cache GROUP BY 1""")
P("C3 symbols having BOTH 'none' and 'qfq' anywhere (would allow deriving adj factor)",
  """SELECT COUNT(*) FROM (SELECT symbol FROM daily_bar_cache GROUP BY symbol
        HAVING SUM(adjustment_mode='none')>0 AND SUM(adjustment_mode='qfq')>0)""")

# ---------- D. corporate action tables anywhere ----------
P("D1 any table/column matching corporate-action words, market_history",
  """SELECT name FROM mh.sqlite_master WHERE type='table' AND (
        lower(sql) LIKE '%dividend%' OR lower(sql) LIKE '%split%' OR lower(sql) LIKE '%adj_factor%'
        OR lower(sql) LIKE '%adjustment_factor%' OR lower(sql) LIKE '%ex_date%' OR lower(sql) LIKE '%corporate%')""")
P("D2 same for trading_local",
  """SELECT name FROM sqlite_master WHERE type='table' AND (
        lower(sql) LIKE '%dividend%' OR lower(sql) LIKE '%split%' OR lower(sql) LIKE '%adj_factor%'
        OR lower(sql) LIKE '%adjustment_factor%' OR lower(sql) LIKE '%ex_date%' OR lower(sql) LIKE '%corporate%')""")
P("D3 table count market_history / trading_local",
  """SELECT (SELECT COUNT(*) FROM mh.sqlite_master WHERE type='table'),
            (SELECT COUNT(*) FROM sqlite_master WHERE type='table')""")
c.close()
