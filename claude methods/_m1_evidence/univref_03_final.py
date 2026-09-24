# -*- coding: utf-8 -*-
import sqlite3, datetime
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
W0, W1 = "2023-09-04", "2026-09-04"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
mh, tl = ro(MH), ro(TL)
def show(t, c, s, *a):
    print("\n### " + t); print("SQL: " + " ".join(s.split()))
    try:
        for r in c.execute(s, a).fetchall(): print("   ", r)
    except Exception as e: print("    ERR", e)

print("="*78); print("D. Denominator: calendar days vs TRADING days vs distinct snapshot dates")
d0 = datetime.date(2023,9,4); d1 = datetime.date(2026,9,4)
print(f"   calendar days inclusive = {(d1-d0).days+1}")
show("D1 distinct TRADING dates in window (market_history)", mh,
 "SELECT COUNT(DISTINCT trade_date) FROM daily_bars WHERE trade_date>=? AND trade_date<=?", W0, W1)
show("D2 how many of those trading dates have a universe_snapshot", mh,
 "SELECT COUNT(*) FROM (SELECT DISTINCT trade_date d FROM daily_bars WHERE trade_date>=? AND trade_date<=?)"
 " WHERE d IN (SELECT snapshot_date FROM universe_snapshots)", W0, W1)

print("\n"+"="*78); print("E. Dead-name census: is ANY symbol's history terminating mid-window?")
show("E1 symbols whose last bar < 2026-01-01 (would be 2023/24/25 exits)", mh,
 "SELECT COUNT(*) FROM (SELECT symbol, MAX(trade_date) m FROM daily_bars GROUP BY symbol) WHERE m<'2026-01-01'")
show("E2 same, cache, excluding the invalid 'ERROR' date", tl,
 "SELECT COUNT(*) FROM (SELECT symbol, MAX(trade_date) m FROM daily_bar_cache"
 " WHERE length(trade_date)=10 AND trade_date LIKE '____-__-__' GROUP BY symbol) WHERE m<'2026-01-01'")
show("E3 the invalid trade_date rows that poisoned MAX()", tl,
 "SELECT trade_date, COUNT(*) FROM daily_bar_cache WHERE NOT (length(trade_date)=10 AND trade_date LIKE '____-__-__')"
 " GROUP BY trade_date")
show("E4 the 11 symbols that DO stop mid-2026 -- names + status", mh,
 "SELECT b.symbol, i.name, i.status, i.list_date, i.delist_date, b.m FROM"
 " (SELECT symbol, MAX(trade_date) m FROM daily_bars GROUP BY symbol) b"
 " LEFT JOIN instruments i ON i.symbol=b.symbol WHERE b.m<'2026-08-28' ORDER BY b.m")
show("E5 the 5 'inactive' instruments -- do they have bars, and until when?", mh,
 "SELECT i.symbol, i.name, i.status, i.list_date, i.delist_date,"
 " (SELECT MIN(trade_date) FROM daily_bars b WHERE b.symbol=i.symbol) fst,"
 " (SELECT MAX(trade_date) FROM daily_bars b WHERE b.symbol=i.symbol) lst"
 " FROM instruments i WHERE i.status<>'active'")

print("\n"+"="*78); print("F. Other dated cross-sections the auditor did not check")
for tbl, datecol in (("full_market_feature_runs","*"),("full_market_feature_state","*"),
                     ("candidate_scans","*"),("market_regime_snapshots","*"),
                     ("sector_membership_history","effective_from"),
                     ("sector_membership_snapshots","effective_date")):
    try:
        cols = [r[1] for r in tl.execute(f"PRAGMA table_info({tbl})").fetchall()]
        n = tl.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"\n   {tbl}: {n} rows; cols={cols}")
        for c in cols:
            if any(k in c.lower() for k in ("date","_at","as_of")):
                mn, mx, nd = tl.execute(
                  f"SELECT MIN({c}), MAX({c}), COUNT(DISTINCT {c}) FROM {tbl}").fetchone()
                print(f"      {c}: min={mn} max={mx} distinct={nd}")
    except Exception as e: print("   ERR", tbl, e)

show("F1 sector_membership_history: any effective_from inside window?", tl,
 "SELECT COUNT(*) rows, COUNT(DISTINCT symbol) syms, MIN(effective_from), MAX(effective_from),"
 " SUM(effective_to IS NOT NULL) with_end FROM sector_membership_history")

print("\n"+"="*78); print("G. Are the bar-panel symbols a strict subset of the 2026 survivor master?")
mhs = set(r[0] for r in mh.execute("SELECT DISTINCT symbol FROM daily_bars").fetchall())
inst = set(r[0] for r in mh.execute("SELECT symbol FROM instruments").fetchall())
umem = set(r[0] for r in mh.execute("SELECT DISTINCT symbol FROM universe_members").fetchall())
tls = set(r[0] for r in tl.execute("SELECT DISTINCT symbol FROM daily_bar_cache").fetchall())
print(f"   daily_bars symbols          = {len(mhs)}")
print(f"   instruments symbols         = {len(inst)}")
print(f"   universe_members union      = {len(umem)}")
print(f"   daily_bar_cache symbols     = {len(tls)}")
print(f"   bars - instruments          = {len(mhs-inst)}")
print(f"   instruments - bars          = {len(inst-mhs)} -> {sorted(inst-mhs)[:10]}")
print(f"   universe_members == instruments? {umem==inst}")
print(f"   cache - instruments         = {len(tls-inst)} -> {sorted(tls-inst)[:20]}")
