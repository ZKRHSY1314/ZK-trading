# -*- coding: utf-8 -*-
"""ADVERSARIAL VERIFICATION of: instruments.delist_date structurally never written.
READ-ONLY. Independent queries (not a re-run of the auditor's)."""
import sqlite3, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
W0, W1 = "2023-09-04", "2026-09-04"

mh = sqlite3.connect("file:%s?mode=ro" % MH, uri=True)
tl = sqlite3.connect("file:%s?mode=ro" % TL, uri=True)

def show(title, con, sql, params=()):
    print("\n" + "=" * 78)
    print(title)
    print("SQL: " + " ".join(sql.split()))
    cur = con.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    print("  " + " | ".join(cols))
    for r in rows:
        print("  " + " | ".join("NULL" if v is None else str(v) for v in r))
    print("  (%d row(s))" % len(rows))
    return rows

print("#" * 78)
print("A. DENOMINATOR AUDIT -- is 5,561 the right denominator? rows vs distinct securities?")
print("#" * 78)

show("A1. instruments: total rows vs DISTINCT symbols (rows-vs-securities check)", mh, """
SELECT COUNT(*) AS total_rows,
       COUNT(DISTINCT symbol) AS distinct_symbols,
       COUNT(*) - COUNT(DISTINCT symbol) AS dup_rows
FROM instruments
""")

show("A2. instruments segmented by asset_type x exchange (are indices inflating it?)", mh, """
SELECT asset_type, exchange, status, COUNT(*) AS n,
       SUM(CASE WHEN delist_date IS NULL THEN 1 ELSE 0 END) AS delist_is_null,
       SUM(CASE WHEN delist_date IS NOT NULL THEN 1 ELSE 0 END) AS delist_not_null
FROM instruments
GROUP BY asset_type, exchange, status
ORDER BY n DESC
""")

print("\n" + "#" * 78)
print("B. TYPE / EMPTY-STRING / SENTINEL AUDIT -- would 'IS NOT NULL' have missed anything?")
print("   (and would a sentinel like '' / '0' / 'None' have been *counted* but be useless?)")
print("#" * 78)

show("B1. typeof(delist_date) histogram -- catches empty string, 0, 'None', blank", mh, """
SELECT typeof(delist_date) AS sqlite_type,
       COUNT(*) AS n,
       MIN(COALESCE(CAST(delist_date AS TEXT),'<null>')) AS min_val,
       MAX(COALESCE(CAST(delist_date AS TEXT),'<null>')) AS max_val
FROM instruments
GROUP BY typeof(delist_date)
""")

show("B2. delist_date usable-as-a-DATE test (length-10 ISO, not blank/sentinel)", mh, """
SELECT COUNT(*) AS total_rows,
       SUM(CASE WHEN delist_date IS NULL THEN 1 ELSE 0 END) AS null_rows,
       SUM(CASE WHEN delist_date IS NOT NULL AND trim(delist_date)='' THEN 1 ELSE 0 END) AS blank_rows,
       SUM(CASE WHEN delist_date IS NOT NULL AND trim(delist_date)<>''
                 AND length(trim(delist_date))=10
                 AND substr(delist_date,5,1)='-' THEN 1 ELSE 0 END) AS iso_date_rows,
       SUM(CASE WHEN delist_date IS NOT NULL AND trim(delist_date)<>''
                 AND NOT (length(trim(delist_date))=10 AND substr(delist_date,5,1)='-')
                THEN 1 ELSE 0 END) AS nonblank_nondate_rows
FROM instruments
""")

show("B3. same test restricted to STOCKS ONLY on real exchanges (no indices) -- correct denominator", mh, """
SELECT COUNT(DISTINCT symbol) AS distinct_stocks,
       SUM(CASE WHEN delist_date IS NULL THEN 1 ELSE 0 END) AS null_delist,
       SUM(CASE WHEN delist_date IS NOT NULL THEN 1 ELSE 0 END) AS any_delist_value,
       SUM(CASE WHEN list_date IS NULL THEN 1 ELSE 0 END) AS null_list_date
FROM instruments
WHERE asset_type='stock' AND exchange IN ('SH','SZ','BJ')
""")

print("\n" + "#" * 78)
print("C. THE 'ONLY 5 DELISTED NAMES' CLAIM -- count distinct securities, check the filter")
print("#" * 78)

show("C1. full status histogram (did they forget a status value? case sensitivity?)", mh, """
SELECT status, COUNT(DISTINCT symbol) AS distinct_symbols, COUNT(*) AS rows
FROM instruments GROUP BY status ORDER BY rows DESC
""")

show("C2. non-active rows in full, incl. created_at/updated_at/fetched_at spread", mh, """
SELECT symbol, name, exchange, asset_type, status, list_date,
       COALESCE(delist_date,'<NULL>') AS delist_date,
       created_at, updated_at, fetched_at, provider
FROM instruments WHERE lower(trim(status)) <> 'active' ORDER BY symbol
""")

mh.close(); tl.close()
