# -*- coding: utf-8 -*-
"""Read-only survivorship audit, part 5: manifest content, snapshot churn rate, decision universe."""
import sqlite3, sys, io, json, os, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"


def ro(p):
    return sqlite3.connect("file:%s?mode=ro" % p, uri=True)


mh = ro(MH)
tl = ro(TL)


def show(tag, conn, sql, params=(), limit=None):
    rows = conn.execute(sql, params).fetchall()
    print("\n### %s" % tag)
    print("SQL: %s" % " ".join(sql.split()))
    if params:
        print("PARAMS: %r" % (params,))
    it = rows if limit is None else rows[:limit]
    for r in it:
        print("   ", r)
    if limit is not None and len(rows) > limit:
        print("    ... (%d rows total)" % len(rows))
    return rows


print("=" * 100)
print("SECTION 19  current_a_share_universe.json content analysis")
print("=" * 100)
p = r"D:/codex-A股交易/backend/logs/current_a_share_universe.json"
with open(p, "r", encoding="utf-8") as fh:
    man = json.load(fh)
members = man["members"]
print("manifest_kind      = %r" % man.get("manifest_kind"))
print("observed_at        = %r" % man.get("observed_at"))
print("universe_count     = %r" % man.get("universe_count"))
print("len(members)       = %d" % len(members))
print("member field names = %s" % sorted(members[0].keys()))
print("has any 'snapshot_date'/'as_of'/'effective_date' key at top level? %s" %
      [k for k in man if k.lower() in ("snapshot_date", "as_of", "effective_date", "date")])
cnt = collections.Counter(m.get("status") for m in members)
print("status distribution in manifest: %r" % dict(cnt))
print("members with a delist_date key : %d" % sum(1 for m in members if "delist_date" in m))
print("members with non-null list_date: %d / %d" % (sum(1 for m in members if m.get("list_date")), len(members)))
ld = sorted(m["list_date"] for m in members if m.get("list_date"))
print("list_date min/max              : %s .. %s" % (ld[0], ld[-1]))
print("members whose name contains ST : %d" % sum(1 for m in members if "ST" in (m.get("name") or "")))
print("members whose name contains 退 : %d" % sum(1 for m in members if "退" in (m.get("name") or "")))
print("VERDICT: this manifest carries ONE observed_at timestamp for the whole file; it is a CURRENT snapshot.")

print("=" * 100)
print("SECTION 20  churn rate measured from consecutive universe snapshots")
print("=" * 100)
snaps = mh.execute(
    "SELECT id, universe_name, snapshot_date, fetched_at, member_count FROM universe_snapshots "
    "ORDER BY universe_name, fetched_at").fetchall()
sets = {}
for sid, name, sd, fa, mc in snaps:
    syms = set(r[0] for r in mh.execute("SELECT symbol FROM universe_members WHERE snapshot_id=?", (sid,)))
    sets[sid] = (name, sd, fa, syms)
print("\nSQL: SELECT symbol FROM universe_members WHERE snapshot_id=? (per snapshot), diffed in python")
by_name = collections.defaultdict(list)
for sid, (name, sd, fa, syms) in sets.items():
    by_name[name].append((fa, sd, sid, syms))
for name, lst in sorted(by_name.items()):
    lst.sort()
    print("\n-- universe_name=%s" % name)
    for i in range(1, len(lst)):
        fa0, sd0, id0, s0 = lst[i - 1]
        fa1, sd1, id1, s1 = lst[i]
        removed = sorted(s0 - s1)
        added = sorted(s1 - s0)
        print("   %s(%s) -> %s(%s):  removed=%d  added=%d" % (sd0, id0, sd1, id1, len(removed), len(added)))
        if removed:
            print("      removed symbols: %s" % removed[:20])

print("=" * 100)
print("SECTION 21  the decision universe actually used by the cockpit")
print("=" * 100)
show("forecast_decisions: stock-scope subjects and cutoff range", tl,
     "SELECT scope, COUNT(*), COUNT(DISTINCT subject), MIN(decision_cutoff), MAX(decision_cutoff) "
     "FROM forecast_decisions GROUP BY scope")
show("forecast_decisions stock subjects that are NOT in market_history.instruments (delisted?)", tl,
     "SELECT COUNT(DISTINCT subject) FROM forecast_decisions WHERE scope='stock'")

print("=" * 100)
print("SECTION 22  cross-check: decision subjects vs instruments catalog")
print("=" * 100)
subs = set(r[0] for r in tl.execute("SELECT DISTINCT subject FROM forecast_decisions WHERE scope='stock'"))
inst = set(r[0] for r in mh.execute("SELECT symbol FROM instruments"))
inst_bare = set(s[2:] if len(s) > 2 and s[:2] in ("SH", "SZ", "BJ") else s for s in inst)
print("SQL(tl): SELECT DISTINCT subject FROM forecast_decisions WHERE scope='stock'")
print("SQL(mh): SELECT symbol FROM instruments")
print("distinct stock subjects        = %d" % len(subs))
print("sample subjects                = %s" % sorted(subs)[:10])
print("subjects not in instruments (raw)   = %d" % len(subs - inst))
print("subjects not in instruments (bare)  = %d" % len(set(s for s in subs if s not in inst and s not in inst_bare)))
print("sample unmatched               = %s" % sorted(set(s for s in subs if s not in inst and s not in inst_bare))[:20])

print("=" * 100)
print("SECTION 23  daily_bar_cache provenance columns (source / quality_status) as universe evidence")
print("=" * 100)
show("daily_bar_cache source distribution", tl,
     "SELECT source, COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date), MAX(trade_date) "
     "FROM daily_bar_cache GROUP BY source ORDER BY 2 DESC")
show("daily_bars provider distribution", mh,
     "SELECT provider, COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date), MAX(trade_date) "
     "FROM daily_bars GROUP BY provider ORDER BY 2 DESC")
mh.close()
tl.close()
