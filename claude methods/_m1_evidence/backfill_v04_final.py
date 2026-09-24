import sqlite3
MH=r"D:\codex-A股交易\market_history.sqlite3"
TL=r"D:\codex-A股交易\trading_local.sqlite3"
c=sqlite3.connect(f"file:{MH}?mode=ro",uri=True)
c.execute(f"ATTACH DATABASE 'file:{TL}?mode=ro' AS tl")
def q(label,sql,p=()):
    print(f"\n--- {label}\nSQL: {' '.join(sql.split())}")
    for r in c.execute(sql,p): print("   ",r)

BASE = """FROM daily_bars d JOIN tl.daily_bar_cache c ON c.symbol=d.symbol AND c.trade_date=d.trade_date
 WHERE d.amount IS NULL AND c.amount IS NOT NULL AND c.quality_status='ready' AND c.adjustment_mode='qfq'"""

q("L1 volume_unit crosstab on the repairable set (does a hand/share mix explain NOT_A_REBASE?)",
  f"SELECT d.volume_unit, c.volume_unit, COUNT(*) {BASE} GROUP BY 1,2 ORDER BY 3 DESC")

q("L2 GRADED repairability of the 1,652,090",
  f"""SELECT CASE
       WHEN c.volume IS NULL OR c.volume=0 THEN 'D_no_volume_cannot_validate'
       WHEN NOT ((c.amount/(c.volume*100.0)) BETWEEN c.low*0.98 AND c.high*1.02) THEN 'C_cache_amount_self_inconsistent'
       WHEN ABS(d.close-c.close)<=0.005*MAX(d.close,c.close) THEN 'A_same_frame_safe_copy'
       WHEN d.volume>0 AND ABS((d.close/c.close)-(c.volume/d.volume))<=0.02 THEN 'B_pure_qfq_rebase_amount_invariant'
       ELSE 'E_frames_do_not_reconcile' END grade, COUNT(*) rows, COUNT(DISTINCT d.symbol) syms
     {BASE} GROUP BY 1 ORDER BY 2 DESC""")

q("L3 CLEAN repairable total (grades A+B only)",
  f"""SELECT COUNT(*) {BASE}
     AND c.volume IS NOT NULL AND c.volume>0
     AND (c.amount/(c.volume*100.0)) BETWEEN c.low*0.98 AND c.high*1.02
     AND ( ABS(d.close-c.close)<=0.005*MAX(d.close,c.close)
           OR (d.volume>0 AND ABS((d.close/c.close)-(c.volume/d.volume))<=0.02) )""")

q("L4 residual needing network or further work = amount_null - clean",
  f"""SELECT (SELECT SUM(amount IS NULL) FROM daily_bars) - (SELECT COUNT(*) {BASE}
     AND c.volume IS NOT NULL AND c.volume>0
     AND (c.amount/(c.volume*100.0)) BETWEEN c.low*0.98 AND c.high*1.02
     AND ( ABS(d.close-c.close)<=0.005*MAX(d.close,c.close)
           OR (d.volume>0 AND ABS((d.close/c.close)-(c.volume/d.volume))<=0.02) )) AS residual""")

q("M1 research-window coverage framing: daily_bars span vs mandated window 2023-09-04..2026-09-04",
  "SELECT MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date) sessions, COUNT(*) rows FROM daily_bars")
q("M2 rows dated before 2024-04-09 (i.e. first ~7 months of the window) in daily_bars",
  "SELECT COUNT(*) FROM daily_bars WHERE trade_date < '2024-04-09'")
c.close()
