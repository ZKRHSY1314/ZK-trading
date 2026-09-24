import sqlite3, datetime as dt
L = r"D:/codex-A股交易/trading_local.sqlite3"
H = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
lc, hc = ro(L), ro(H)
def one(con, sql, p=()):
    r = con.execute(sql, p).fetchone()
    print("SQL:", " ".join(sql.split())); print("   ->", r); print()
    return r

print("### L. EMPIRICAL session-count estimator: same calendar span, later years (real data)")
for a,b in [("2024-09-04","2025-04-08"), ("2025-09-04","2026-04-08")]:
    r = one(lc, "SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache "
                "WHERE length(trade_date)=10 AND trade_date BETWEEN ? AND ?", (a,b))
    print(f"   analogue span {a}..{b} observed sessions = {r[0]}")
print("   -> these bracket the true 2023-09-04..2024-04-08 session count\n")

print("### M. Broad-coverage floor: first session with full market breadth, both DBs")
one(lc, "SELECT MIN(trade_date) FROM (SELECT trade_date, COUNT(DISTINCT symbol) n FROM daily_bar_cache "
        "WHERE length(trade_date)=10 GROUP BY trade_date) WHERE n>=5000")
one(hc, "SELECT MIN(trade_date) FROM (SELECT trade_date, COUNT(DISTINCT symbol) n FROM daily_bars "
        "GROUP BY trade_date) WHERE n>=5000")
print("### M2. rows sitting in the THIN pre-breadth sessions (what 587 is padded with)")
one(lc, "SELECT COUNT(*), COUNT(DISTINCT trade_date), COUNT(DISTINCT symbol) FROM daily_bar_cache "
        "WHERE length(trade_date)=10 AND trade_date BETWEEN '2024-04-09' AND '2024-06-21'")

print("### N. TRUE deficit vs a listing-aware rectangle over the whole window")
# gap sessions synthesized: weekdays minus enumerated CN closures
hol = {"2023-09-29","2023-10-02","2023-10-03","2023-10-04","2023-10-05","2023-10-06",
       "2024-01-01","2024-02-09","2024-02-12","2024-02-13","2024-02-14","2024-02-15",
       "2024-02-16","2024-04-04","2024-04-05"}
d, end, gap = dt.date(2023,9,4), dt.date(2024,4,8), []
while d <= end:
    if d.weekday() < 5 and d.isoformat() not in hol: gap.append(d.isoformat())
    d += dt.timedelta(days=1)
print(f"synthesized gap sessions = {len(gap)}  ({gap[0]} .. {gap[-1]})")
real = [r[0] for r in lc.execute("SELECT DISTINCT trade_date FROM daily_bar_cache "
        "WHERE length(trade_date)=10 AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'").fetchall()]
sessions = sorted(set(gap) | set(real))
print(f"total window sessions (synthesized gap + observed) = {len(sessions)}")
print()
# listing-aware denominator per session
lst = [r[0] for r in hc.execute("SELECT list_date FROM instruments WHERE list_date IS NOT NULL AND list_date<>''").fetchall()]
lst.sort()
import bisect
denom = sum(bisect.bisect_right(lst, s) for s in sessions)
have_l = lc.execute("SELECT COUNT(*) FROM daily_bar_cache WHERE length(trade_date)=10 "
                    "AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'").fetchone()[0]
have_h = hc.execute("SELECT COUNT(*) FROM daily_bars WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'").fetchone()[0]
print(f"listing-aware expected symbol-days over {len(sessions)} sessions = {denom:,}")
print(f"daily_bar_cache rows in window   = {have_l:,}   deficit = {denom-have_l:,}  ({100*(denom-have_l)/denom:.1f}%)")
print(f"market_history rows in window    = {have_h:,}   deficit = {denom-have_h:,}  ({100*(denom-have_h)/denom:.1f}%)")
print()
gapdenom = sum(bisect.bisect_right(lst, s) for s in gap)
print(f"### N2. deficit attributable ONLY to the pre-2024-04-09 gap ({len(gap)} sessions, listing-aware) = {gapdenom:,}")
print(f"   claim's figure = 754,382 (146 x 5,167).  Delta = {754382-gapdenom:+,}")
print()
print("### O. survivorship: is the delist column usable at all?")
one(hc, "SELECT COUNT(*) FROM instruments WHERE delist_date IS NOT NULL AND delist_date<>''")
lc.close(); hc.close()
