import os, cProfile, pstats, sqlite3, io
os.environ["ENABLE_LIVE_TRADING"]="false"; os.environ["DATABASE_PATH"]=r"D:\codex-A股交易\trading_local.sqlite3"
from app.backtest.engine import BacktestEngine
con=sqlite3.connect(r"file:D:\codex-A股交易\trading_local.sqlite3?mode=ro",uri=True)
syms=[r[0] for r in con.execute("select symbol from daily_bar_cache where quality_status='ready' group by symbol having count(*)>450 order by symbol")][::400][:12]
pr=cProfile.Profile(); pr.enable()
r=BacktestEngine().run("2026-04-01","2026-07-17",syms,100000.0,5,0.2,persist=False)
pr.disable()
print("bars:",r["metrics"]["signal_evaluated_bars"],"days:",r["days"])
s=io.StringIO(); pstats.Stats(pr,stream=s).sort_stats("cumulative").print_stats(18); print(s.getvalue()[:3500])
