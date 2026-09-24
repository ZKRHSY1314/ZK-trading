import sqlite3
OPS = r"D:/codex-A股交易/trading_local.sqlite3"
HIS = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{OPS}?mode=ro", uri=True)
c.execute("ATTACH DATABASE ? AS mh", (f"file:{HIS}?mode=ro",))
c.execute("PRAGMA temp_store=MEMORY"); c.execute("PRAGMA cache_size=-400000")
def q(label, sql, lim=60):
    print("="*100); print(label); print("SQL:", " ".join(sql.split()))
    rows = c.execute(sql).fetchall()
    for r in rows[:lim]: print("   ", r)
    if len(rows)>lim: print(f"    ...{len(rows)} rows")
    return rows

# Exact symbol denominator: affected vs total IN THE JOIN
q("4. Affected-symbol count with the CORRECT denominator (join = 5,560 symbols)", """
SELECT COUNT(*) AS symbols_in_join,
       SUM(CASE WHEN n_halfcent>0 THEN 1 ELSE 0 END) AS syms_any_halfcent,
       SUM(CASE WHEN n_gt1pct>0 THEN 1 ELSE 0 END)  AS syms_any_gt1pct,
       SUM(CASE WHEN 1.0*n_gt1pct/n > 0.10 THEN 1 ELSE 0 END) AS syms_gt1pct_on_over_10pct_of_bars
FROM (SELECT d.symbol, COUNT(*) n,
        SUM(CASE WHEN ABS(d.close-b.close)>0.005 THEN 1 ELSE 0 END) n_halfcent,
        SUM(CASE WHEN ABS(d.close-b.close)/b.close>0.01 THEN 1 ELSE 0 END) n_gt1pct
      FROM daily_bar_cache d JOIN mh.daily_bars b
        ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
      WHERE d.quality_status='ready' AND d.adjustment_mode='qfq' AND b.close>0
      GROUP BY 1)
""")

# Are any join symbols NOT stocks (index contamination)?
q("5. Index / non-instrument contamination in the join", """
SELECT CASE WHEN i.symbol IS NULL THEN 'NOT in instruments' ELSE i.asset_type END AS kind,
       COUNT(DISTINCT j.symbol) AS syms, SUM(j.n) AS rows
FROM (SELECT d.symbol, COUNT(*) n FROM daily_bar_cache d
      JOIN mh.daily_bars b ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
      WHERE d.quality_status='ready' AND d.adjustment_mode='qfq' GROUP BY 1) j
LEFT JOIN mh.instruments i ON i.symbol=j.symbol GROUP BY 1
""")

# THE DECISIVE TEST: do DAILY RETURNS agree? (level/anchor artifact vs real shape defect)
q("6. DECISIVE: same-day close-to-close RETURN agreement on consecutive shared bars", """
WITH j AS (
  SELECT d.symbol s, d.trade_date td, d.close dc, b.close bc
  FROM daily_bar_cache d JOIN mh.daily_bars b
    ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
  WHERE d.quality_status='ready' AND d.adjustment_mode='qfq' AND b.close>0 AND d.close>0
), r AS (
  SELECT s, td,
    dc/LAG(dc) OVER (PARTITION BY s ORDER BY td) AS dret,
    bc/LAG(bc) OVER (PARTITION BY s ORDER BY td) AS bret
  FROM j
)
SELECT CASE
   WHEN dret IS NULL OR bret IS NULL THEN 'z first-bar (no prior)'
   WHEN ABS(dret-bret) < 0.00001 THEN 'a returns match  <0.001%'
   WHEN ABS(dret-bret) < 0.0001  THEN 'b returns match  <0.01%'
   WHEN ABS(dret-bret) < 0.001   THEN 'c returns differ <0.1%'
   WHEN ABS(dret-bret) < 0.01    THEN 'd returns differ <1%'
   ELSE 'e returns differ >=1%' END AS bucket,
 COUNT(*), ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER (),4) AS pct, COUNT(DISTINCT s) syms
FROM r GROUP BY 1 ORDER BY 1
""")
c.close()
