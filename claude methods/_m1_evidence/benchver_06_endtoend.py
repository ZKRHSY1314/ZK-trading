import sqlite3, sys
import numpy as np, pandas as pd
sys.path.insert(0, r"D:/codex-A股交易/backend")
from app.data.symbols import normalize_a_share_code

df=pd.read_pickle(r"D:/codex-A股交易/claude methods/_m1_evidence/benchver_bars.pkl")
con=sqlite3.connect(r"file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True)
f=pd.read_sql_query("SELECT symbol,total_share_billion,book_value_per_share FROM symbol_fundamental_snapshot",con)
con.close()
f["code"]=f["symbol"].map(normalize_a_share_code)
df["code"]=df["symbol"].map(normalize_a_share_code)
df=df.join(f.set_index("code")[["total_share_billion","book_value_per_share"]],on="code")
df["cap_proj"]=df["close"]*df["total_share_billion"]
df["pb_proj"]=np.where(df["book_value_per_share"]>0, df["close"]/df["book_value_per_share"], np.nan)

# same-bar S0 with projected fundamentals
df["lowpos"]=df["ratio"]<=0.5
df["s0"]=df["lowpos"]&(df["pct_change"]>=df["limit_thr"])&(df["pb_proj"]<=6.0)&(df["cap_proj"]>=50.0)&(df["cap_proj"]<=200.0)
df["div"]=df["volume_ratio"]>=1.5
g=df.groupby("symbol",sort=False)
# ARMED window: S0 within the previous 1..5 bars (rules.yaml armed_window_days=5)
armed=np.zeros(len(df),dtype=bool)
s0v=df["s0"].to_numpy()
for k in range(1,6):
    armed |= g["s0"].shift(k).fillna(False).to_numpy().astype(bool)
df["armed"]=armed
df["s0_or_armed"]=df["s0"]|df["armed"]
# constitution hard block still applies on the entry bar
df["strong_samebar"]=df["s0"]&df["div"]&df["lowpos"]
df["strong_armed"]=df["s0_or_armed"]&df["div"]&df["lowpos"]

# next-bar execution feasibility
df["next_open"]=g["open"].shift(-1); df["next_low"]=g["low"].shift(-1)
df["next_date"]=g["trade_date"].shift(-1); df["next_amount"]=np.nan
df["one_word"]=df["next_low"]>= (df["close"]*(1+df["limit_thr"]/100))*0.99

WIN={"run1":("2025-10-12","2026-06-09"),"run13":("2025-06-17","2026-06-12"),"run19":("2025-10-15","2026-06-12"),
     "research_window":("2023-09-04","2026-09-04")}
print("=== MARKET-WIDE end-to-end, allow_projected_fundamentals=True ===")
print(f"{'window':<16}{'strong(same-bar cfg)':>21}{'strong(armed-5 cfg)':>21}{'entry-feasible(same-bar)':>26}")
for lbl,(a,b) in WIN.items():
    d=df[(df["bar_idx"]>=1)&(df["trade_date"]>=a)&(df["trade_date"]<=b)]
    ss=d[d["strong_samebar"]]; sa=d[d["strong_armed"]]
    feas=ss[(ss["next_date"].notna())&(~ss["one_word"].fillna(True))]
    print(f"{lbl:<16}{len(ss):>21}{len(sa):>21}{len(feas):>26}")

print()
print("=== STORED vs CLAIMED rejected_by_risk_count ===")
con=sqlite3.connect(r"file:D:/codex-A股交易/trading_local.sqlite3?mode=ro",uri=True)
for rid,claimed_blk,claimed_evals in ((1,1626,1760),(13,4644,4810),(19,3082,3220)):
    import json
    row=con.execute("SELECT start_date,end_date,metrics_json FROM historical_backtest_runs WHERE id=?",(rid,)).fetchone()
    m=json.loads(row[2]); stored=m.get("rejected_by_risk_count")
    nd=con.execute("SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ?",(row[0],row[1])).fetchone()[0]
    print(f"  run {rid:<3} {row[0]}..{row[1]}  stored_rejected={stored:<6} claimed_blocked={claimed_blk:<6} delta={claimed_blk-stored:+d} "
          f"| claimed_evals={claimed_evals} / {nd} trading dates -> implied universe = {claimed_evals/nd:.2f} symbols "
          f"(market has {con.execute('SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ? AND quality_status=chr(114)||chr(101)||chr(97)||chr(100)||chr(121)',(row[0],row[1])).fetchone()[0]})")
    print(f"          metrics_json keys: {sorted(m.keys())}")
con.close()
