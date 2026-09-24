import sqlite3
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True); m = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)
print("sqlite", sqlite3.sqlite_version)

print("\n=== mh instruments.board values ===")
for r in m.execute("SELECT board, COUNT(*) FROM instruments GROUP BY 1 ORDER BY 2 DESC"): print(r)

print("\n=== board vs symbol-prefix rule agreement (mh.instruments) ===")
q = """
SELECT board,
  CASE WHEN symbol LIKE 'SH688%' OR symbol LIKE 'SH689%' THEN 'p20_star'
       WHEN symbol LIKE 'SZ30%' THEN 'p20_chinext'
       WHEN symbol LIKE 'BJ%' THEN 'p30_bj'
       WHEN symbol LIKE 'SH60%' OR symbol LIKE 'SZ00%' THEN 'p10_main'
       ELSE 'p_UNCLASSIFIED' END AS prefix_rule,
  COUNT(*) FROM instruments GROUP BY 1,2 ORDER BY 3 DESC"""
for r in m.execute(q): print(r)
print("\n-- unclassified-by-prefix instruments:")
for r in m.execute("""SELECT symbol,board,list_date,status FROM instruments
   WHERE NOT (symbol LIKE 'SH688%' OR symbol LIKE 'SH689%' OR symbol LIKE 'SZ30%'
              OR symbol LIKE 'BJ%' OR symbol LIKE 'SH60%' OR symbol LIKE 'SZ00%') LIMIT 40"""): print(r)

print("\n=== cache close decimal places (window rows) ===")
for r in c.execute("""SELECT CASE
   WHEN close IS NULL THEN 'null'
   WHEN close = ROUND(close,2) THEN 'le2dp'
   WHEN close = ROUND(close,3) THEN '3dp'
   WHEN close = ROUND(close,4) THEN '4dp' ELSE 'gt4dp' END k, COUNT(*)
   FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04' GROUP BY 1"""): print(r)

print("\n=== cache close price level distribution (window) ===")
for r in c.execute("""SELECT CASE WHEN close IS NULL THEN 'null' WHEN close<0.5 THEN 'a_<0.5'
   WHEN close<1 THEN 'b_0.5-1' WHEN close<2 THEN 'c_1-2' WHEN close<5 THEN 'd_2-5'
   WHEN close<20 THEN 'e_5-20' ELSE 'f_>=20' END k, COUNT(*)
   FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04' GROUP BY 1 ORDER BY 1"""): print(r)

print("\n=== BJ rows: cache vs mh, all dates AND window ===")
print("cache BJ all:", c.execute("SELECT COUNT(*),COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE symbol LIKE 'BJ%'").fetchone())
print("cache BJ win:", c.execute("SELECT COUNT(*),COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE symbol LIKE 'BJ%' AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'").fetchone())
print("mh    BJ all:", m.execute("SELECT COUNT(*),COUNT(DISTINCT symbol) FROM daily_bars WHERE symbol LIKE 'BJ%'").fetchone())
print("mh    BJ win:", m.execute("SELECT COUNT(*),COUNT(DISTINCT symbol) FROM daily_bars WHERE symbol LIKE 'BJ%' AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'").fetchone())
print("cache ALL win:", c.execute("SELECT COUNT(*),COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'").fetchone())
print("mh    ALL win:", m.execute("SELECT COUNT(*),COUNT(DISTINCT symbol) FROM daily_bars WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'").fetchone())
print("\ncache BJ min/max date:", c.execute("SELECT MIN(trade_date),MAX(trade_date) FROM daily_bar_cache WHERE symbol LIKE 'BJ%'").fetchone())
print("mh    BJ min/max date:", m.execute("SELECT MIN(trade_date),MAX(trade_date) FROM daily_bars WHERE symbol LIKE 'BJ%'").fetchone())
