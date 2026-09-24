# -*- coding: utf-8 -*-
"""Read-only survivorship / universe reconstruction audit."""
import sqlite3, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
W0, W1 = "2023-09-04", "2026-09-04"


def ro(p):
    return sqlite3.connect("file:%s?mode=ro" % p, uri=True)


mh = ro(MH)
tl = ro(TL)


def q(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()


def show(tag, conn, sql, params=(), limit=None):
    rows = q(conn, sql, params)
    print("\n### %s" % tag)
    print("SQL: %s" % " ".join(sql.split()))
    if params:
        print("PARAMS: %r" % (params,))
    if limit:
        for r in rows[:limit]:
            print("   ", r)
        if len(rows) > limit:
            print("    ... (%d rows total)" % len(rows))
    else:
        for r in rows:
            print("   ", r)
    return rows


print("=" * 100)
print("SECTION 1  universe_snapshots (market_history) -- ALL ROWS")
print("=" * 100)
show("universe_snapshots full dump", mh,
     "SELECT id, universe_name, snapshot_date, provider, member_count, fetched_at, source_hash, metadata_json "
     "FROM universe_snapshots ORDER BY snapshot_date, id")

show("universe_snapshots count / date range", mh,
     "SELECT COUNT(*), MIN(snapshot_date), MAX(snapshot_date), COUNT(DISTINCT snapshot_date), "
     "COUNT(DISTINCT universe_name) FROM universe_snapshots")

show("snapshots inside research window", mh,
     "SELECT COUNT(*) FROM universe_snapshots WHERE snapshot_date BETWEEN ? AND ?", (W0, W1))

print("=" * 100)
print("SECTION 2  universe_members")
print("=" * 100)
show("members per snapshot", mh,
     "SELECT s.id, s.universe_name, s.snapshot_date, s.member_count AS declared, "
     "(SELECT COUNT(*) FROM universe_members m WHERE m.snapshot_id=s.id) AS actual "
     "FROM universe_snapshots s ORDER BY s.snapshot_date, s.id")

show("universe_members total + distinct symbols", mh,
     "SELECT COUNT(*), COUNT(DISTINCT symbol), COUNT(DISTINCT snapshot_id) FROM universe_members")

show("histogram: distinct symbols appearing in exactly N snapshots", mh,
     "SELECT n_snaps, COUNT(*) AS n_symbols FROM (SELECT symbol, COUNT(DISTINCT snapshot_id) AS n_snaps "
     "FROM universe_members GROUP BY symbol) GROUP BY n_snaps ORDER BY n_snaps")

show("churn between earliest and latest snapshot per universe_name", mh,
     "WITH first_s AS (SELECT universe_name, MIN(snapshot_date) d FROM universe_snapshots GROUP BY universe_name), "
     "last_s AS (SELECT universe_name, MAX(snapshot_date) d FROM universe_snapshots GROUP BY universe_name) "
     "SELECT f.universe_name, f.d AS first_date, l.d AS last_date, "
     "(SELECT COUNT(*) FROM universe_members m JOIN universe_snapshots s ON s.id=m.snapshot_id "
     " WHERE s.universe_name=f.universe_name AND s.snapshot_date=f.d AND m.symbol NOT IN "
     " (SELECT m2.symbol FROM universe_members m2 JOIN universe_snapshots s2 ON s2.id=m2.snapshot_id "
     "  WHERE s2.universe_name=f.universe_name AND s2.snapshot_date=l.d)) AS dropped, "
     "(SELECT COUNT(*) FROM universe_members m JOIN universe_snapshots s ON s.id=m.snapshot_id "
     " WHERE s.universe_name=f.universe_name AND s.snapshot_date=l.d AND m.symbol NOT IN "
     " (SELECT m2.symbol FROM universe_members m2 JOIN universe_snapshots s2 ON s2.id=m2.snapshot_id "
     "  WHERE s2.universe_name=f.universe_name AND s2.snapshot_date=f.d)) AS added "
     "FROM first_s f JOIN last_s l ON l.universe_name=f.universe_name")

print("=" * 100)
print("SECTION 3  instruments")
print("=" * 100)
show("instruments totals", mh,
     "SELECT COUNT(*) AS total, SUM(list_date IS NOT NULL) AS has_list_date, SUM(list_date IS NULL) AS null_list_date, "
     "SUM(delist_date IS NOT NULL) AS has_delist_date, SUM(delist_date IS NULL) AS null_delist_date FROM instruments")

show("instruments status distribution", mh,
     "SELECT status, COUNT(*) FROM instruments GROUP BY status ORDER BY 2 DESC")

show("instruments asset_type x exchange", mh,
     "SELECT asset_type, exchange, COUNT(*) FROM instruments GROUP BY asset_type, exchange ORDER BY 3 DESC")

show("instruments non-active count", mh,
     "SELECT COUNT(*) FROM instruments WHERE status <> 'active'")

show("stocks (asset_type=stock, exchange SH/SZ/BJ) list/delist coverage", mh,
     "SELECT COUNT(*) AS stocks, SUM(list_date IS NOT NULL) AS with_list_date, "
     "SUM(list_date IS NULL) AS without_list_date, SUM(delist_date IS NOT NULL) AS with_delist_date "
     "FROM instruments WHERE asset_type='stock' AND exchange IN ('SH','SZ','BJ')")

show("instruments provider / fetched_at distribution", mh,
     "SELECT provider, COUNT(*), MIN(fetched_at), MAX(fetched_at) FROM instruments GROUP BY provider")

show("instruments board distribution", mh,
     "SELECT board, COUNT(*) FROM instruments GROUP BY board ORDER BY 2 DESC")

show("list_date min/max + count inside window", mh,
     "SELECT MIN(list_date), MAX(list_date), SUM(list_date BETWEEN ? AND ?) FROM instruments WHERE list_date IS NOT NULL",
     (W0, W1))

print("=" * 100)
print("SECTION 4  THE QUESTION: what was the tradable universe on 2024-03-15?")
print("=" * 100)
AD = "2024-03-15"
show("A) snapshot exactly on 2024-03-15", mh,
     "SELECT COUNT(*) FROM universe_snapshots WHERE snapshot_date = ?", (AD,))
show("B) most recent snapshots on-or-before 2024-03-15", mh,
     "SELECT id, universe_name, snapshot_date, member_count FROM universe_snapshots WHERE snapshot_date <= ? "
     "ORDER BY snapshot_date DESC LIMIT 5", (AD,))
show("C) instruments reconstruction: list_date<=D AND (delist_date IS NULL OR delist_date>D)", mh,
     "SELECT COUNT(*) FROM instruments WHERE asset_type='stock' AND exchange IN ('SH','SZ','BJ') "
     "AND list_date IS NOT NULL AND list_date <= ? AND (delist_date IS NULL OR delist_date > ?)", (AD, AD))
show("C2) stocks excluded from (C) purely because list_date IS NULL", mh,
     "SELECT COUNT(*) FROM instruments WHERE asset_type='stock' AND exchange IN ('SH','SZ','BJ') AND list_date IS NULL")
show("D) bar-presence reconstruction market_history.daily_bars on 2024-03-15 (stock only)", mh,
     "SELECT COUNT(DISTINCT b.symbol) FROM daily_bars b JOIN instruments i ON i.symbol=b.symbol "
     "WHERE b.trade_date = ? AND i.asset_type='stock' AND i.exchange IN ('SH','SZ','BJ')", (AD,))
show("D2) bar-presence market_history.daily_bars on 2024-03-15 (all symbols, any adjustment_mode)", mh,
     "SELECT COUNT(DISTINCT symbol) FROM daily_bars WHERE trade_date = ?", (AD,))
show("E) bar-presence trading_local.daily_bar_cache on 2024-03-15", tl,
     "SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE trade_date = ?", (AD,))
show("F) available_at point-in-time distribution for trade_date 2024-03-15", mh,
     "SELECT COUNT(*), MIN(available_at), MAX(available_at) FROM daily_bars WHERE trade_date = ?", (AD,))
show("F2) distinct available_at values for 2024-03-15 (top 10)", mh,
     "SELECT available_at, COUNT(*) FROM daily_bars WHERE trade_date = ? GROUP BY available_at ORDER BY 2 DESC LIMIT 10",
     (AD,))

print("=" * 100)
print("SECTION 5  sector_membership_* (trading_local) dated evidence?")
print("=" * 100)
show("sector_membership_snapshots aggregate", tl,
     "SELECT COUNT(*), COUNT(DISTINCT source), COUNT(DISTINCT sector), MIN(effective_date), MAX(effective_date), "
     "MIN(observed_at), MAX(observed_at) FROM sector_membership_snapshots")
show("sector_membership_snapshots by effective_date", tl,
     "SELECT effective_date, COUNT(*) AS n_sectors, SUM(member_count) AS members FROM sector_membership_snapshots "
     "GROUP BY effective_date ORDER BY effective_date")
show("sector_membership_snapshot_members totals", tl,
     "SELECT COUNT(*), COUNT(DISTINCT symbol), COUNT(DISTINCT snapshot_id) FROM sector_membership_snapshot_members")
show("sector_membership_history rows", tl,
     "SELECT COUNT(*) FROM sector_membership_history")

print("=" * 100)
print("SECTION 6  bar store global ranges")
print("=" * 100)
show("market_history.daily_bars global range", mh,
     "SELECT MIN(trade_date), MAX(trade_date), COUNT(DISTINCT symbol) FROM daily_bars")
show("trading_local.daily_bar_cache global range", tl,
     "SELECT MIN(trade_date), MAX(trade_date), COUNT(DISTINCT symbol) FROM daily_bar_cache")
show("daily_bars recent dates symbol counts", mh,
     "SELECT trade_date, COUNT(DISTINCT symbol) FROM daily_bars WHERE trade_date >= '2026-08-15' "
     "GROUP BY trade_date ORDER BY trade_date DESC LIMIT 20")
show("daily_bar_cache recent dates symbol counts", tl,
     "SELECT trade_date, COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE trade_date >= '2026-08-15' "
     "GROUP BY trade_date ORDER BY trade_date DESC LIMIT 20")
mh.close()
tl.close()
