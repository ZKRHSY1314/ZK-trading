import sqlite3, textwrap
MH='file:D:/codex-A股交易/market_history.sqlite3?mode=ro'
c=sqlite3.connect(MH,uri=True); c.row_factory=sqlite3.Row
def q(label,sql,params=()):
    print('='*78); print(label); print(textwrap.dedent(sql).strip()); print('-'*78)
    for r in c.execute(sql,params): print(dict(r))
    print()

# C1: exact median / p95 / max lag, STOCKS ONLY, via ordered offset (no approximation)
n=c.execute("SELECT COUNT(*) FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol WHERE i.exchange IN ('SH','SZ','BJ')").fetchone()[0]
for name,off in (('p50',n//2),('p95',int(n*0.95)),('max',n-1),('min',0)):
    v=c.execute("""SELECT CAST(julianday(substr(b.available_at,1,10))-julianday(b.trade_date) AS INT) lag
                   FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
                   WHERE i.exchange IN ('SH','SZ','BJ')
                   ORDER BY lag LIMIT 1 OFFSET ?""",(off,)).fetchone()[0]
    print(f'C1 exact {name} lag (calendar days, stocks only, n={n}): {v}')
print()

# C2: FUNCTIONAL PIT TEST -- walk the research window, ask what a PIT query returns.
print('='*78)
print('C2 FUNCTIONAL PIT REPLAY: rows/securities visible under a correct PIT filter')
print("SQL per cutoff: SELECT COUNT(*), COUNT(DISTINCT b.symbol) FROM daily_bars b JOIN instruments i")
print("  ON i.symbol=b.symbol WHERE i.exchange IN ('SH','SZ','BJ')")
print("  AND b.trade_date <= date(:cut) AND b.available_at <= :cut")
print('-'*78)
cuts=['2023-09-04T15:00:00','2024-06-28T15:00:00','2025-01-02T15:00:00','2025-06-30T15:00:00',
      '2026-01-05T15:00:00','2026-07-15T14:15:17','2026-07-15T14:15:19','2026-07-31T15:00:00',
      '2026-09-02T15:00:00','2026-09-03T20:00:00','2026-09-04T15:00:00']
sql="""SELECT COUNT(*) rows_visible, COUNT(DISTINCT b.symbol) syms_visible
       FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
       WHERE i.exchange IN ('SH','SZ','BJ')
         AND b.trade_date <= date(?) AND b.available_at <= ?"""
sql_nopit="""SELECT COUNT(*) rows_naive, COUNT(DISTINCT b.symbol) syms_naive
       FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
       WHERE i.exchange IN ('SH','SZ','BJ') AND b.trade_date <= date(?)"""
for cut in cuts:
    a=c.execute(sql,(cut,cut)).fetchone(); b=c.execute(sql_nopit,(cut,)).fetchone()
    print(f'cutoff={cut}  PIT_rows={a["rows_visible"]:>9}  PIT_syms={a["syms_visible"]:>5} '
          f'| no-PIT_rows={b["rows_naive"]:>9}  no-PIT_syms={b["syms_naive"]:>5} '
          f'| PIT/no-PIT rows = {(100.0*a["rows_visible"]/b["rows_naive"] if b["rows_naive"] else float("nan")):6.2f}%')
print()

# C3: does the PIT column ever *withhold* a bar that trade_date alone would admit,
#     other than by the two bulk step-functions? (i.e. is it monotone-informative?)
q('C3 distinct available_at values per fetch calendar day (is it a clock or a step function?)', """
SELECT substr(available_at,1,10) AS day, COUNT(*) rows,
       COUNT(DISTINCT available_at) distinct_ts,
       COUNT(DISTINCT symbol) syms, MIN(trade_date) td_lo, MAX(trade_date) td_hi
FROM daily_bars GROUP BY day ORDER BY day
""")
c.close()
