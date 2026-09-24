# -*- coding: utf-8 -*-
import sqlite3, os
cands = [
 r"D:/codex-A股交易/backend/trading_local.sqlite3",
 r"D:/codex-A股交易/logs/backups/trading_local.continuous-test.20260713-143554.sqlite3",
 r"D:/codex-A股交易/logs/backups/trading_local.pre-refactor-smoke.20260712-103726.sqlite3",
 r"D:/codex-A股交易/logs/backups/trading_local.pre-sidebar-refactor.20260713-190846.sqlite3",
 r"D:/codex-A股交易/output/backups/market_history_20260715_182750_pre_full_universe.sqlite3",
 r"D:/codex-A股交易/output/backups/trading_local_20260715_182750_pre_full_universe.sqlite3",
 r"D:/codex-A股交易/output/backups/trading_local_20260715_192304_pre_qfq_recovery.sqlite3",
 r"D:/codex-A股交易/output/backups/trading_local_20260715_pre_amount_restore.sqlite3",
 r"D:/codex-A股交易/output/backups/trading_local_20260715_pre_qfq_refresh.sqlite3",
]
SQL = """SELECT COUNT(*) AS n, MIN(CAST(trade_date AS TEXT)) AS lo, MAX(CAST(trade_date AS TEXT)) AS hi,
         SUM(CASE WHEN CAST(replace(CAST(trade_date AS TEXT),'-','') AS INTEGER)
                  BETWEEN 19900101 AND 20240408 THEN 1 ELSE 0 END) AS rows_before_2024_04_09
         FROM {t}"""
print("SQL template:", " ".join(SQL.split()))
print()
for p in cands:
    if not os.path.exists(p):
        print(f"MISSING {p}"); continue
    sz = os.path.getsize(p)/1e9
    try:
        c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        tabs = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        t = "daily_bar_cache" if "daily_bar_cache" in tabs else ("daily_bars" if "daily_bars" in tabs else None)
        if t is None:
            print(f"{os.path.basename(p):62s} {sz:5.2f}GB  no bar table"); c.close(); continue
        n, lo, hi, pre = c.execute(SQL.format(t=t)).fetchone()
        print(f"{os.path.basename(p):62s} {sz:5.2f}GB  {t:15s} n={n:>9} lo={lo} hi={hi} rows_before_2024_04_09={pre}")
        c.close()
    except Exception as e:
        print(f"{os.path.basename(p):62s} ERROR {e}")
