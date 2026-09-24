import sqlite3
MH=r"D:\codex-A股交易\market_history.sqlite3"
TL=r"D:\codex-A股交易\trading_local.sqlite3"
W0,W1="2023-09-04","2026-09-04"
c=sqlite3.connect(f"file:{MH}?mode=ro",uri=True)
c.execute(f"ATTACH DATABASE 'file:{TL}?mode=ro' AS tl")
def q(label,sql,p=()):
    print(f"\n--- {label}\nSQL: {' '.join(sql.split())}")
    for r in c.execute(sql,p): print("   ",r)

q("A1 symbol namespace samples (mh vs tl)",
  "SELECT 'mh' src, symbol FROM daily_bars LIMIT 3")
q("A1b cache symbol samples",
  "SELECT 'tl' src, symbol FROM tl.daily_bar_cache LIMIT 3")
q("A2 symbol-format overlap: mh symbols not present in cache at all",
  "SELECT COUNT(*) FROM (SELECT DISTINCT symbol FROM daily_bars) m WHERE NOT EXISTS (SELECT 1 FROM tl.daily_bar_cache c WHERE c.symbol=m.symbol)")

q("B1 amount NULL overall (denominator = ALL rows incl indices)",
  "SELECT SUM(amount IS NULL) amt_null, COUNT(*) total, ROUND(100.0*SUM(amount IS NULL)/COUNT(*),2) pct FROM daily_bars")
q("B2 amount NULL EXCLUDING indices (join instruments, exchange<>'INDEX')",
  "SELECT SUM(d.amount IS NULL), COUNT(*), ROUND(100.0*SUM(d.amount IS NULL)/COUNT(*),2) FROM daily_bars d JOIN instruments i ON i.symbol=d.symbol WHERE i.exchange<>'INDEX'")
q("B3 amount NULL inside RESEARCH WINDOW only, stocks only",
  "SELECT SUM(d.amount IS NULL), COUNT(*), ROUND(100.0*SUM(d.amount IS NULL)/COUNT(*),2) FROM daily_bars d JOIN instruments i ON i.symbol=d.symbol WHERE i.exchange<>'INDEX' AND d.trade_date BETWEEN ? AND ?",(W0,W1))
q("B4 amount NULL by year",
  "SELECT substr(trade_date,1,4) yr, COUNT(*) rows, SUM(amount IS NULL) nulls, ROUND(100.0*SUM(amount IS NULL)/COUNT(*),1) pct FROM daily_bars GROUP BY 1 ORDER BY 1")
q("B5 max/min trade_date of NULL vs NOT NULL amount",
  "SELECT amount IS NULL AS is_null, MIN(trade_date), MAX(trade_date), COUNT(*) FROM daily_bars GROUP BY 1")

q("C1 THEIR repair count, reproduced verbatim",
  "SELECT COUNT(*) FROM daily_bars d JOIN tl.daily_bar_cache c ON c.symbol=d.symbol AND c.trade_date=d.trade_date WHERE d.amount IS NULL AND c.amount IS NOT NULL AND c.quality_status='ready' AND c.adjustment_mode='qfq'")
q("C2 repair count, distinct (symbol,trade_date) cells -- fan-out check",
  "SELECT COUNT(DISTINCT d.symbol||'|'||d.trade_date) FROM daily_bars d JOIN tl.daily_bar_cache c ON c.symbol=d.symbol AND c.trade_date=d.trade_date WHERE d.amount IS NULL AND c.amount IS NOT NULL AND c.quality_status='ready' AND c.adjustment_mode='qfq'")
q("C3 repairable, distinct symbols, and index-vs-stock split",
  "SELECT i.exchange, COUNT(*) rows, COUNT(DISTINCT d.symbol) syms FROM daily_bars d JOIN tl.daily_bar_cache c ON c.symbol=d.symbol AND c.trade_date=d.trade_date JOIN instruments i ON i.symbol=d.symbol WHERE d.amount IS NULL AND c.amount IS NOT NULL AND c.quality_status='ready' AND c.adjustment_mode='qfq' GROUP BY 1 ORDER BY 2 DESC")
q("C4 repairable INSIDE research window only",
  "SELECT COUNT(*) FROM daily_bars d JOIN tl.daily_bar_cache c ON c.symbol=d.symbol AND c.trade_date=d.trade_date WHERE d.amount IS NULL AND c.amount IS NOT NULL AND c.quality_status='ready' AND c.adjustment_mode='qfq' AND d.trade_date BETWEEN ? AND ?",(W0,W1))
q("C5 amount-NULL rows with NO usable cache partner (unrepairable residue)",
  "SELECT COUNT(*) FROM daily_bars d WHERE d.amount IS NULL AND NOT EXISTS (SELECT 1 FROM tl.daily_bar_cache c WHERE c.symbol=d.symbol AND c.trade_date=d.trade_date AND c.amount IS NOT NULL AND c.quality_status='ready' AND c.adjustment_mode='qfq')")
c.close()
