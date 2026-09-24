# -*- coding: utf-8 -*-
import sqlite3
HIST = r"D:/codex-A股交易/market_history.sqlite3"
OPS  = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
h = ro(HIST); qh = lambda s,a=(): h.execute(s,a).fetchall()
o = ro(OPS);  qo = lambda s,a=(): o.execute(s,a).fetchall()
W0,W1='2023-09-04','2026-09-04'

print("### Q13 date arithmetic verified by julianday (not by hand)")
print("window inclusive days:", qh(f"SELECT CAST(julianday('{W1}')-julianday('{W0}') AS INT)+1"))
print("snapshot span inclusive days:", qh("SELECT CAST(julianday(MAX(snapshot_date))-julianday(MIN(snapshot_date)) AS INT)+1 FROM universe_snapshots"))
print("days before first snapshot (W0..2026-07-13 incl):", qh(f"SELECT CAST(julianday('2026-07-13')-julianday('{W0}') AS INT)+1"))

print("\n### Q14 TRADING-day denominator (calendar days may be the wrong denominator)")
print("distinct trade_dates in window, HIST:", qh(f"SELECT COUNT(DISTINCT trade_date) FROM daily_bars WHERE trade_date BETWEEN '{W0}' AND '{W1}'"))
print("MIN/MAX trade_date HIST in window:", qh(f"SELECT MIN(trade_date),MAX(trade_date) FROM daily_bars WHERE trade_date BETWEEN '{W0}' AND '{W1}'"))
print("distinct trade_dates OPS:", qo(f"SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN '{W0}' AND '{W1}'"))
print("MIN/MAX OPS:", qo(f"SELECT MIN(trade_date),MAX(trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN '{W0}' AND '{W1}'"))
print("trading days on/after first snapshot 2026-07-14:", qh(f"SELECT COUNT(DISTINCT trade_date) FROM daily_bars WHERE trade_date BETWEEN '2026-07-14' AND '{W1}'"))

print("\n### Q15 the 5 symbols whose bars stop early -- delisting or suspension?")
for r in qh(f"""WITH ls AS (SELECT symbol,MAX(trade_date) mx,COUNT(*) n FROM daily_bars
   WHERE trade_date BETWEEN '{W0}' AND '{W1}' GROUP BY symbol)
   SELECT ls.symbol, ls.mx, ls.n, i.name, i.status, i.list_date, i.delist_date
   FROM ls JOIN instruments i USING(symbol) WHERE ls.mx < '2026-08-25' ORDER BY ls.mx"""):
    print(r)

print("\n### Q16 list_date partial-reconstruction path (auditor never tested list_date)")
print(qh(f"""SELECT
  SUM(list_date IS NOT NULL AND list_date <= '{W0}') listed_at_window_start,
  SUM(list_date IS NOT NULL AND list_date >  '{W0}') ipo_during_window,
  SUM(list_date IS NULL) list_date_unknown FROM instruments"""))
print("IPOs by year inside window:", qh(f"""SELECT substr(list_date,1,4) yr, COUNT(*) FROM instruments
  WHERE list_date > '{W0}' AND list_date <= '{W1}' GROUP BY yr ORDER BY yr"""))

print("\n### Q17 any OTHER dated symbol-set source anywhere? (avoid missing a path)")
print("HIST universe_members distinct symbols across ALL 12 snapshots:",
      qh("SELECT COUNT(DISTINCT symbol) FROM universe_members"))
print("members per snapshot:", qh("""SELECT s.snapshot_date,s.universe_name,COUNT(m.symbol)
     FROM universe_snapshots s LEFT JOIN universe_members m ON m.snapshot_id=s.id
     GROUP BY s.id ORDER BY s.snapshot_date"""))
print("\nOPS sector_membership_snapshots effective_date range:",
      qo("SELECT COUNT(*),MIN(effective_date),MAX(effective_date),COUNT(DISTINCT effective_date) FROM sector_membership_snapshots"))
print("OPS symbol_fundamental_snapshot as_of range:",
      qo("SELECT COUNT(*),MIN(as_of),MAX(as_of),COUNT(DISTINCT as_of) FROM symbol_fundamental_snapshot"))
print("OPS capital_flow_snapshots trade_date range:",
      qo("SELECT COUNT(*),MIN(trade_date),MAX(trade_date) FROM capital_flow_snapshots"))

print("\n### Q18 indices contaminating the OPS store the backtest reads")
for r in qo("""SELECT symbol,COUNT(*) n,MIN(trade_date),MAX(trade_date) FROM daily_bar_cache
   WHERE symbol IN ('SH000001','SH000300','000001','300750','600519','920099') GROUP BY symbol ORDER BY symbol"""):
    print(r)
h.close(); o.close()
