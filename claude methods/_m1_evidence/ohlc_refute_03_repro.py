import sqlite3, pandas as pd, traceback
OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p):
    c=sqlite3.connect(f"file:{p}?mode=ro",uri=True); c.row_factory=sqlite3.Row; return c

PRICE_COLUMNS=["open","high","low","close"]; NUMERIC=PRICE_COLUMNS+["volume","amount"]
op=ro(OP)
syms=['SH688089','SH688143','SH688173']
ph=",".join("?"*len(syms))
rows=op.execute(f"""SELECT symbol,trade_date,open,high,low,close,volume,amount,quality_status
 FROM daily_bar_cache WHERE symbol IN ({ph}) AND quality_status='ready' ORDER BY trade_date ASC""",syms).fetchall()
frames={}
for s in syms:
    df=pd.DataFrame([dict(r) for r in rows if r["symbol"]==s])
    for c in NUMERIC: df[c]=pd.to_numeric(df[c],errors="coerce")
    df.dropna(subset=PRICE_COLUMNS,inplace=True)          # exact engine.py:457
    df[["volume","amount"]]=df[["volume","amount"]].fillna(0.0)
    df["trade_date"]=pd.to_datetime(df["trade_date"]); df.set_index("trade_date",inplace=True)
    frames[s]=df

curr=pd.to_datetime("2024-11-06")
print("=== replication of engine.py _load_symbol_frames -> row survives dropna? ===")
for s in syms:
    print(s,"row present at 2024-11-06:",curr in frames[s].index,
          "| open=",float(frames[s].loc[curr,"open"]),
          "| bars_total=",len(frames[s]))

print("\n=== exact engine.py:231-233 arithmetic (slippage from settings) ===")
import os,sys
sys.path.insert(0,r"D:/codex-A股交易/backend")
os.environ.setdefault("TRADING_DATABASE_PATH", OP)
from app.config import settings
slippage=settings.slippage_rate; lot=settings.min_order_lot
print("slippage_rate=",slippage,"min_order_lot=",lot)
for s in syms:
    bar=dict(frames[s].loc[curr])
    alloc=100000.0*0.2
    reference_price=float(bar["open"])
    buy_price=round(reference_price*(1+slippage),4)
    print(f"{s}: reference_price={reference_price} buy_price={buy_price}")
    try:
        q=int(alloc/buy_price)//lot*lot
        print("   requested_qty =",q)
    except Exception as e:
        print("   RAISED:",type(e).__name__,e)

print("\n=== does execution.decide() have its own guard that would fire first? ===")
from app.backtest.execution import BacktestExecutionModel
m=BacktestExecutionModel()
bar=dict(frames['SH688089'].loc[curr])
d=m.decide(side="buy",requested_quantity=1000,price=0.0,bar=bar,previous_close=20.75,limit_pct=20.0)
print("   decide(price=0.0) ->",d.fill_status,d.reject_reason)

print("\n=== market_history cross-check: symbols with a 2024-11-06 bar ===")
mh=ro(MH)
for r in mh.execute("""SELECT adjustment_mode, COUNT(*) n, COUNT(DISTINCT symbol) syms
   FROM daily_bars WHERE trade_date='2024-11-06' GROUP BY adjustment_mode"""): print("   ",dict(r))
for r in mh.execute("""SELECT COUNT(DISTINCT symbol) distinct_syms FROM daily_bars WHERE trade_date='2024-11-06'"""):
    print("   distinct symbols on 2024-11-06 in market_history:",dict(r))
for r in mh.execute("""SELECT symbol, COUNT(*) n FROM daily_bars WHERE symbol IN ('SH688089','SH688143','SH688173')
   GROUP BY symbol"""): print("   ",dict(r))
