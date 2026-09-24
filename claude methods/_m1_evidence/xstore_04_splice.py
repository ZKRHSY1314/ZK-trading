import sqlite3, collections
OPS = r"D:/codex-A股交易/trading_local.sqlite3"
HIST= r"D:/codex-A股交易/market_history.sqlite3"
con = sqlite3.connect(f"file:{OPS}?mode=ro", uri=True)
con.execute(f"ATTACH DATABASE 'file:{HIST}?mode=ro' AS mh")
def q(label, sql, args=(), lim=40):
    print("="*100); print(label); print("SQL:", " ".join(sql.split()))
    cur=con.execute(sql,args); cols=[d[0] for d in cur.description]; rows=cur.fetchall()
    print(" | ".join(cols))
    for r in rows[:lim]: print(" | ".join("" if v is None else str(v) for v in r))
    if len(rows)>lim: print(f"... ({len(rows)} rows total)")
    print()

# E1: per-symbol AND per-hist-vintage affine fit  (splice-aware)
print("="*100)
print("E1 splice-aware affine fit: ops_close = a*hist_close + b fitted SEPARATELY per (symbol, hist fetch vintage)")
SQL = """
SELECT d.symbol, substr(b.fetched_at,1,10) vint, d.close dc, b.close bc
FROM daily_bar_cache d JOIN mh.daily_bars b
  ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
WHERE d.quality_status='ready' AND d.adjustment_mode='qfq'
ORDER BY d.symbol, vint
"""
print("SQL:", " ".join(SQL.split()))
acc=collections.defaultdict(lambda:[0,0.0,0.0,0.0,0.0,0])  # n,sx,sy,sxx,sxy,ndiff
rows=[]
for sym,vint,dc,bc in con.execute(SQL):
    k=(sym,vint); a=acc[k]
    a[0]+=1; a[1]+=bc; a[2]+=dc; a[3]+=bc*bc; a[4]+=bc*dc
    if abs(dc-bc)>0.005: a[5]+=1
    rows.append((sym,vint,dc,bc))
fit={}
for k,(n,sx,sy,sxx,sxy,nd) in acc.items():
    den=n*sxx-sx*sx
    if n<20 or den==0: continue
    a=(n*sxy-sx*sy)/den; b=(sy-a*sx)/n
    fit[k]=(n,a,b,nd)
maxres=collections.defaultdict(float)
for sym,vint,dc,bc in rows:
    f=fit.get((sym,vint))
    if not f: continue
    r=abs(dc-(f[1]*bc+f[2]))
    if r>maxres[(sym,vint)]: maxres[(sym,vint)]=r
aff=[k for k,v in fit.items() if v[3]>0]
def cnt(t): return sum(1 for k in aff if maxres[k]<=t)
print(f"  (symbol,vintage) segments fitted with >=20 bars: {len(fit)}")
print(f"  segments containing at least one >0.005 diff    : {len(aff)}")
for t in (0.005,0.01,0.02,0.05,0.10):
    print(f"    segments explained by ONE affine map to within {t:>5}: {cnt(t):6d}  ({100.0*cnt(t)/len(aff):5.1f}%)")
print(f"    segments NOT explained even at 0.10           : {len(aff)-cnt(0.10):6d}  ({100.0*(len(aff)-cnt(0.10))/len(aff):5.1f}%)")
worst=sorted(aff,key=lambda k:-maxres[k])[:10]
print("  worst 10 segments:")
for k in worst:
    n,a,b,nd=fit[k]; print(f"    {k[0]} vint={k[1]} n={n} a={a:.6f} b={b:+.4f} maxres={maxres[k]:.4f}")
print()

# E2: where do the >1% RETURN discrepancies land? at the hist provider splice seam?
q("E2 >1% return discrepancies: distribution by trade_date (top dates)",
  """WITH j AS (SELECT d.symbol s, d.trade_date td, d.close dc, b.close bc, b.provider pv
       FROM daily_bar_cache d JOIN mh.daily_bars b
         ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
       WHERE d.quality_status='ready' AND d.adjustment_mode='qfq'),
     r AS (SELECT s, td, pv, LAG(pv) OVER (PARTITION BY s ORDER BY td) ppv,
                  dc/NULLIF(LAG(dc) OVER (PARTITION BY s ORDER BY td),0)-1 orr,
                  bc/NULLIF(LAG(bc) OVER (PARTITION BY s ORDER BY td),0)-1 hrr FROM j)
     SELECT td, COUNT(*) n_gt1pct, SUM(CASE WHEN pv<>ppv THEN 1 ELSE 0 END) at_provider_seam
     FROM r WHERE orr IS NOT NULL AND ABS(orr-hrr)>0.01 GROUP BY td ORDER BY n_gt1pct DESC LIMIT 20""")

q("E3 return discrepancy >1%: how many sit exactly on a hist provider-change seam?",
  """WITH j AS (SELECT d.symbol s, d.trade_date td, d.close dc, b.close bc, b.provider pv
       FROM daily_bar_cache d JOIN mh.daily_bars b
         ON b.symbol=d.symbol AND b.trade_date=d.trade_date AND b.adjustment_mode='qfq'
       WHERE d.quality_status='ready' AND d.adjustment_mode='qfq'),
     r AS (SELECT s, td, pv, LAG(pv) OVER (PARTITION BY s ORDER BY td) ppv,
                  dc/NULLIF(LAG(dc) OVER (PARTITION BY s ORDER BY td),0)-1 orr,
                  bc/NULLIF(LAG(bc) OVER (PARTITION BY s ORDER BY td),0)-1 hrr FROM j)
     SELECT SUM(CASE WHEN ABS(orr-hrr)>0.01 THEN 1 ELSE 0 END) ret_gt1pct,
            SUM(CASE WHEN ABS(orr-hrr)>0.01 AND pv<>ppv THEN 1 ELSE 0 END) gt1pct_at_seam,
            SUM(CASE WHEN pv<>ppv THEN 1 ELSE 0 END) total_seam_rows,
            SUM(CASE WHEN ABS(orr-hrr)>0.001 THEN 1 ELSE 0 END) ret_gt10bp,
            SUM(CASE WHEN ABS(orr-hrr)>0.001 AND pv<>ppv THEN 1 ELSE 0 END) gt10bp_at_seam
     FROM r WHERE orr IS NOT NULL AND hrr IS NOT NULL""")
con.close()
