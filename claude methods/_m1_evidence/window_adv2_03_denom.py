import sqlite3, datetime as dt
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

W0, W1 = "2023-09-04", "2026-09-04"
FLOOR   = "2024-04-09"

def weekdays(a,b):
    d0=dt.date.fromisoformat(a); d1=dt.date.fromisoformat(b); n=0; cal=0
    d=d0
    while d<=d1:
        cal+=1
        if d.weekday()<5: n+=1
        d+=dt.timedelta(days=1)
    return n, cal

print("### E. CALENDAR ARITHMETIC (recomputed independently) ###")
wd_win, cal_win = weekdays(W0, W1)
wd_gap, cal_gap = weekdays(W0, "2024-04-08")
wd_cov, cal_cov = weekdays(FLOOR, W1)
print(f"  window {W0}..{W1}: weekdays={wd_win} calendar_days={cal_win}")
print(f"  gap    {W0}..2024-04-08: weekdays={wd_gap} calendar_days={cal_gap}   <-- their claim said 156 weekdays / 213 calendar days")
print(f"  covered {FLOOR}..{W1}: weekdays={wd_cov} calendar_days={cal_cov}")

print()
print("### F. OBSERVED SESSION DENSITY in the covered sub-period (measured, not assumed) ###")
for db,(path,tbl) in {"trading_local.daily_bar_cache":(TL,"daily_bar_cache"),
                      "market_history.daily_bars":(MH,"daily_bars")}.items():
    c = ro(path)
    q = (f"SELECT COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date) FROM {tbl} "
         f"WHERE trade_date BETWEEN '{FLOOR}' AND '{W1}' AND length(trade_date)=10")
    n,mn,mx = c.execute(q).fetchone()
    print(f"  {db}: distinct sessions={n} range={mn}..{mx}  density={n/wd_cov:.4f} sessions/weekday")
    print(f"    SQL: {q}")
    c.close()

print()
print("### G. SESSION-BASED gap estimate using MEASURED density (not a guess) ###")
c = ro(MH)
n_cov = c.execute(f"SELECT COUNT(DISTINCT trade_date) FROM daily_bars WHERE trade_date BETWEEN '{FLOOR}' AND '{W1}'").fetchone()[0]
c.close()
dens = n_cov/wd_cov
print(f"  measured density {dens:.4f} -> gap sessions ~= {wd_gap}*{dens:.4f} = {wd_gap*dens:.1f}")
print(f"  window total sessions ~= {wd_win}*{dens:.4f} = {wd_win*dens:.1f}")
print(f"  fraction of window MISSING (session-weighted) = {wd_gap*dens/(wd_win*dens):.4f} = {100*wd_gap/wd_win:.2f}%")

print()
print("### H. ARE THERE HOLES *INSIDE* the covered sub-period too? (missing weekdays not explained by w/e) ###")
for db,(path,tbl) in {"trading_local.daily_bar_cache":(TL,"daily_bar_cache"),
                      "market_history.daily_bars":(MH,"daily_bars")}.items():
    c = ro(path)
    have = {r[0] for r in c.execute(f"SELECT DISTINCT trade_date FROM {tbl} WHERE trade_date BETWEEN '{FLOOR}' AND '{W1}' AND length(trade_date)=10")}
    d=dt.date.fromisoformat(FLOOR); end=dt.date.fromisoformat(W1); miss=[]
    while d<=end:
        if d.weekday()<5 and d.isoformat() not in have: miss.append(d.isoformat())
        d+=dt.timedelta(days=1)
    print(f"  {db}: weekdays inside covered range with NO rows = {len(miss)}")
    print(f"    first 12: {miss[:12]}")
    c.close()
