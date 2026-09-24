import sqlite3, datetime, sys
TL = "D:/codex-A股交易/trading_local.sqlite3"
MH = "D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
tl, mh = ro(TL), ro(MH)
W0, W1 = '2023-09-04', '2026-09-04'
def P(*a): print(*a); sys.stdout.flush()

P("### 1. BENCHMARK SERIES — raw, no calendar")
for r in tl.execute("""
  SELECT symbol, COUNT(*) rows_all, COUNT(DISTINCT trade_date) ddays,
         MIN(trade_date), MAX(trade_date),
         SUM(CASE WHEN trade_date BETWEEN ? AND ? THEN 1 ELSE 0 END) in_window,
         SUM(CASE WHEN trade_date < ? THEN 1 ELSE 0 END) before_window,
         SUM(CASE WHEN trade_date > ? THEN 1 ELSE 0 END) after_window,
         SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) null_close,
         SUM(CASE WHEN quality_status='ready' THEN 1 ELSE 0 END) ready
  FROM daily_bar_cache WHERE symbol IN ('SH000300','SH000001') GROUP BY symbol""",(W0,W1,W0,W1)):
    P("   ", r)

P("\n   source/quality/adjustment of benchmark rows:")
for r in tl.execute("""SELECT symbol, source, quality_status, adjustment_mode, volume_unit, COUNT(*)
                       FROM daily_bar_cache WHERE symbol IN ('SH000300','SH000001') GROUP BY 1,2,3,4,5"""):
    P("   ", r)

P("\n   identical date sets between the two benchmarks?")
P("   ", tl.execute("""SELECT
   (SELECT COUNT(*) FROM (SELECT trade_date FROM daily_bar_cache WHERE symbol='SH000300'
                          EXCEPT SELECT trade_date FROM daily_bar_cache WHERE symbol='SH000001')),
   (SELECT COUNT(*) FROM (SELECT trade_date FROM daily_bar_cache WHERE symbol='SH000001'
                          EXCEPT SELECT trade_date FROM daily_bar_cache WHERE symbol='SH000300'))""").fetchone())

P("\n### 2. Benchmark rows anywhere before 2024-06-19?")
P("   dbc <2024-06-19:", tl.execute("SELECT COUNT(*) FROM daily_bar_cache WHERE symbol IN ('SH000300','SH000001') AND trade_date<'2024-06-19'").fetchone()[0])
P("   market_history index-shaped:", mh.execute("SELECT COUNT(*) FROM daily_bars WHERE symbol LIKE 'SH000%' OR symbol LIKE 'SZ399%'").fetchone()[0])
P("   market_history instruments exchange list:", [r[0] for r in mh.execute("SELECT DISTINCT exchange FROM instruments")])

P("\n### 7. Weekday arithmetic")
d0=datetime.date(2023,9,4); d1=datetime.date(2026,9,4)
P("   caldays:",(d1-d0).days+1," weekdays:",sum(1 for i in range((d1-d0).days+1) if (d0+datetime.timedelta(days=i)).weekday()<5))
