# Apply the engine's soft-risk demotion: RuleEngine.evaluate() turns strong->watch when
# risk_no_chasing_after_big_rise fails (five_day_pct >= big_rise_pct=20).
import sqlite3, numpy as np, pandas as pd
OP = r"D:/codex-A股交易/trading_local.sqlite3"; MH = r"D:/codex-A股交易/market_history.sqlite3"
op = sqlite3.connect(f"file:{OP}?mode=ro", uri=True); mh = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)
stocks = {r[0] for r in mh.execute("SELECT symbol FROM instruments WHERE asset_type='stock'")}
df = pd.read_sql_query("SELECT symbol,trade_date,high,close,volume FROM daily_bar_cache "
                       "WHERE quality_status='ready' ORDER BY symbol ASC, trade_date ASC", op)
df = df[df["symbol"].isin(stocks)].copy()
for c in ("high","close","volume"): df[c] = pd.to_numeric(df[c], errors="coerce")
df = df.dropna(subset=["high","close"]); df["volume"] = df["volume"].fillna(0.0)
g = df.groupby("symbol", sort=False)
df["bar_idx"]=g.cumcount()
df["high250"]=g["high"].transform(lambda s: s.rolling(250,min_periods=1).max())
df["pc"]=(df["close"]-g["close"].shift(1))/g["close"].shift(1)*100
df["c5"]=g["close"].shift(5)
df["f5"]=np.where(df["c5"].notna(),(df["close"]-df["c5"])/df["c5"]*100,0.0)   # engine: 0.0 when len(hist)<6
vm=g["volume"].transform(lambda s: s.shift(1).rolling(5,min_periods=5).mean())
df["vr"]=np.where(vm.notna()&(vm>0), df["volume"]/vm, 1.0)
code=df["symbol"].str.extract(r"(\d{6})",expand=False)
b=np.select([code.str.startswith(("300","301","302")),code.str.startswith("688"),code.str[0].isin(list("849"))],
            ["chinext","star","bse"],default="main")
df["thr"]=pd.Series(b,index=df.index).map({"main":9.8,"chinext":19.5,"star":19.5,"bse":29.0}).astype(float)
fun=pd.read_sql_query("SELECT symbol,total_share_billion,book_value_per_share FROM symbol_fundamental_snapshot",op)
fun["code"]=fun["symbol"].str.extract(r"(\d{6})",expand=False)
fun=fun.dropna(subset=["code"]).drop_duplicates("code",keep="last").set_index("code")
df["cap"]=df["close"]*code.map(fun["total_share_billion"]); bv=code.map(fun["book_value_per_share"])
df["pb"]=np.where(bv.notna()&(bv!=0), df["close"]/bv, np.nan)

ev=df["bar_idx"]>=1
S0=(df["ratio"] if False else (df["close"]/df["high250"]<=0.5))&(df["pc"]>=df["thr"])&(df["pb"]<=6.0)&(df["cap"]>=50)&(df["cap"]<=200)
STRONG=S0&(df["vr"]>=1.5)
SOFT_OK=df["f5"]<20.0          # risk gate passes
print("=== STRONG same-bar (projected fundamentals), before vs after soft-risk demotion ===")
for lbl,(a,b2) in {"RESEARCH WINDOW 2023-09-04..2026-09-04":("2023-09-04","2026-09-04"),
                   "run  1 2025-10-12..2026-06-09":("2025-10-12","2026-06-09"),
                   "run 13 2025-06-17..2026-06-12":("2025-06-17","2026-06-12"),
                   "run 19 2025-10-15..2026-06-12":("2025-10-15","2026-06-12"),
                   "run 39 2025-10-15..2026-06-29":("2025-10-15","2026-06-29")}.items():
    w=ev&(df["trade_date"]>=a)&(df["trade_date"]<=b2)
    pre=int((w&STRONG).sum()); post=int((w&STRONG&SOFT_OK).sum())
    print(f"  {lbl:<40} strong_pre_demotion={pre:>4}  strong_AFTER_demotion={post:>4}  distinct_symbols={df.loc[w&STRONG&SOFT_OK,'symbol'].nunique():>3}")
out=df.loc[ev&(df['trade_date']>='2023-09-04')&(df['trade_date']<='2026-09-04')&STRONG&SOFT_OK,
           ["symbol","trade_date","close","high250","pc","thr","vr","cap","pb","f5"]]
out.to_csv(r"D:/codex-A股交易/claude methods/_m1_evidence/benchmark_v6_strong_final.csv",index=False)
print("\n  final STRONG bars (soft-risk applied):",len(out),"over",out['symbol'].nunique(),"stocks")
print(out.sort_values('trade_date').head(10).to_string(index=False))
