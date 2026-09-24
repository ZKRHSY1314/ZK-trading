"""How many 灯盏 entries exist under (a) rules.yaml's same-bar rule vs (b) the spec's sequential state machine."""
import os, sqlite3, pandas as pd, numpy as np
os.environ["ENABLE_LIVE_TRADING"]="false"; os.environ["DATABASE_PATH"]=r"D:\codex-A股交易\trading_local.sqlite3"
from app.storage.sqlite_store import SQLiteStore
from app.data.fundamentals import FundamentalResolver
from app.data.price_limits import infer_board_type, limit_up_threshold
from app.data.symbols import normalize_a_share_code
DB=r"D:\codex-A股交易\trading_local.sqlite3"
con=sqlite3.connect(f"file:{DB}?mode=ro",uri=True)
df=pd.read_sql("select symbol,trade_date,high,close,volume from daily_bar_cache where quality_status='ready' order by symbol,trade_date",con)
df=df.dropna(subset=["close","high"]); df["volume"]=df["volume"].fillna(0)
print("rows",len(df),"symbols",df.symbol.nunique())
res=FundamentalResolver(SQLiteStore(DB))
share={}
for s in df.symbol.unique():
    r=res.resolve(s,1.0); share[s]=r.market_cap_billion  # cap per 1元 = total_share(亿)
df["share"]=df.symbol.map(share)
g=df.groupby("symbol",sort=False)
df["prev_close"]=g.close.shift(1)
df["high250"]=g.high.transform(lambda x: x.rolling(250,min_periods=120).max().shift(1))
df["pct"]=(df.close/df.prev_close-1)*100
df["vol_ratio"]=df.volume/g.volume.transform(lambda x: x.rolling(5).mean().shift(1))
df["cap"]=df.close*df.share
df["limit_th"]=df.symbol.map(lambda s: limit_up_threshold(infer_board_type(normalize_a_share_code(s),"")))
df["low"]=df.close/df.high250<=0.5
df["lu"]=df.pct>=df.limit_th-0.05
df["band"]=(df.cap>=50)&(df.cap<=200)
df["s0"]=df.low&df.lu&df.band
df["div_same"]=df.s0&(df.vol_ratio>=1.5)
# sequential: divergence within next 1..5 bars after s0
fwd=np.zeros(len(df),bool)
vr=(df.vol_ratio>=1.5).values; sym=df.symbol.values; s0=df.s0.values
for i in np.flatnonzero(s0):
    for k in range(1,6):
        j=i+k
        if j<len(df) and sym[j]==sym[i] and vr[j]: fwd[i]=True; break
df["div_seq"]=fwd
n=len(df)
print(f"evaluable bars (high250 known): {df.high250.notna().sum()}")
print(f"low position          : {df.low.sum():7d}  ({df.low.mean():.2%})")
print(f"low & limit-up        : {(df.low&df.lu).sum():7d}")
print(f"S0 = low&LU&cap50-200 : {df.s0.sum():7d}   symbols={df[df.s0].symbol.nunique()}")
print(f"  + same-bar vol>=1.5 (rules.yaml requires) : {df.div_same.sum():5d}")
print(f"  + vol>=1.5 within next 1-5 bars (spec)     : {df.div_seq.sum():5d}")
print("S0 per month:"); print(df[df.s0].groupby(df.trade_date.str[:7]).size().to_string())
