import sqlite3, math
OPS = r"D:/codex-A股交易/trading_local.sqlite3"
HIST= r"D:/codex-A股交易/market_history.sqlite3"
con = sqlite3.connect(f"file:{OPS}?mode=ro", uri=True)
con.execute(f"ATTACH DATABASE 'file:{HIST}?mode=ro' AS mh")
print("sqlite:", con.execute("select sqlite_version()").fetchone()[0])

# ---------- D1: RETURN equivalence (what a backtest actually consumes) ----------
SQL_RET = """
WITH j AS (
  SELECT d.symbol s, d.trade_date td, d.close dc, b.close bc
  FROM daily_bar_cache d JOIN mh.daily_bars b
    ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
  WHERE d.quality_status='ready' AND d.adjustment_mode='qfq'),
r AS (
  SELECT s, td,
         dc/NULLIF(LAG(dc) OVER (PARTITION BY s ORDER BY td),0)-1 ops_ret,
         bc/NULLIF(LAG(bc) OVER (PARTITION BY s ORDER BY td),0)-1 hist_ret,
         dc, bc, LAG(dc) OVER (PARTITION BY s ORDER BY td) pdc
  FROM j)
SELECT COUNT(*) n_ret_pairs,
  SUM(CASE WHEN ABS(ops_ret-hist_ret)<=1e-6 THEN 1 ELSE 0 END) ret_eq_1e6,
  SUM(CASE WHEN ABS(ops_ret-hist_ret)>1e-6 AND ABS(ops_ret-hist_ret)<=1e-4 THEN 1 ELSE 0 END) ret_1e6_1bp,
  SUM(CASE WHEN ABS(ops_ret-hist_ret)>1e-4 AND ABS(ops_ret-hist_ret)<=1e-3 THEN 1 ELSE 0 END) ret_1bp_10bp,
  SUM(CASE WHEN ABS(ops_ret-hist_ret)>1e-3 AND ABS(ops_ret-hist_ret)<=1e-2 THEN 1 ELSE 0 END) ret_10bp_1pct,
  SUM(CASE WHEN ABS(ops_ret-hist_ret)>1e-2 THEN 1 ELSE 0 END) ret_gt_1pct,
  COUNT(DISTINCT CASE WHEN ABS(ops_ret-hist_ret)>1e-3 THEN s END) syms_ret_gt10bp,
  COUNT(DISTINCT CASE WHEN ABS(ops_ret-hist_ret)>1e-2 THEN s END) syms_ret_gt1pct,
  ROUND(100.0*SUM(CASE WHEN ABS(ops_ret-hist_ret)>1e-3 THEN 1 ELSE 0 END)/COUNT(*),3) pct_ret_gt10bp
FROM r WHERE ops_ret IS NOT NULL AND hist_ret IS NOT NULL
"""
print("="*100); print("D1 DAILY-RETURN agreement between the two stores (same symbol, same consecutive shared dates)")
print("SQL:", " ".join(SQL_RET.split()))
cur=con.execute(SQL_RET); cols=[d[0] for d in cur.description]; row=cur.fetchone()
for c,v in zip(cols,row): print(f"  {c} = {v}")
print()

# ---------- D2: per-symbol AFFINE fit  ops = a*hist + b  (qfq re-anchor signature) ----------
print("="*100)
print("D2 per-symbol affine fit ops_close = a*hist_close + b, on symbols whose closes disagree")
SQL_FIT = """
SELECT d.symbol, COUNT(*) n,
       SUM(b.close) sx, SUM(d.close) sy, SUM(b.close*b.close) sxx, SUM(b.close*d.close) sxy,
       SUM(CASE WHEN ABS(d.close-b.close)>0.005 THEN 1 ELSE 0 END) ndiff
FROM daily_bar_cache d JOIN mh.daily_bars b
  ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
WHERE d.quality_status='ready' AND d.adjustment_mode='qfq'
GROUP BY d.symbol HAVING n>20
"""
print("SQL(step1):", " ".join(SQL_FIT.split()))
fits={}
for sym,n,sx,sy,sxx,sxy,ndiff in con.execute(SQL_FIT):
    den = n*sxx - sx*sx
    if den == 0: continue
    a = (n*sxy - sx*sy)/den
    b = (sy - a*sx)/n
    fits[sym]=(n,a,b,ndiff)
print(f"  symbols fitted (n>20 shared bars): {len(fits)}")

# residual pass
SQL_ROWS = """
SELECT d.symbol, d.close, b.close
FROM daily_bar_cache d JOIN mh.daily_bars b
  ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
WHERE d.quality_status='ready' AND d.adjustment_mode='qfq'
ORDER BY d.symbol
"""
print("SQL(step2 residuals):", " ".join(SQL_ROWS.split()))
maxres={}; maxratio_spread={}
import collections
ratios=collections.defaultdict(lambda:[float('inf'),float('-inf')])
for sym,dc,bc in con.execute(SQL_ROWS):
    f=fits.get(sym)
    if not f: continue
    n,a,b,ndiff=f
    r=abs(dc-(a*bc+b))
    if r>maxres.get(sym,0.0): maxres[sym]=r
    if bc:
        rt=dc/bc
        lo,hi=ratios[sym]
        ratios[sym]=[min(lo,rt),max(hi,rt)]

affected=[s for s,(n,a,b,nd) in fits.items() if nd>0]
def bucket(pred, pool): return sum(1 for s in pool if pred(s))
print(f"\n  symbols with >=1 bar differing by >0.005 (among fitted): {len(affected)}")
print(f"  of those, MAX affine residual <= 0.01 (one tick)      : {bucket(lambda s: maxres.get(s,9e9)<=0.01, affected)}")
print(f"  of those, MAX affine residual <= 0.02                 : {bucket(lambda s: maxres.get(s,9e9)<=0.02, affected)}")
print(f"  of those, MAX affine residual <= 0.05                 : {bucket(lambda s: maxres.get(s,9e9)<=0.05, affected)}")
print(f"  of those, MAX affine residual  > 0.05 (true shape mismatch): {bucket(lambda s: maxres.get(s,9e9)>0.05, affected)}")
# pure-scale test (their test): constant ratio
pure_scale = bucket(lambda s: (ratios[s][1]-ratios[s][0])<=1e-6, affected)
print(f"  of those, ops/hist ratio constant to 1e-6 (PURE scale): {pure_scale}")
print(f"  -> symbols where a PURE ratio fails but an AFFINE fit succeeds within one tick: "
      f"{bucket(lambda s: maxres.get(s,9e9)<=0.01, affected) - pure_scale}")

# top residual offenders
worst=sorted(affected, key=lambda s:-maxres.get(s,0))[:15]
print("\n  worst 15 by max affine residual (symbol, n, slope a, intercept b, max_resid):")
for s in worst:
    n,a,b,nd=fits[s]; print(f"    {s} n={n} a={a:.6f} b={b:+.4f} maxres={maxres[s]:.4f}")
con.close()
