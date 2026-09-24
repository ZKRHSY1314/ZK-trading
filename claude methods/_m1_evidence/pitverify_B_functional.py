import sqlite3
MH = r"D:/codex-A股交易/market_history.sqlite3"
con = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
def show(t, sql, p=()):
    print("="*78); print(t); print("SQL:", " ".join(sql.split()))
    for r in con.execute(sql,p).fetchall(): print("   ", dict(r))

# A. Index contamination check -- are any daily_bars symbols indices?
show("A INDEX CONTAMINATION: exchange mix of symbols actually present in daily_bars", """
SELECT i.exchange, i.asset_type, COUNT(DISTINCT b.symbol) AS symbols, COUNT(*) AS bars
FROM daily_bars b LEFT JOIN instruments i ON i.symbol=b.symbol
GROUP BY i.exchange, i.asset_type ORDER BY bars DESC""")

# B. Is the 30-day threshold cherry-picked? Full lag distribution, independent buckets.
show("B FULL LAG DISTRIBUTION (independent of any 30-day threshold)", """
SELECT CASE
    WHEN julianday(substr(available_at,1,10))-julianday(trade_date) <= 1   THEN 'a_lag_0_1d'
    WHEN julianday(substr(available_at,1,10))-julianday(trade_date) <= 7   THEN 'b_lag_2_7d'
    WHEN julianday(substr(available_at,1,10))-julianday(trade_date) <= 30  THEN 'c_lag_8_30d'
    WHEN julianday(substr(available_at,1,10))-julianday(trade_date) <= 180 THEN 'd_lag_31_180d'
    WHEN julianday(substr(available_at,1,10))-julianday(trade_date) <= 365 THEN 'e_lag_181_365d'
    ELSE 'f_lag_over_365d' END AS bucket,
  COUNT(*) AS bars, ROUND(100.0*COUNT(*)/2787736,3) AS pct,
  MIN(trade_date) AS min_td, MAX(trade_date) AS max_td
FROM daily_bars GROUP BY bucket ORDER BY bucket""")

# C. Are the "fresh" 4.58% genuinely point-in-time, or just bars whose trade_date
#    happens to sit next to the two bulk ingest dates?
show("C ARE THE FRESH ROWS A REAL PIT SUBSET? trade_date range of lag<=30d rows", """
SELECT COUNT(*) AS fresh_bars, MIN(trade_date) AS earliest_fresh_td, MAX(trade_date) AS latest_fresh_td,
       COUNT(DISTINCT substr(available_at,1,10)) AS distinct_avail_days
FROM daily_bars
WHERE substr(available_at,1,10) <= date(trade_date,'+30 day')""")

# D. THE DECISIVE FUNCTIONAL TEST: can you reconstruct an as-of view at any cutoff
#    inside the research window? A true PIT store returns ~all bars up to the cutoff.
print("="*78)
print("D AS-OF RECONSTRUCTION TEST -- bars visible under `available_at <= cutoff`")
print("SQL (per cutoff): SELECT COUNT(*) FROM daily_bars WHERE available_at <= :cutoff AND trade_date <= :cutoff_date")
print(f"{'cutoff':<14}{'visible_PIT':>14}{'bars_actually_dated<=cutoff':>30}{'recovered_pct':>15}")
for c in ['2024-06-30','2024-12-31','2025-06-30','2025-12-31','2026-03-31','2026-06-30','2026-07-14','2026-07-15','2026-09-03']:
    vis = con.execute("SELECT COUNT(*) FROM daily_bars WHERE available_at <= ? AND trade_date <= ?", (c+"T23:59:59", c)).fetchone()[0]
    tot = con.execute("SELECT COUNT(*) FROM daily_bars WHERE trade_date <= ?", (c,)).fetchone()[0]
    pct = (100.0*vis/tot) if tot else float('nan')
    print(f"{c:<14}{vis:>14,}{tot:>30,}{pct:>14.2f}%")

# E. Same test measured in SECURITIES (not rows) -- universe reconstruction framing
print("="*78)
print("E AS-OF UNIVERSE TEST -- distinct symbols visible under `available_at <= cutoff`")
print("SQL: SELECT COUNT(DISTINCT symbol) FROM daily_bars WHERE available_at<=? AND trade_date BETWEEN date(?, '-30 day') AND ?")
for c in ['2024-12-31','2025-06-30','2025-12-31','2026-06-30','2026-07-15']:
    vis = con.execute("SELECT COUNT(DISTINCT symbol) FROM daily_bars WHERE available_at<=? AND trade_date BETWEEN date(?, '-30 day') AND ?", (c+"T23:59:59", c, c)).fetchone()[0]
    tot = con.execute("SELECT COUNT(DISTINCT symbol) FROM daily_bars WHERE trade_date BETWEEN date(?, '-30 day') AND ?", (c, c)).fetchone()[0]
    print(f"   cutoff {c}: symbols_visible_PIT={vis:,}  symbols_truly_trading={tot:,}")

# F. Cross-check the claim's own headline number by a THIRD method (no julianday, no date())
show("F THIRD METHOD -- integer date keys, pure arithmetic on YYYYMMDD ints", """
SELECT COUNT(*) AS bars_avail_more_than_30d_later
FROM daily_bars
WHERE (CAST(substr(available_at,1,4) AS INT)*372
      + CAST(substr(available_at,6,2) AS INT)*31
      + CAST(substr(available_at,9,2) AS INT))
    - (CAST(substr(trade_date,1,4) AS INT)*372
      + CAST(substr(trade_date,6,2) AS INT)*31
      + CAST(substr(trade_date,9,2) AS INT)) > 31""")
con.close()
