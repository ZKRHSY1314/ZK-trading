import sqlite3, json
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c
mh = ro(MH); tl = ro(TL)
def q(conn,sql,args=()):
    return [dict(r) for r in conn.execute(sql,args).fetchall()]
def one(conn,sql,args=()):
    r = conn.execute(sql,args).fetchone()
    return r[0] if r else None

print("="*78); print("A. DENOMINATOR + NULL/FORMAT AUDIT (market_history.daily_bars)"); print("="*78)
print("SQL: SELECT COUNT(*), SUM(available_at IS NULL), SUM(fetched_at IS NULL),")
print("     COUNT(DISTINCT symbol), COUNT(DISTINCT symbol||'|'||trade_date) FROM daily_bars")
r = q(mh,"""SELECT COUNT(*) total,
       SUM(CASE WHEN available_at IS NULL THEN 1 ELSE 0 END) null_avail,
       SUM(CASE WHEN fetched_at  IS NULL THEN 1 ELSE 0 END) null_fetch,
       COUNT(DISTINCT symbol) nsym,
       COUNT(DISTINCT symbol||'|'||trade_date) nsymdate,
       COUNT(DISTINCT adjustment_mode) nmodes
FROM daily_bars""")[0]
print(json.dumps(r,indent=2))

print("\n-- format check: rows where julianday(substr(available_at,1,10)) IS NULL (would silently drop from their filter)")
print("SQL: SELECT COUNT(*) FROM daily_bars WHERE available_at IS NULL OR julianday(substr(available_at,1,10)) IS NULL")
print("unparseable_or_null =", one(mh,"SELECT COUNT(*) FROM daily_bars WHERE available_at IS NULL OR julianday(substr(available_at,1,10)) IS NULL"))
print("\n-- sample raw available_at values (verbatim, to check ISO format / timezone suffix)")
for row in q(mh,"SELECT available_at, fetched_at, created_at, updated_at, trade_date, symbol FROM daily_bars LIMIT 5"):
    print("  ",row)

print("\n"+"="*78); print("B. IS available_at LITERALLY THE SAME VALUE AS fetched_at? (row-level identity)"); print("="*78)
print("SQL: SELECT COUNT(*) FROM daily_bars WHERE available_at IS NOT fetched_at")
print("rows_where_available_at_differs_from_fetched_at =", one(mh,"SELECT COUNT(*) FROM daily_bars WHERE available_at IS NOT fetched_at"))
print("SQL: SELECT COUNT(*) FROM daily_bars WHERE available_at IS NOT updated_at")
print("rows_where_available_at_differs_from_updated_at =", one(mh,"SELECT COUNT(*) FROM daily_bars WHERE available_at IS NOT updated_at"))

print("\n"+"="*78); print("C. POSITIVE TEST: how many bars have a PLAUSIBLE point-in-time stamp?"); print("="*78)
print("A daily bar becomes available after the close on trade_date. A PIT-correct")
print("available_at must therefore fall in [trade_date, trade_date + N days] for small N.")
print("SQL: SELECT CAST(julianday(substr(available_at,1,10)) - julianday(trade_date) AS INT) lag, COUNT(*) ...")
for n in (0,1,2,3,7,30,90,365):
    c = one(mh,"""SELECT COUNT(*) FROM daily_bars
                  WHERE available_at IS NOT NULL
                    AND julianday(substr(available_at,1,10)) - julianday(trade_date) BETWEEN 0 AND ?""",(n,))
    print(f"   lag in [0,{n:>3}] days : {c:>10,}  ({100.0*c/r['total']:.4f}% of {r['total']:,})")
c_neg = one(mh,"SELECT COUNT(*) FROM daily_bars WHERE julianday(substr(available_at,1,10)) - julianday(trade_date) < 0")
print(f"   lag NEGATIVE (avail before trade_date, impossible) : {c_neg:,}")

print("\n-- full lag distribution bucketed")
print("SQL: SELECT CASE ... END bucket, COUNT(*) FROM daily_bars GROUP BY bucket")
for row in q(mh,"""SELECT CASE
   WHEN available_at IS NULL THEN 'z_null'
   WHEN julianday(substr(available_at,1,10)) - julianday(trade_date) < 0 THEN 'a_negative'
   WHEN julianday(substr(available_at,1,10)) - julianday(trade_date) <= 1 THEN 'b_0to1d'
   WHEN julianday(substr(available_at,1,10)) - julianday(trade_date) <= 7 THEN 'c_2to7d'
   WHEN julianday(substr(available_at,1,10)) - julianday(trade_date) <= 30 THEN 'd_8to30d'
   WHEN julianday(substr(available_at,1,10)) - julianday(trade_date) <= 365 THEN 'e_31to365d'
   ELSE 'f_over365d' END bucket, COUNT(*) n
FROM daily_bars GROUP BY bucket ORDER BY bucket"""):
    print(f"   {row['bucket']:<12} {row['n']:>10,}  {100.0*row['n']/r['total']:6.2f}%")

print("\n"+"="*78); print("D. DISTINCT available_at VALUES (not just days) — cardinality test"); print("="*78)
print("SQL: SELECT COUNT(DISTINCT available_at), COUNT(DISTINCT substr(available_at,1,10)) FROM daily_bars")
print(q(mh,"SELECT COUNT(DISTINCT available_at) distinct_full, COUNT(DISTINCT substr(available_at,1,10)) distinct_days FROM daily_bars")[0])
print("\n-- every distinct available_at DAY with row count and the trade_date range it covers")
print("SQL: SELECT substr(available_at,1,10) d, COUNT(*) n, MIN(trade_date), MAX(trade_date), COUNT(DISTINCT symbol) FROM daily_bars GROUP BY d")
for row in q(mh,"""SELECT substr(available_at,1,10) d, COUNT(*) n,
        MIN(trade_date) min_td, MAX(trade_date) max_td, COUNT(DISTINCT symbol) nsym
        FROM daily_bars GROUP BY d ORDER BY n DESC"""):
    print(f"   {row['d']}  n={row['n']:>9,}  trade_date {row['min_td']} .. {row['max_td']}  symbols={row['nsym']:,}")
mh.close(); tl.close()
