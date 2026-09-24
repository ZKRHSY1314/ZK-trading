import sqlite3, json
TL = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"
con = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
con.execute("PRAGMA query_only=ON")
con.execute(f"ATTACH DATABASE 'file:{MH}?mode=ro' AS mh")
c = con.cursor()
W0, W1 = '2023-09-04', '2026-09-04'

# ---- INDEPENDENT denominator: NO instruments join at all.
# Stock = exchange-prefixed 8-char symbol, excluding the two known index tickers.
SQL_NOJOIN = """
SELECT trade_date, COUNT(DISTINCT symbol) n, COUNT(*) rows
FROM daily_bar_cache
WHERE trade_date >= ? AND trade_date <= ?
  AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
  AND LENGTH(symbol)=8
  AND SUBSTR(symbol,1,2) IN ('SH','SZ','BJ')
  AND symbol NOT IN ('SH000001','SH000300')
GROUP BY 1 ORDER BY 1
"""
nojoin = c.execute(SQL_NOJOIN, (W0, W1)).fetchall()

# ---- Control: their join-based denominator
SQL_JOIN = """
SELECT d.trade_date, COUNT(DISTINCT d.symbol) n
FROM daily_bar_cache d JOIN mh.instruments i ON i.symbol=d.symbol
WHERE i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ')
  AND d.trade_date >= ? AND d.trade_date <= ?
  AND d.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
GROUP BY 1 ORDER BY 1
"""
joined = dict(c.execute(SQL_JOIN, (W0, W1)).fetchall())

print("sessions (no-join stock denominator):", len(nojoin))
print("sessions (their join denominator):   ", len(joined))
print()
print("=== first 22 sessions: date | nojoin_symbols | nojoin_rows | their_join ===")
for d, n, rows in nojoin[:22]:
    print(f"  {d}  nojoin={n:<6} rows={rows:<6} join={joined.get(d,'--')}")
print("  ...")
print("=== last 6 sessions ===")
for d, n, rows in nojoin[-6:]:
    print(f"  {d}  nojoin={n:<6} rows={rows:<6} join={joined.get(d,'--')}")
print()

# ---- Buckets, my own denominator
def bucket(n):
    if n < 100: return "A <100"
    if n < 1000: return "B 100-999"
    if n < 3000: return "C 1000-2999"
    if n < 5000: return "D 3000-4999"
    return "E >=5000"
from collections import Counter
bk = Counter(bucket(n) for _, n, _ in nojoin)
print("=== bucket distribution (MY no-join denominator) ===")
for k in sorted(bk): print(f"  {k:14} {bk[k]}")
bk2 = Counter(bucket(n) for n in joined.values())
print("=== bucket distribution (their join denominator) ===")
for k in sorted(bk2): print(f"  {k:14} {bk2[k]}")
print()

# ---- crossing points
first5000 = next(d for d, n, _ in nojoin if n >= 5000)
first1000 = next(d for d, n, _ in nojoin if n >= 1000)
first100  = next(d for d, n, _ in nojoin if n >= 100)
print("first session >=100 stocks :", first100)
print("first session >=1000 stocks:", first1000)
print("first session >=5000 stocks:", first5000)
n_ge5000 = sum(1 for _, n, _ in nojoin if n >= 5000)
n_lt5000 = sum(1 for _, n, _ in nojoin if n < 5000)
print("sessions >=5000:", n_ge5000, " sessions <5000:", n_lt5000)
print()

# ---- is the ramp monotone / contiguous? are all sub-5000 sessions at the START?
sub = [d for d, n, _ in nojoin if n < 5000]
idx = [i for i, (d, n, _) in enumerate(nojoin) if n < 5000]
print("count sub-5000 sessions:", len(sub))
print("their positional indices (0-based) min/max:", min(idx), max(idx))
print("are they a contiguous prefix?", idx == list(range(len(idx))))
print("sub-5000 sessions NOT in the leading prefix:", [nojoin[i][0] for i in idx if i >= len(idx)])
print()

# ---- ramp sub-window replication (their claim: 4682 rows / 935 symbols)
r = c.execute("""SELECT COUNT(*), COUNT(DISTINCT symbol) FROM daily_bar_cache
  WHERE trade_date BETWEEN '2024-04-09' AND '2024-06-21'
    AND LENGTH(symbol)=8 AND SUBSTR(symbol,1,2) IN ('SH','SZ','BJ')
    AND symbol NOT IN ('SH000001','SH000300')""").fetchone()
print("MY ramp sub-window 2024-04-09..2024-06-21 (no join): rows=%d distinct_symbols=%d" % r)
r2 = c.execute("""SELECT COUNT(*), COUNT(DISTINCT d.symbol) FROM daily_bar_cache d
  JOIN mh.instruments i ON i.symbol=d.symbol
  WHERE i.asset_type='stock' AND d.trade_date BETWEEN '2024-04-09' AND '2024-06-21'""").fetchone()
print("THEIR ramp sub-window (join):                        rows=%d distinct_symbols=%d" % r2)
print()

# ---- MECHANISM: when were the ramp rows physically written? live vs backfill
print("=== created_at date vs trade_date for the ramp prefix (first 15 sessions) ===")
for d, n, _ in nojoin[:15]:
    row = c.execute("""SELECT MIN(SUBSTR(created_at,1,10)), MAX(SUBSTR(created_at,1,10)), COUNT(*)
        FROM daily_bar_cache WHERE trade_date=? AND LENGTH(symbol)=8
        AND symbol NOT IN ('SH000001','SH000300')""", (d,)).fetchone()
    print(f"  trade_date={d} symbols={n:<5} created_at min={row[0]} max={row[1]} rows={row[2]}")
print()
print("=== created_at date for a mid full-market session and the final session ===")
for d in (first5000, nojoin[-1][0], nojoin[300][0]):
    row = c.execute("""SELECT MIN(SUBSTR(created_at,1,10)), MAX(SUBSTR(created_at,1,10)), COUNT(*)
        FROM daily_bar_cache WHERE trade_date=? AND LENGTH(symbol)=8""", (d,)).fetchone()
    print(f"  trade_date={d} created_at min={row[0]} max={row[1]} rows={row[2]}")
con.close()
