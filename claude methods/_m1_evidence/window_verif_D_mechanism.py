import sqlite3
from collections import Counter
TL = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"
con = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
con.execute("PRAGMA query_only=ON")
con.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")
c = con.cursor()

print("=== per-symbol bar COUNT distribution (stocks only, valid dates) ===")
SQL = """SELECT symbol, COUNT(*) n, MIN(trade_date) mn, MAX(trade_date) mx
 FROM daily_bar_cache
 WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
   AND LENGTH(symbol)=8 AND SUBSTR(symbol,1,2) IN ('SH','SZ','BJ')
   AND symbol NOT IN ('SH000001','SH000300')
 GROUP BY 1"""
rows = c.execute(SQL).fetchall()
cnts = sorted(r[1] for r in rows)
N = len(cnts)
def pct(p): return cnts[min(N-1,int(p/100*N))]
print(f"  symbols={N}  min={cnts[0]} p1={pct(1)} p5={pct(5)} p25={pct(25)} median={pct(50)} p75={pct(75)} p95={pct(95)} max={cnts[-1]}")
print("  TOP-10 most common per-symbol bar counts:", Counter(cnts).most_common(10))
print()

print("=== per-symbol EARLIEST date: top 12 most common first dates ===")
for d, k in Counter(r[2] for r in rows).most_common(12):
    print(f"   first_date={d}  n_symbols={k}")
print()

print("=== correlation: symbols whose FIRST bar is in the ramp (before 2024-06-24) ===")
ramp = [r for r in rows if r[2] < '2024-06-24']
main = [r for r in rows if r[2] >= '2024-06-24']
def summ(tag, s):
    if not s: print(f"  {tag}: none"); return
    cc = sorted(x[1] for x in s)
    print(f"  {tag}: n_symbols={len(s)} bar_count median={cc[len(cc)//2]} min={cc[0]} max={cc[-1]}")
summ("first-bar BEFORE 2024-06-24 (ramp symbols)", ramp)
summ("first-bar ON/AFTER 2024-06-24            ", main)
print()

print("=== do ramp symbols also have CONTINUOUS data after 2024-06-24? (10 samples) ===")
for sym, n, mn, mx in sorted(ramp, key=lambda r: r[2])[:10]:
    after = c.execute("""SELECT COUNT(*) FROM daily_bar_cache WHERE symbol=? AND trade_date>='2024-06-24'
      AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'""", (sym,)).fetchone()[0]
    before = n - after
    print(f"   {sym}  total={n}  bars_in_ramp={before}  bars_after={after}  first={mn} last={mx}")
print()

print("=== listing dates of ramp symbols: are they new listings? ===")
r = c.execute("""SELECT COUNT(*) FROM mh.instruments i WHERE i.list_date >= '2024-04-09'""").fetchone()[0]
print("  instruments listed on/after 2024-04-09:", r)
print("  ramp symbols (first bar < 2024-06-24):", len(ramp))
print()

print("=== created_at census across the whole cache (ingest wave shape) ===")
for r in c.execute("""SELECT SUBSTR(created_at,1,7) ym, COUNT(*) FROM daily_bar_cache GROUP BY 1 ORDER BY 1"""):
    print("   created_at month", r[0], "rows", r[1])
print()

print("=== market_history.daily_bars: MY independent per-session census ===")
mh_rows = c.execute("""SELECT trade_date, COUNT(DISTINCT symbol) n FROM mh.daily_bars
  WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'
    AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
    AND LENGTH(symbol)=8 AND SUBSTR(symbol,1,2) IN ('SH','SZ','BJ')
  GROUP BY 1 ORDER BY 1""").fetchall()
print("  mh sessions in window:", len(mh_rows))
print("  mh min date:", mh_rows[0], " max:", mh_rows[-1])
ge = [d for d, n in mh_rows if n >= 5000]
print("  mh first session >=5000 stocks:", ge[0] if ge else None, " count>=5000:", len(ge))
print("  mh adjustment_mode census:", c.execute("SELECT adjustment_mode, COUNT(*) FROM mh.daily_bars GROUP BY 1").fetchall())
con.close()
