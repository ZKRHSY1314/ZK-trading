import sqlite3
OPS = r"D:/codex-A股交易/trading_local.sqlite3"
HIS = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{OPS}?mode=ro", uri=True)
c.execute("ATTACH DATABASE ? AS mh", (f"file:{HIS}?mode=ro",))
c.execute("PRAGMA temp_store=MEMORY"); c.execute("PRAGMA cache_size=-400000")
def q(label, sql, lim=40):
    print("="*100); print(label); print("SQL:", " ".join(sql.split()))
    rows=c.execute(sql).fetchall()
    for r in rows[:lim]: print("   ", r)
    if len(rows)>lim: print(f"    ...{len(rows)} rows")
    return rows

# 12. REGIME test: count day-over-day ratio BREAKS >0.2% (tolerant to 2dp quantization)
q("12. Ratio-regime breaks per symbol (break = consecutive-day ratio move >0.2%)", """
WITH j AS (
  SELECT d.symbol s, d.trade_date td, d.close/b.close ratio,
         CASE WHEN d.source=b.provider THEN 1 ELSE 0 END same_prov
  FROM daily_bar_cache d JOIN mh.daily_bars b
    ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
  WHERE d.quality_status='ready' AND d.adjustment_mode='qfq' AND b.close>0 AND d.close>0
), br AS (
  SELECT s, td, ratio, LAG(ratio) OVER (PARTITION BY s ORDER BY td) prev, same_prov FROM j
), agg AS (
  SELECT s, COUNT(*) n,
         SUM(CASE WHEN prev IS NOT NULL AND ABS(ratio/prev-1)>0.002 THEN 1 ELSE 0 END) breaks,
         MIN(same_prov) minp, MAX(same_prov) maxp
  FROM br GROUP BY s HAVING n>20
)
SELECT CASE WHEN breaks=0 THEN 'a 0 breaks (constant ratio within 0.2%)'
            WHEN breaks<=2 THEN 'b 1-2 breaks (piecewise: corp-action / re-anchor)'
            WHEN breaks<=10 THEN 'c 3-10 breaks'
            ELSE 'd >10 breaks (genuinely different shape)' END AS regime,
  COUNT(*) symbols, SUM(n) bars,
  ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER (),2) pct_symbols
FROM agg GROUP BY 1 ORDER BY 1
""")

# 13. Same, split by whether the two stores used the SAME provider
q("13. Regime breaks split by same-vs-different provider", """
WITH j AS (
  SELECT d.symbol s, d.trade_date td, d.close/b.close ratio,
         CASE WHEN d.source=b.provider THEN 1 ELSE 0 END sp
  FROM daily_bar_cache d JOIN mh.daily_bars b
    ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
  WHERE d.quality_status='ready' AND d.adjustment_mode='qfq' AND b.close>0 AND d.close>0
), br AS (SELECT s, td, ratio, LAG(ratio) OVER (PARTITION BY s ORDER BY td) prev, sp FROM j),
agg AS (SELECT s, COUNT(*) n, AVG(sp) frac_same,
        SUM(CASE WHEN prev IS NOT NULL AND ABS(ratio/prev-1)>0.002 THEN 1 ELSE 0 END) breaks
        FROM br GROUP BY s HAVING n>20)
SELECT CASE WHEN frac_same=1 THEN 'always same provider'
            WHEN frac_same=0 THEN 'always different provider'
            ELSE 'mixed' END AS prov,
  COUNT(*) symbols,
  SUM(CASE WHEN breaks=0 THEN 1 ELSE 0 END) b0,
  SUM(CASE WHEN breaks BETWEEN 1 AND 2 THEN 1 ELSE 0 END) b1_2,
  SUM(CASE WHEN breaks BETWEEN 3 AND 10 THEN 1 ELSE 0 END) b3_10,
  SUM(CASE WHEN breaks>10 THEN 1 ELSE 0 END) b_gt10
FROM agg GROUP BY 1 ORDER BY 2 DESC
""")

# 14. Their SZ000001 spot check -- what provider pair, and how big is it really?
q("14. SZ000001 provider pair + ratio spread", """
SELECT d.source, b.provider, COUNT(*) n,
  ROUND(MIN(d.close/b.close),6) min_r, ROUND(MAX(d.close/b.close),6) max_r,
  ROUND(100.0*MAX(ABS(d.close-b.close)/b.close),4) worst_pct
FROM daily_bar_cache d JOIN mh.daily_bars b
  ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
WHERE d.symbol='SZ000001' AND d.quality_status='ready' AND d.adjustment_mode='qfq' AND b.close>0
GROUP BY 1,2
""")

# 15. Staleness signature: ratio==1 at the tail, constant!=1 earlier?
q("15. How many symbols end at ratio~1.0 but differ earlier (stale-history signature)", """
WITH j AS (SELECT d.symbol s, d.trade_date td, d.close/b.close ratio
  FROM daily_bar_cache d JOIN mh.daily_bars b
    ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
  WHERE d.quality_status='ready' AND d.adjustment_mode='qfq' AND b.close>0 AND d.close>0),
k AS (SELECT s, COUNT(*) n,
   SUM(CASE WHEN ABS(ratio-1)<0.0005 THEN 1 ELSE 0 END) n_unity,
   MAX(CASE WHEN td=(SELECT MAX(td) FROM j j2 WHERE j2.s=j.s) THEN ratio END) last_ratio
   FROM j GROUP BY s HAVING n>20)
SELECT CASE WHEN ABS(last_ratio-1)<0.0005 AND 1.0*n_unity/n < 0.95 THEN 'a recent agrees, history differs (STALE ADJUSTMENT)'
            WHEN 1.0*n_unity/n >= 0.95 THEN 'b agrees throughout'
            ELSE 'c differs at the tail too' END AS sig,
  COUNT(*) symbols, SUM(n) bars
FROM k GROUP BY 1 ORDER BY 1
""")
c.close()
