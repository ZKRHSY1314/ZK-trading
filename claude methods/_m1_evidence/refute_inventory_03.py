import sqlite3
OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
def show(t, rows):
    print("--", t)
    for r in rows: print("   ", r)

m = ro(MH)
print("### E. instruments taxonomy (to strip indices, count SECURITIES not rows)")
show("exchange x asset_type", m.execute(
  "SELECT exchange, asset_type, COUNT(*) FROM instruments GROUP BY 1,2 ORDER BY 3 DESC").fetchall())
stock_syms = {r[0] for r in m.execute(
  "SELECT symbol FROM instruments WHERE exchange IN ('SH','SZ','BJ')").fetchall()}
idx_syms = {r[0] for r in m.execute(
  "SELECT symbol FROM instruments WHERE exchange='INDEX'").fetchall()}
print("   stock-exchange symbols:", len(stock_syms), " index symbols:", len(idx_syms))
m.close()

c = ro(OP)
c.execute("ATTACH DATABASE ? AS mh", (f"file:{MH}?mode=ro",))
print()
print("### F. INDEPENDENT full-market onset: distinct STOCK symbols per session (indices excluded)")
rows = c.execute("""
SELECT b.trade_date,
       COUNT(DISTINCT b.symbol) AS all_syms,
       COUNT(DISTINCT CASE WHEN i.exchange IN ('SH','SZ','BJ') THEN b.symbol END) AS stock_syms,
       COUNT(DISTINCT CASE WHEN i.exchange='INDEX' THEN b.symbol END) AS index_syms,
       COUNT(DISTINCT CASE WHEN i.symbol IS NULL THEN b.symbol END) AS unmapped
FROM daily_bar_cache b LEFT JOIN mh.instruments i ON i.symbol=b.symbol
WHERE b.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
GROUP BY b.trade_date ORDER BY b.trade_date
""").fetchall()
print("   total distinct sessions in cache:", len(rows))
plateau = sorted(r[2] for r in rows)
med = plateau[len(plateau)//2]
print("   median STOCK symbols/session =", med)
for frac in (0.10, 0.50, 0.80, 0.90, 0.95):
    thr = med*frac
    first = next((r for r in rows if r[2] >= thr), None)
    print(f"   first session with stock_syms >= {frac:.0%} of median ({thr:.0f}): {first[0] if first else None}  (stock={first[2] if first else '-'} idx={first[3] if first else '-'})")
print("   FIRST 18 SESSIONS (date, all, stock, index, unmapped):")
for r in rows[:18]: print("     ", r)
print("   LAST 3 SESSIONS:", rows[-3:])

print()
print("### G. their 'stray probe' months, counted as DISTINCT SECURITIES")
show("2024-04/05/06 monthly", c.execute("""
SELECT substr(trade_date,1,7) ym, COUNT(*) rows, COUNT(DISTINCT symbol) syms,
       COUNT(DISTINCT trade_date) sessions
FROM daily_bar_cache WHERE trade_date < '2024-07-01'
  AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
GROUP BY ym ORDER BY ym""").fetchall())
show("are the 2024-04/05 symbols indices?", c.execute("""
SELECT COALESCE(i.exchange,'UNMAPPED') ex, COUNT(DISTINCT b.symbol)
FROM daily_bar_cache b LEFT JOIN mh.instruments i ON i.symbol=b.symbol
WHERE b.trade_date < '2024-06-01' AND b.trade_date GLOB '[0-9]*'
GROUP BY 1 ORDER BY 2 DESC""").fetchall())

print()
print("### H. per-symbol DEPTH measured as COUNT(DISTINCT trade_date) (not rows)")
show("cache depth quantiles + threshold counts", c.execute("""
WITH d AS (SELECT symbol, COUNT(DISTINCT trade_date) n FROM daily_bar_cache
           WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' GROUP BY symbol)
SELECT COUNT(*) symbols, MAX(n) max_depth, MIN(n) min_depth,
       SUM(n>=730) ge730, SUM(n>=600) ge600, SUM(n>=583) ge583, SUM(n>=538) ge538, SUM(n>=500) ge500
FROM d""").fetchall())
show("market_history depth", c.execute("""
WITH d AS (SELECT symbol, COUNT(DISTINCT trade_date) n FROM mh.daily_bars GROUP BY symbol)
SELECT COUNT(*) symbols, MAX(n) max_depth, SUM(n>=730) ge730, SUM(n>=600) ge600, SUM(n>=537) ge537
FROM d""").fetchall())

print()
print("### I. the missing span, and the ceiling on achievable depth")
show("sessions present inside window", c.execute("""
SELECT COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date) FROM daily_bar_cache
WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
  AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'""").fetchall())
show("sessions from full-market onset onward", c.execute("""
SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date >= '2024-06-24'
  AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'""").fetchall())
show("calendar days uncovered at window head", c.execute("""
SELECT julianday('2024-06-24')-julianday('2023-09-04') AS days_to_fullmarket,
       (julianday('2024-06-24')-julianday('2023-09-04'))/30.44 AS months,
       julianday('2024-04-09')-julianday('2023-09-04') AS days_to_any_row""").fetchall())
c.close()
