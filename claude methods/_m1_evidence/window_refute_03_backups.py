# -*- coding: utf-8 -*-
import sqlite3, os
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
B = r"D:/codex-A股交易"
paths = [
 f"{B}/logs/backups/trading_local.continuous-test.20260713-143554.sqlite3",
 f"{B}/logs/backups/trading_local.pre-refactor-smoke.20260712-103726.sqlite3",
 f"{B}/logs/backups/trading_local.pre-sidebar-refactor.20260713-190846.sqlite3",
 f"{B}/output/backups/market_history_20260715_182750_pre_full_universe.sqlite3",
 f"{B}/output/backups/trading_local_20260715_182750_pre_full_universe.sqlite3",
 f"{B}/output/backups/trading_local_20260715_192304_pre_qfq_recovery.sqlite3",
 f"{B}/output/backups/trading_local_20260715_pre_amount_restore.sqlite3",
 f"{B}/output/backups/trading_local_20260715_pre_qfq_refresh.sqlite3",
 f"{B}/backend/trading_local.sqlite3",
 f"{B}/claude methods/_m1_evidence/refute_replica.sqlite3",
]
print("#"*100)
print("# L. DOES ANY ON-DISK BACKUP HOLD PRE-2024-04-09 BARS? (would refute 'window does not exist')")
print("#"*100)
for p in paths:
    if not os.path.exists(p): print("  MISSING", p); continue
    try:
        c = ro(p)
        tabs = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        out = []
        for t in ("daily_bar_cache","daily_bars"):
            if t in tabs:
                n, mn, mx = c.execute(f"SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM {t} WHERE length(trade_date)=10").fetchone()
                pre = c.execute(f"SELECT COUNT(*) FROM {t} WHERE length(trade_date)=10 AND trade_date < '2024-04-09'").fetchone()[0]
                prew = c.execute(f"SELECT COUNT(*) FROM {t} WHERE length(trade_date)=10 AND trade_date < '2023-09-04'").fetchone()[0]
                out.append(f"{t}: n={n} min={mn} max={mx} pre_2024_04_09={pre} pre_window={prew}")
        print(f"  {os.path.basename(p)[:58]:60s} {' | '.join(out) if out else '(no bar tables)'}")
        c.close()
    except Exception as e:
        print(f"  {os.path.basename(p)[:58]:60s} ERROR {e}")

print()
print("#"*100)
print("# M. When does a BROAD cross-section actually begin? (2024-04-09 floor may be 1-2 symbols)")
print("#"*100)
h = ro(f"{B}/market_history.sqlite3")
for r in h.execute("""
SELECT b.trade_date, COUNT(DISTINCT b.symbol) AS n_stocks
FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
WHERE i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ')
GROUP BY b.trade_date ORDER BY b.trade_date LIMIT 45""").fetchall():
    print("   ", r)
print("   ...")
for r in h.execute("""
SELECT MIN(trade_date) FROM (
  SELECT b.trade_date, COUNT(DISTINCT b.symbol) c
  FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
  WHERE i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ')
  GROUP BY b.trade_date HAVING c >= 1000)""").fetchall():
    print("   first session with >=1000 distinct stocks:", r)
for r in h.execute("""
SELECT MIN(trade_date) FROM (
  SELECT b.trade_date, COUNT(DISTINCT b.symbol) c
  FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol
  WHERE i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ')
  GROUP BY b.trade_date HAVING c >= 4000)""").fetchall():
    print("   first session with >=4000 distinct stocks:", r)
h.close()
