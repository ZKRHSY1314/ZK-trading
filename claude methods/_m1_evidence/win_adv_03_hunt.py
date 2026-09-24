# -*- coding: utf-8 -*-
import sqlite3
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
def hdr(t): print("\n"+"="*74+"\n"+t+"\n"+"="*74)
mh = ro(MH); tl = ro(TL)

hdr("M. MEMBERSHIP CHURN between the two official-catalog snapshots (real PIT evidence?)")
q = """
WITH a AS (SELECT symbol FROM universe_members WHERE snapshot_id=18),   -- 2026-07-16 official
     b AS (SELECT symbol FROM universe_members WHERE snapshot_id=94)    -- 2026-09-04 official
SELECT (SELECT COUNT(*) FROM a) n_jul,
       (SELECT COUNT(*) FROM b) n_sep,
       (SELECT COUNT(*) FROM a WHERE symbol NOT IN (SELECT symbol FROM b)) dropped_out,
       (SELECT COUNT(*) FROM b WHERE symbol NOT IN (SELECT symbol FROM a)) added_in
"""
print("SQL:", q.strip())
print("   (n_jul, n_sep, dropped_out, added_in) =", mh.execute(q).fetchone())
q2 = """SELECT symbol FROM universe_members WHERE snapshot_id=18
        AND symbol NOT IN (SELECT symbol FROM universe_members WHERE snapshot_id=94) LIMIT 30"""
print("   dropped symbols:", [r[0] for r in mh.execute(q2)])

hdr("N. Hunt ANY delisting/listing-history evidence in trading_local")
for tbl in ("stock_profiles","symbol_fundamental_snapshot","candidate_lifecycle",
            "sector_membership_snapshots","full_market_feature_state","price_readiness_reports",
            "global_market_bars","technical_indicators"):
    try:
        cols = [r[1] for r in tl.execute(f"PRAGMA table_info({tbl})")]
        n = tl.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        hits = [c for c in cols if any(k in c.lower() for k in ("delist","list_date","listing","status","ipo","suspend","halt","st_flag","active"))]
        print(f"   {tbl:34s} rows={n:<9} listing-ish cols={hits}")
    except Exception as e:
        print(f"   {tbl}: ERR {e}")

q = "SELECT state, COUNT(*) FROM candidate_lifecycle GROUP BY 1"
print("SQL:", q); 
for r in tl.execute(q): print("     ", r)

hdr("O. stock_profiles / sector_membership -- do they carry historical dates?")
for tbl, datecol in (("stock_profiles",None),("sector_membership_snapshots","snapshot_date"),
                     ("sector_membership_history",None)):
    try:
        cols = [r[1] for r in tl.execute(f"PRAGMA table_info({tbl})")]
        n = tl.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"   {tbl} rows={n} cols={cols}")
        dc = datecol or next((c for c in cols if 'date' in c.lower() or c.lower().endswith('_at')), None)
        if dc and n:
            q = f"SELECT MIN({dc}),MAX({dc}),COUNT(DISTINCT {dc}) FROM {tbl}"
            print(f"     SQL: {q} ->", tl.execute(q).fetchone())
    except Exception as e:
        print(f"   {tbl}: ERR {e}")

hdr("P. Does daily_bars.available_at give ANY point-in-time listing evidence pre-2026-07?")
q = "SELECT MIN(available_at), MAX(available_at), COUNT(DISTINCT substr(available_at,1,10)) FROM daily_bars"
print("SQL:", q); print("   ", mh.execute(q).fetchone())
q = "SELECT substr(available_at,1,7) ym, COUNT(*) FROM daily_bars GROUP BY 1 ORDER BY 1 LIMIT 12"
print("SQL:", q)
for r in mh.execute(q): print("   ", r)
q = "SELECT MIN(fetched_at),MAX(fetched_at) FROM daily_bars"
print("SQL:", q); print("   ", mh.execute(q).fetchone())

hdr("Q. ingest_runs / instruments provider timeline (independent restatement)")
q = "SELECT MIN(started_at),MAX(started_at),COUNT(*) FROM ingest_runs"
try:
    print("SQL:", q); print("   ", mh.execute(q).fetchone())
except Exception as e:
    print("   ", e, [r[1] for r in mh.execute("PRAGMA table_info(ingest_runs)")])
q = "SELECT provider, COUNT(*), MIN(substr(fetched_at,1,10)), MAX(substr(fetched_at,1,10)) FROM instruments GROUP BY 1"
print("SQL:", q)
for r in mh.execute(q): print("   ", r)
mh.close(); tl.close()
