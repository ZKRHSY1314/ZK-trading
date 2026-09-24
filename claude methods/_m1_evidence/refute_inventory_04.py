import sqlite3, os, glob
files = [
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
print("### J. did pre-2024-04-09 bars EVER exist? (every backup, read-only)")
for f in files:
    if not os.path.exists(f): print(" MISSING", f); continue
    sz = os.path.getsize(f)/1e9
    try:
        c = sqlite3.connect(f"file:{f}?mode=ro", uri=True)
        tabs = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        out=[]
        for t in ("daily_bar_cache","daily_bars"):
            if t in tabs:
                n, mn, mx = c.execute(f"SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM {t}").fetchone()
                pre = c.execute(f"SELECT COUNT(*) FROM {t} WHERE trade_date < '2023-09-04' AND trade_date GLOB '[0-9]*'").fetchone()[0]
                out.append(f"{t}: rows={n} min={mn} max={mx} rows_before_2023-09-04={pre}")
        print(f"  {os.path.basename(f)} ({sz:.2f}GB): " + ("; ".join(out) if out else "no bar table"))
        c.close()
    except Exception as e:
        print(f"  {os.path.basename(f)}: ERR {e}")

print()
print("### K. cache write history (independent of theirs): when was history written, how far back")
c = sqlite3.connect(r"file:D:/codex-A股交易/trading_local.sqlite3?mode=ro", uri=True)
for r in c.execute("""
SELECT substr(created_at,1,7) AS wrote_month, COUNT(*) rows,
       MIN(trade_date) oldest_bar_written, MAX(trade_date) newest_bar_written,
       COUNT(DISTINCT symbol) syms
FROM daily_bar_cache WHERE trade_date GLOB '[0-9]*'
GROUP BY wrote_month ORDER BY wrote_month"""):
    print("   ", r)
c.close()
