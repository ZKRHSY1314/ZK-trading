import sqlite3, sys, time
import numpy as np, pandas as pd
sys.path.insert(0, r"D:/codex-A股交易/backend")
from app.data.price_limits import infer_board_type, limit_up_threshold
from app.data.symbols import normalize_a_share_code

OP=r"D:/codex-A股交易/trading_local.sqlite3"
con=sqlite3.connect(f"file:{OP}?mode=ro",uri=True)
t0=time.time()
df=pd.read_sql_query("""
 SELECT symbol,trade_date,open,high,low,close,volume
 FROM daily_bar_cache WHERE quality_status='ready'
""",con)
con.close()
print("loaded",len(df),"rows in",round(time.time()-t0,1),"s")

for c in ("open","high","low","close","volume"):
    df[c]=pd.to_numeric(df[c],errors="coerce")
# engine: dropna on OHLC, volume filled 0
df=df.dropna(subset=["open","high","low","close"]).copy()
df["volume"]=df["volume"].fillna(0.0)
df=df.sort_values(["symbol","trade_date"],kind="mergesort").reset_index(drop=True)
print("after OHLC dropna:",len(df),"rows /",df["symbol"].nunique(),"symbols")

g=df.groupby("symbol",sort=False)
df["bar_idx"]=g.cumcount()                       # 0-based; len(hist)=bar_idx+1
df["prev_close"]=g["close"].shift(1)
df["high250"]=g["high"].transform(lambda s: s.rolling(250,min_periods=1).max())
# volume_mean = mean of the 5 bars BEFORE current (hist.volume.iloc[-6:-1]), only when len(hist)>=6
vm=g["volume"].transform(lambda s: s.shift(1).rolling(5,min_periods=5).mean())
df["vol_mean"]=np.where(df["bar_idx"]>=5, vm, np.nan)
df["volume_ratio"]=np.where((df["vol_mean"].notna())&(df["vol_mean"]>0), df["volume"]/df["vol_mean"], 1.0)
df["pct_change"]=(df["close"]-df["prev_close"])/df["prev_close"]*100.0

# board threshold per symbol (engine passes name="")
syms=df["symbol"].unique()
thr={}
bad=[]
for s in syms:
    try: code=normalize_a_share_code(s)
    except Exception: bad.append(s); thr[s]=np.nan; continue
    thr[s]=limit_up_threshold(infer_board_type(code,""))
df["limit_thr"]=df["symbol"].map(thr)
print("unmappable symbols:",len(bad), bad[:5])
print("limit_thr distribution:", df.drop_duplicates('symbol')['limit_thr'].value_counts(dropna=False).to_dict())

df["ratio"]=df["close"]/df["high250"]
df["evaluable"]=df["bar_idx"]>=1     # engine requires len(hist)>=2

WIN={"run1":("2025-10-12","2026-06-09"),"run13":("2025-06-17","2026-06-12"),"run19":("2025-10-15","2026-06-12"),
     "research_window":("2023-09-04","2026-09-04")}
print()
print("=== FULL-MARKET GATE CASCADE (all quality_status='ready' symbols, warm-up = full pre-window history) ===")
hdr=f"{'window':<16}{'evals':>10}{'hardblk':>10}{'blk%':>8}{'lowpos':>9}{'+limitup':>10}{'+div(no-fund)':>14}{'syms':>7}"
print(hdr)
store={}
for lbl,(a,b) in WIN.items():
    m=df["evaluable"]&(df["trade_date"]>=a)&(df["trade_date"]<=b)
    d=df[m]
    n=len(d)
    lowpos=(d["ratio"]<=0.5)
    hardblk=(~lowpos)  # is_low_position fails => hard block (high250>0 always here since high>0)
    s0nf=lowpos&(d["pct_change"]>=d["limit_thr"])          # S0 ignoring pb/cap
    both=s0nf&(d["volume_ratio"]>=1.5)                      # S0(no fund) AND divergence
    print(f"{lbl:<16}{n:>10}{int(hardblk.sum()):>10}{100*hardblk.mean():>7.2f}%{int(lowpos.sum()):>9}{int(s0nf.sum()):>10}{int(both.sum()):>14}{d['symbol'].nunique():>7}")
    store[lbl]=d.assign(lowpos=lowpos,s0nf=s0nf,both=both)

print()
print("=== per-symbol hard-block rate distribution, run19 window (deciles) ===")
d=store["run19"]
per=d.groupby("symbol").apply(lambda x: pd.Series({"n":len(x),"blk":(~x["lowpos"]).sum()}))
per["rate"]=per["blk"]/per["n"]
print(per["rate"].describe(percentiles=[.1,.25,.5,.75,.9,.95,.99]).round(4).to_dict())
print("symbols with block rate >=0.92 :", int((per["rate"]>=0.92).sum()), "/", len(per))
print("symbols with block rate ==1.00 :", int((per["rate"]>=0.999).sum()))
df.to_pickle(r"D:/codex-A股交易/claude methods/_m1_evidence/benchver_bars.pkl")
print("saved pickle")
