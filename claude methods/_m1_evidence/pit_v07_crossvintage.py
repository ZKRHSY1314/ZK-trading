import sqlite3
OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
c.execute("PRAGMA query_only=ON")
c.execute("ATTACH DATABASE 'file:D:/codex-A股交易/market_history.sqlite3?mode=ro' AS mh")
c.execute("PRAGMA mh.query_only=ON")
q = lambda s,*a: c.execute(s,a).fetchall()
def one(s,*a):
    r=c.execute(s,a).fetchone(); return r[0] if r else None

print("H. CONTROLLED CROSS-VINTAGE TEST")
print("   market_history rows last written 2026-07-15 preserve the JULY vintage.")
print("   daily_bar_cache rows last written 2026-09-03 hold the SEPTEMBER rewrite.")
print()

CTRL = """
SELECT COUNT(*) n,
       SUM(CASE WHEN ABS(b.close - h.close) <= 1e-6 THEN 1 ELSE 0 END) same_close,
       SUM(CASE WHEN ABS(b.close - h.close) > 0.005*ABS(h.close) THEN 1 ELSE 0 END) close_gt50bp,
       SUM(CASE WHEN b.volume IS NULL OR h.volume IS NULL THEN 0
                WHEN ABS(b.volume-h.volume) <= 1e-6 THEN 1 ELSE 0 END) same_vol,
       AVG(ABS(b.close-h.close)/NULLIF(ABS(h.close),0)) mean_abs_rel
FROM daily_bar_cache b
JOIN mh.daily_bars h
  ON h.symbol=b.symbol AND h.trade_date=b.trade_date AND h.adjustment_mode='qfq'
WHERE b.adjustment_mode='qfq'
  AND substr(replace(h.updated_at,'T',' '),1,10)='2026-07-15'
  AND substr(replace(b.updated_at,'T',' '),1,10)=?
"""
print("   CONTROL  (cache rows also last written 2026-07-15 -> should agree if MH-July mirrors cache-July):")
r = q(CTRL, '2026-07-15')[0]
n,sc,gt,sv,mar = r
if n: print(f"      pairs={n:,}  identical_close={sc:,} ({sc/n*100:.2f}%)  close moved >50bp={gt:,} ({gt/n*100:.2f}%)  identical_volume={sv:,} ({sv/n*100:.2f}%)  mean|rel diff|={mar}")
else: print("      pairs=0")
print()
print("   TREATMENT (cache rows last written 2026-09-03 = the mass rewrite):")
r = q(CTRL, '2026-09-03')[0]
n,sc,gt,sv,mar = r
if n: print(f"      pairs={n:,}  identical_close={sc:,} ({sc/n*100:.2f}%)  close moved >50bp={gt:,} ({gt/n*100:.2f}%)  identical_volume={sv:,} ({sv/n*100:.2f}%)  mean|rel diff|={mar}")
else: print("      pairs=0")
print()
print("   magnitude buckets for the 2026-09-03 rewrite vs July vintage:")
for r in q("""
SELECT CASE WHEN ABS(b.close-h.close) <= 1e-6 THEN 'a. identical'
            WHEN ABS(b.close-h.close) <= 0.0005*ABS(h.close) THEN 'b. <=5bp'
            WHEN ABS(b.close-h.close) <= 0.005 *ABS(h.close) THEN 'c. 5-50bp'
            WHEN ABS(b.close-h.close) <= 0.02  *ABS(h.close) THEN 'd. 0.5-2%'
            WHEN ABS(b.close-h.close) <= 0.10  *ABS(h.close) THEN 'e. 2-10%'
            ELSE 'f. >10%' END bucket, COUNT(*) n, COUNT(DISTINCT b.symbol) nsym
FROM daily_bar_cache b JOIN mh.daily_bars h
  ON h.symbol=b.symbol AND h.trade_date=b.trade_date AND h.adjustment_mode='qfq'
WHERE b.adjustment_mode='qfq'
  AND substr(replace(h.updated_at,'T',' '),1,10)='2026-07-15'
  AND substr(replace(b.updated_at,'T',' '),1,10)='2026-09-03'
GROUP BY 1 ORDER BY 1"""):
    print("     ", r)
c.close()
