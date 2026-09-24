import json, sqlite3, os, glob, datetime

CAL = r"D:/codex-A股交易/backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json"
TL  = r"D:/codex-A股交易/trading_local.sqlite3"
MH  = r"D:/codex-A股交易/market_history.sqlite3"

def ro(path):
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    c.execute("PRAGMA query_only=1")
    return c

cal = json.load(open(CAL, encoding="utf-8"))
cal = sorted({f"{d[0:4]}-{d[4:6]}-{d[6:8]}" for d in cal})
calset = set(cal)
print("=== OFFLINE CALENDAR (akshare file_fold/calendar.json, zero network) ===")
print("total sessions:", len(cal), "range:", cal[0], "..", cal[-1])

def cnt(a, b):
    return sum(1 for d in cal if a <= d <= b)

W0, W1 = "2023-09-04", "2026-09-04"
print("W  2023-09-04..2026-09-04 sessions :", cnt(W0, W1))
print("A  2023-09-04..2024-04-08 sessions :", cnt("2023-09-04", "2024-04-08"))
print("B  2024-04-09..2024-06-21 sessions :", cnt("2024-04-09", "2024-06-21"))
print("C  2024-06-24..2026-09-03 sessions :", cnt("2024-06-24", "2026-09-03"))
print("D  2026-09-04                       :", cnt("2026-09-04", "2026-09-04"))
print("gap 2023-09-04..2024-06-21 sessions:", cnt("2023-09-04", "2024-06-21"))
print("warmup 250 sessions before window start would begin:",
      cal[max(0, cal.index("2023-09-04") - 250)] if "2023-09-04" in calset else "n/a(2023-09-04 not a session)")
print("is 2023-09-04 a session?", "2023-09-04" in calset)
print("2025 full-year sessions:", cnt("2025-01-01", "2025-12-31"))

tl = ro(TL); mh = ro(MH)

print()
print("=== OBSERVED spine vs CALENDAR ===")
obs = [r[0] for r in tl.execute(
  "SELECT DISTINCT trade_date FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' "
  "AND trade_date BETWEEN ? AND ? ORDER BY 1", (W0, W1))]
print("observed distinct trade_date in window:", len(obs), obs[0], "..", obs[-1])
notcal = [d for d in obs if d not in calset]
print("observed trade_date NOT in exchange calendar:", len(notcal), notcal[:20])
wknd = [d for d in obs if datetime.date.fromisoformat(d).weekday() >= 5]
print("observed trade_date falling on SAT/SUN:", len(wknd), wknd[:20])
missing_in_C = [d for d in cal if "2024-06-24" <= d <= "2026-09-03" and d not in set(obs)]
print("calendar sessions inside dense segment C with NO bars at all:", len(missing_in_C), missing_in_C[:20])
mh_obs = set(r[0] for r in mh.execute("SELECT DISTINCT trade_date FROM daily_bars WHERE trade_date BETWEEN ? AND ?", (W0, W1)))
print("market_history distinct trade_date in window:", len(mh_obs))
print("mh dates not in calendar:", sorted(d for d in mh_obs if d not in calset)[:10])

print()
print("=== TABLE INVENTORY (contract: store inventory) ===")
for name, con in (("trading_local", tl), ("market_history", mh)):
    tabs = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY 1")]
    print(f"-- {name}: {len(tabs)} tables")
    rows = []
    for t in tabs:
        try:
            n = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        except Exception as e:
            n = f"ERR {e}"
        rows.append((n if isinstance(n, int) else -1, t, n))
    rows.sort(reverse=True)
    for n, t, raw in rows[:40]:
        print(f"   {t:48s} {raw}")
    print(f"   ... ({len(rows)} tables total; non-empty: {sum(1 for r in rows if isinstance(r[2],int) and r[2]>0)})")

print()
print("=== DB FILES ON DISK (report claims '9 database snapshots incl. all backups') ===")
pats = [r"D:/codex-A股交易/*.sqlite3", r"D:/codex-A股交易/backend/*.sqlite3",
        r"D:/codex-A股交易/logs/backups/*.sqlite3", r"D:/codex-A股交易/output/backups/*.sqlite3"]
files = []
for p in pats:
    files.extend(glob.glob(p))
for f in sorted(files):
    print(f"   {os.path.getsize(f)/1e6:10.1f} MB  {f}")
print("   count:", len(files))
