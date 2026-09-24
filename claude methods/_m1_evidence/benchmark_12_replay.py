import sqlite3, sys, json
import pandas as pd
sys.stdout.reconfigure(encoding='utf-8')
OP = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
op=ro(OP)
op.row_factory = sqlite3.Row

# recover per-run universes
uni={}
for bj, in op.execute("SELECT backtest_json FROM offhour_research_runs"):
    try: d=json.loads(bj)
    except Exception: continue
    if d.get("run_id"): uni[d["run_id"]]=d.get("symbols") or []

fund = {r["symbol"]: dict(r) for r in op.execute("SELECT symbol, as_of, available_at, total_share_billion, book_value_per_share FROM symbol_fundamental_snapshot")}

THRESH = {"main":9.8, "chinext":19.5, "star":19.5, "bse":29.5, "st":4.8}
def board(code):
    c=code.upper().replace("SH","").replace("SZ","").replace("BJ","")
    if c.startswith(("300","301","302")): return "chinext"
    if c.startswith("688"): return "star"
    if c.startswith(("8","4","9")): return "bse"
    return "main"

def frames(symbols):
    ph=",".join("?" for _ in symbols)
    rows=op.execute(f"SELECT symbol,trade_date,open,high,low,close,volume,amount FROM daily_bar_cache WHERE symbol IN ({ph}) AND quality_status='ready' ORDER BY trade_date ASC", tuple(symbols)).fetchall()
    out={}
    for r in rows: out.setdefault(r["symbol"],[]).append(dict(r))
    res={}
    for s,recs in out.items():
        df=pd.DataFrame(recs)
        for c in ("open","high","low","close","volume","amount"): df[c]=pd.to_numeric(df[c],errors="coerce")
        df=df.dropna(subset=["open","high","low","close"])
        if df.empty: continue
        df["trade_date"]=pd.to_datetime(df["trade_date"]); df=df.set_index("trade_date").sort_index()
        res[s]=df
    return res

def replay(run_id, sd, ed, symbols, projected):
    dfs=frames(symbols)
    dates=sorted({i.strftime("%Y-%m-%d") for df in dfs.values() for i in df.index if sd<=i.strftime("%Y-%m-%d")<=ed})
    c=dict(eval_bars=0, blocked=0, s0_pass=0, s0_unknown_fund=0, s0_fail_limitup=0, s0_fail_pbcap=0,
           div_pass=0, both_pass=0, strong=0, soft_risk_fail=0, no_history=0)
    for d in dates:
        dt=pd.to_datetime(d)
        for s,df in dfs.items():
            if dt not in df.index: continue
            hist=df.loc[:dt]
            if len(hist)<2: c["no_history"]+=1; continue
            bar=hist.iloc[-1]; prev=hist.iloc[-2]
            c["eval_bars"]+=1
            high250=hist["high"].tail(250).max()
            price=float(bar["close"])
            low_pos = high250>0 and price/high250 <= 0.5
            if not low_pos:
                c["blocked"]+=1
                continue
            pct=(price-float(prev["close"]))/float(prev["close"])*100
            thr=THRESH[board(s)]
            vm=hist["volume"].iloc[-6:-1].mean() if len(hist)>=6 else 0
            vr=float(bar["volume"])/vm if vm and vm>0 else 1.0
            f5=(price-float(hist.iloc[-6]["close"]))/float(hist.iloc[-6]["close"])*100 if len(hist)>=6 else 0.0
            fr=fund.get(s.upper()) or fund.get(s.replace("SH","").replace("SZ",""))
            if projected and fr:
                mc = price*fr["total_share_billion"] if fr["total_share_billion"] else None
                pb = price/fr["book_value_per_share"] if fr["book_value_per_share"] else None
            else:
                mc=None; pb=None   # point-in-time: as_of 2026-08-31 not visible before that date
            s0=False
            if pct < thr: c["s0_fail_limitup"]+=1
            elif pb is None or mc is None: c["s0_unknown_fund"]+=1
            elif pb>6.0 or mc<50 or mc>200: c["s0_fail_pbcap"]+=1
            else: s0=True; c["s0_pass"]+=1
            div = vr>=1.5
            if div: c["div_pass"]+=1
            if s0 and div:
                c["both_pass"]+=1
                if f5>=20: c["soft_risk_fail"]+=1
                else: c["strong"]+=1
    return len(dates), c

print("### Q30 rule replay on TODAY's daily_bar_cache, exactly reproducing engine snapshot math")
for run_id in (1, 13, 19):
    syms=uni[run_id]
    r=op.execute("SELECT start_date,end_date FROM historical_backtest_runs WHERE id=?", (run_id,)).fetchone()
    for projected in (False, True):
        nd,c=replay(run_id, r["start_date"], r["end_date"], syms, projected)
        mode="projected_fundamentals" if projected else "point_in_time_fundamentals"
        print(f"  run {run_id} {r['start_date']}..{r['end_date']} symbols={len(syms)} trading_days={nd} mode={mode}")
        print("     ", c)
op.close()
