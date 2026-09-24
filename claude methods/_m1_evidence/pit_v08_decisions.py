import sqlite3, json
OP = r"D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{OP}?mode=ro", uri=True); c.execute("PRAGMA query_only=ON")
c.execute("ATTACH DATABASE 'file:D:/codex-A股交易/market_history.sqlite3?mode=ro' AS mh")
q=lambda s,*a: c.execute(s,a).fetchall()
def one(s,*a):
    r=c.execute(s,a).fetchone(); return r[0] if r else None

print("I. FULL-POPULATION MEASURED RESTATEMENT (value actually changed)")
s = """
SELECT COUNT(*) n,
       SUM(CASE WHEN ABS(b.close-h.close)>1e-6 OR ABS(b.open-h.open)>1e-6
                  OR ABS(b.high-h.high)>1e-6 OR ABS(b.low-h.low)>1e-6 THEN 1 ELSE 0 END) ohlc_changed,
       SUM(CASE WHEN ABS(b.close-h.close)>1e-6 THEN 1 ELSE 0 END) close_changed,
       COUNT(DISTINCT b.symbol) nsym
FROM daily_bar_cache b JOIN mh.daily_bars h
  ON h.symbol=b.symbol AND h.trade_date=b.trade_date AND h.adjustment_mode='qfq'
WHERE b.adjustment_mode='qfq'
  AND substr(replace(h.updated_at,'T',' '),1,10) < '2026-09-01'
"""
n, oc, cc, ns = q(s)[0]
print(f"   comparable pairs (MH still holds a pre-Sep vintage): {n:,} over {ns:,} symbols")
print(f"   OHLC changed : {oc:,} ({oc/n*100:.2f}%)")
print(f"   close changed: {cc:,} ({cc/n*100:.2f}%)")
print(f"   cache rows with NO surviving older vintage anywhere (unmeasurable): "
      f"{one('SELECT COUNT(*) FROM daily_bar_cache')-n:,}")
print()

print("J. DECISION UNIVERSE vs THE 2026-09-03 REWRITE  (degeneracy test)")
tot = one("SELECT COUNT(*) FROM (SELECT DISTINCT decision_id,subject FROM forecast_decisions WHERE scope='stock')")
print(f"   stock-scope distinct (decision_id,subject) pairs: {tot:,}")
for cut in ('2026-09-03','2026-09-04'):
    k = one("SELECT COUNT(*) FROM (SELECT DISTINCT decision_id,subject FROM forecast_decisions WHERE scope='stock' AND substr(decision_cutoff,1,10) < ?)", cut)
    print(f"   pairs with decision_cutoff BEFORE {cut}: {k:,}  ({k/tot*100:.2f}%)")
print()
print("   stock-scope pairs by decision_cutoff day:")
for r in q("""SELECT substr(decision_cutoff,1,10) d, COUNT(*) npairs
              FROM (SELECT DISTINCT decision_id,subject,decision_cutoff FROM forecast_decisions WHERE scope='stock')
              GROUP BY 1 ORDER BY 1"""):
    print("     ", r)
print()
print("K. DO THE SUBJECTS EVEN RESOLVE TO BARS?")
print("   distinct stock subjects:", one("SELECT COUNT(DISTINCT subject) FROM forecast_decisions WHERE scope='stock'"))
print("   sample subjects:", [r[0] for r in q("SELECT DISTINCT subject FROM forecast_decisions WHERE scope='stock' LIMIT 10")])
print("   subjects present in daily_bar_cache:", one("""SELECT COUNT(*) FROM (SELECT DISTINCT subject FROM forecast_decisions WHERE scope='stock'
        AND subject IN (SELECT DISTINCT symbol FROM daily_bar_cache))"""))
print()
print("   one decision's features_json keys:")
r = one("SELECT features_json FROM forecast_decisions WHERE scope='stock' LIMIT 1")
try:
    d=json.loads(r); print("     ", list(d.keys())[:25])
except Exception as e: print("     unparsed:", str(r)[:200])
print("   one decision's evidence_json (truncated):")
r = one("SELECT evidence_json FROM forecast_decisions WHERE scope='stock' LIMIT 1")
print("     ", str(r)[:400])
c.close()
