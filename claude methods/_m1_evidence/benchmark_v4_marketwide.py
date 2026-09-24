# INDEPENDENT market-wide replication of BacktestEngine._snapshot + DengZhanSignals gates.
# Pure read-only sqlite + pandas. No app imports, no store init, no network.
import sqlite3, re, json
import numpy as np, pandas as pd

OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
W0, W1 = "2023-09-04", "2026-09-04"

op = sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
mh = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)

print("SQL0: SELECT MIN(trade_date),MAX(trade_date),COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE quality_status='ready'")
print("  ", op.execute("SELECT MIN(trade_date),MAX(trade_date),COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE quality_status='ready'").fetchone())

# --- universe: stocks only, per market_history.instruments (excludes indices by construction)
stocks = {r[0] for r in mh.execute("SELECT symbol FROM instruments WHERE asset_type='stock'")}
allsym = {r[0] for r in op.execute("SELECT DISTINCT symbol FROM daily_bar_cache WHERE quality_status='ready'")}
nonstock = sorted(allsym - stocks)
print("\nNON-STOCK symbols in daily_bar_cache (excluded as indices/fixtures):", nonstock)
print("stock symbols in cache:", len(allsym & stocks))

print("\nSQL1: SELECT symbol,trade_date,high,close,volume FROM daily_bar_cache WHERE quality_status='ready' ORDER BY symbol,trade_date")
df = pd.read_sql_query(
    "SELECT symbol,trade_date,high,close,volume FROM daily_bar_cache "
    "WHERE quality_status='ready' ORDER BY symbol ASC, trade_date ASC", op)
df = df[df["symbol"].isin(stocks)].copy()
for c in ("high","close","volume"): df[c] = pd.to_numeric(df[c], errors="coerce")
df = df.dropna(subset=["high","close"])          # engine drops NaN OHLC rows
df["volume"] = df["volume"].fillna(0.0)
print("  rows after stock filter + OHLC dropna:", len(df), "symbols:", df["symbol"].nunique())

g = df.groupby("symbol", sort=False)
df["bar_idx"]   = g.cumcount()                                             # 0-based; len(hist)=bar_idx+1
df["high250"]   = g["high"].transform(lambda s: s.rolling(250, min_periods=1).max())
df["prev_close"]= g["close"].shift(1)
df["close_m5"]  = g["close"].shift(5)
df["vmean5"]    = g["volume"].transform(lambda s: s.shift(1).rolling(5, min_periods=5).mean())

df["pct_change"] = (df["close"] - df["prev_close"]) / df["prev_close"] * 100.0
df["vol_ratio"]  = np.where(df["vmean5"].notna() & (df["vmean5"] > 0), df["volume"] / df["vmean5"], 1.0)
df["ratio_hi"]   = df["close"] / df["high250"]

# board threshold (engine calls infer_board_type(code, "") -> name never seen, so never 'st')
code = df["symbol"].str.extract(r"(\d{6})", expand=False)
board = np.select(
    [code.str.startswith(("300","301","302")), code.str.startswith("688"), code.str[0].isin(list("849"))],
    ["chinext","star","bse"], default="main")
df["thr"] = pd.Series(board, index=df.index).map({"main":9.8,"chinext":19.5,"star":19.5,"bse":29.0}).astype(float)

# --- projected fundamentals (allow_projected_fundamentals=True path)
fun = pd.read_sql_query(
    "SELECT symbol, total_share_billion, book_value_per_share FROM symbol_fundamental_snapshot", op)
print("SQL2: SELECT symbol,total_share_billion,book_value_per_share FROM symbol_fundamental_snapshot  ->", len(fun), "rows")
fun["code"] = fun.symbol.str.extract(r"(\d{6})", expand=False)
fun = fun.dropna(subset=["code"]).drop_duplicates("code", keep="last").set_index("code")
df["code"] = code
df["tsb"]  = df["code"].map(fun.total_share_billion)
df["bvps"] = df["code"].map(fun.book_value_per_share)
df["cap_proj"] = (df["close"] * df["tsb"]).round(4)
df["pb_proj"]  = np.where(df["bvps"].notna() & (df["bvps"] != 0), (df["close"] / df["bvps"]).round(4), np.nan)

# --- gates (engine: evaluated bar requires len(hist)>=2 -> bar_idx>=1)
ev   = df["bar_idx"] >= 1
win  = (df["trade_date"] >= W0) & (df["trade_date"] <= W1)
cons = df["ratio_hi"] <= 0.5                       # constitution_no_high_position PASS
lim  = df["pct_change"] >= df["thr"]                  # limit-up candidate
pbok = df["pb_proj"] <= 6.0
capok= (df["cap_proj"] >= 50) & (df["cap_proj"] <= 200)
div  = df["vol_ratio"] >= 1.5                      # dengzhan_forced_divergence

base = ev & win
print("\n================ MARKET-WIDE, RESEARCH WINDOW 2023-09-04..2026-09-04, STOCKS ONLY ================")
def line(lbl, m):
    print(f"  {lbl:<62} bars={int(m.sum()):>9,}  symbols={df.loc[m,'symbol'].nunique():>5,}")
line("evaluated bars (bar_idx>=1, in window)", base)
line("HARD-BLOCKED by constitution (close/high250 > 0.5)", base & ~cons)
line("constitution PASS (close/high250 <= 0.5)", base & cons)
hb = (base & ~cons).sum() / base.sum() * 100
print(f"  --> market-wide hard-block rate = {hb:.2f}%")
line("cons PASS + limit-up (S0 minus fundamentals)", base & cons & lim)
line("cons PASS + limit-up + PB<=6 (projected)", base & cons & lim & pbok)
line("S0 FULL projected (cons+limit+PB+cap 50-200亿)", base & cons & lim & pbok & capok)
line("STRONG same-bar (S0 projected + vol_ratio>=1.5)", base & cons & lim & pbok & capok & div)

print("\n---- why the band bites: distribution of the cons+limit-up survivors ----")
s = df[base & cons & lim]
print(f"  survivors={len(s):,}  cap_proj notnull={s.cap_proj.notna().sum():,}  pb_proj notnull={s.pb_proj.notna().sum():,}")
print("  cap_proj quantiles:", {q: round(float(s.cap_proj.quantile(q)),2) for q in (.1,.25,.5,.75,.9,.99)})
print("  pb_proj  quantiles:", {q: round(float(s.pb_proj.quantile(q)),2) for q in (.1,.25,.5,.75,.9,.99)})
print("  fail cap<50:", int((s.cap_proj<50).sum()), " fail cap>200:", int((s.cap_proj>200).sum()),
      " fail pb>6:", int((s.pb_proj>6).sum()))

print("\n================ PER RUN WINDOW, FULL-MARKET UNIVERSE (stocks only) ================")
for rid,(a,b) in {1:("2025-10-12","2026-06-09"),13:("2025-06-17","2026-06-12"),
                  19:("2025-10-15","2026-06-12"),39:("2025-10-15","2026-06-29")}.items():
    w = ev & (df["trade_date"]>=a) & (df["trade_date"]<=b)
    n = int(w.sum()); blk = int((w & ~cons).sum())
    s0 = int((w & cons & lim & pbok & capok).sum())
    st = int((w & cons & lim & pbok & capok & div).sum())
    print(f"  run {rid:>2} {a}..{b}: evaluated={n:>9,} hard_blocked={blk:>9,} ({blk/n*100:5.2f}%) "
          f"S0_full_projected={s0:>5,} STRONG_same_bar={st:>4,} strong_symbols={df.loc[w&cons&lim&pbok&capok&div,'symbol'].nunique()}")

df.loc[base & cons & lim & pbok & capok & div, ["symbol","trade_date","close","high250","ratio_hi","pct_change","thr","vol_ratio","cap_proj","pb_proj"]]\
  .to_csv(r"D:/codex-A股交易/claude methods/_m1_evidence/benchmark_v4_strong_bars.csv", index=False)
print("\nwrote strong-bar list -> benchmark_v4_strong_bars.csv")
