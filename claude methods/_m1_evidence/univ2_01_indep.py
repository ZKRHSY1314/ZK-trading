# -*- coding: utf-8 -*-
import sqlite3
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
c = ro(MH); c.row_factory = sqlite3.Row
def q(sql, p=()):
    return c.execute(sql, p).fetchall()

print("### A. DDL of instruments (is symbol the PK -> rows==distinct securities?)")
print(q("SELECT sql FROM sqlite_master WHERE name='instruments'")[0][0])

print("\n### A2. rows vs DISTINCT symbols (guard against row-vs-security conflation)")
for r in q("SELECT COUNT(*) AS n_rows, COUNT(DISTINCT symbol) AS n_distinct_symbols, "
           "COUNT(delist_date) AS n_delist_nonnull FROM instruments"):
    print(dict(r))

print("\n### B. typeof(delist_date) census -- catches empty-string / 'None' / 'NaT' sentinels")
for r in q("SELECT typeof(delist_date) AS t, COUNT(*) AS n, "
           "MIN(COALESCE(delist_date,'<null>')) AS mn, MAX(COALESCE(delist_date,'<null>')) AS mx "
           "FROM instruments GROUP BY typeof(delist_date)"):
    print(dict(r))

print("\n### B2. anything that even LOOKS like a date in delist_date (no IS NOT NULL used)")
for r in q("SELECT COUNT(*) AS n FROM instruments "
           "WHERE TRIM(COALESCE(CAST(delist_date AS TEXT),'')) <> ''"):
    print(dict(r))

print("\n### C. status census by asset_type/exchange (do NOT count indices as stocks)")
for r in q("SELECT status, asset_type, exchange, COUNT(*) AS n, "
           "SUM(CASE WHEN delist_date IS NULL THEN 1 ELSE 0 END) AS n_null_delist, "
           "SUM(CASE WHEN list_date IS NULL THEN 1 ELSE 0 END) AS n_null_list "
           "FROM instruments GROUP BY status, asset_type, exchange ORDER BY status, exchange"):
    print(dict(r))

print("\n### D. the non-active rows in full")
for r in q("SELECT symbol,name,exchange,asset_type,board,list_date,delist_date,status,provider,"
           "fetched_at,created_at,updated_at FROM instruments WHERE status IS NOT 'active' ORDER BY symbol"):
    print(dict(r))

print("\n### E. distinct updated_at among inactive rows -- can updated_at date the delisting?")
for r in q("SELECT status, updated_at, COUNT(*) AS n FROM instruments "
           "GROUP BY status, updated_at ORDER BY status, updated_at"):
    print(dict(r))

print("\n### F. universe_snapshots -- could delisting be bounded by snapshot membership diffs?")
for r in q("SELECT id, universe_name, snapshot_date, provider, member_count, created_at "
           "FROM universe_snapshots ORDER BY snapshot_date, id"):
    print(dict(r))
c.close()
