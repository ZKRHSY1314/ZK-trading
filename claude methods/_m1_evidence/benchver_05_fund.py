import sqlite3, sys
import numpy as np, pandas as pd
sys.path.insert(0, r"D:/codex-A股交易/backend")
from app.data.symbols import normalize_a_share_code

df=pd.read_pickle(r"D:/codex-A股交易/claude methods/_m1_evidence/benchver_bars.pkl")
OP=r"D:/codex-A股交易/trading_local.sqlite3"
con=sqlite3.connect(f"file:{OP}?mode=ro",uri=True)
f=pd.read_sql_query("SELECT symbol,as_of,available_at,total_share_billion,book_value_per_share FROM symbol_fundamental_snapshot",con)
con.close()
print("fund rows",len(f),"as_of set",sorted(f['as_of'].unique()),"available_at set",sorted(f['available_at'].unique())[:3])
f["code"]=f["symbol"].map(lambda s:(normalize_a_share_code(s) if s else None))
fmap=f.dropna(subset=["code"]).set_index("code")[["total_share_billion","book_value_per_share"]]
df["code"]=df["symbol"].map(lambda s: normalize_a_share_code(s))
df=df.join(fmap,on="code")
print("bars with a projectable snapshot:", int(df["total_share_billion"].notna().sum()), "/", len(df),
      " distinct codes matched:", df.loc[df['total_share_billion'].notna(),'code'].nunique())

df["cap_proj"]=np.where(df["total_share_billion"].notna(), df["close"]*df["total_share_billion"], np.nan)
df["pb_proj"]=np.where((df["book_value_per_share"].notna())&(df["book_value_per_share"]>0), df["close"]/df["book_value_per_share"], np.nan)

WIN={"run1":("2025-10-12","2026-06-09"),"run13":("2025-06-17","2026-06-12"),"run19":("2025-10-15","2026-06-12"),
     "research_window":("2023-09-04","2026-09-04")}
print()
print("=== S0 cascade WITH allow_projected_fundamentals=True (market-wide) ===")
print(f"{'window':<16}{'lowpos+limitup':>16}{'pass PB<=6':>12}{'pass cap band':>14}{'S0 pass':>9}{'S0+div=STRONG':>15}")
detail={}
for lbl,(a,b) in WIN.items():
    d=df[(df["bar_idx"]>=1)&(df["trade_date"]>=a)&(df["trade_date"]<=b)]
    base=d[(d["ratio"]<=0.5)&(d["pct_change"]>=d["limit_thr"])]
    pbok=(base["pb_proj"].notna())&(base["pb_proj"]<=6.0)
    capok=(base["cap_proj"].notna())&(base["cap_proj"]>=50.0)&(base["cap_proj"]<=200.0)
    s0=pbok&capok
    strong=s0&(base["volume_ratio"]>=1.5)
    print(f"{lbl:<16}{len(base):>16}{int(pbok.sum()):>12}{int(capok.sum()):>14}{int(s0.sum()):>9}{int(strong.sum()):>15}")
    detail[lbl]=base.assign(pbok=pbok,capok=capok,s0=s0,strong=strong)

print()
print("=== STRONG bars (projected fundamentals) in research window ===")
s=detail["research_window"]
w=s[s["strong"]]
print("count:",len(w),"distinct symbols:",w["symbol"].nunique())
print(w[["symbol","trade_date","close","pct_change","limit_thr","ratio","volume_ratio","cap_proj","pb_proj"]].head(30).to_string(index=False))
print()
print("=== why the 'lowpos+limitup' bars fail the band (research window) ===")
b=detail["research_window"]
print(" no snapshot at all:", int(b["total_share_billion"].isna().sum()))
print(" cap < 50亿:", int(((b['cap_proj'].notna())&(b['cap_proj']<50)).sum()),
      " cap > 200亿:", int(((b['cap_proj'].notna())&(b['cap_proj']>200)).sum()),
      " cap in band:", int(b['capok'].sum()))
print(" pb > 6:", int(((b['pb_proj'].notna())&(b['pb_proj']>6)).sum()), " pb missing:", int(b['pb_proj'].isna().sum()))
print()
print("=== POINT-IN-TIME visibility of the single snapshot at each run cutoff ===")
for lbl,(a,b2) in WIN.items():
    print(f"  {lbl} end={b2}: snapshots with as_of<=end AND available_at<=end -> ",
          int(((f['as_of']<=b2)&(f['available_at'].str[:10]<=b2)).sum()))
