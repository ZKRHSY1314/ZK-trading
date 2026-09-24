import sqlite3
OP = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
c = ro(OP)
q = lambda s, *a: c.execute(s, a).fetchall()
def one(s,*a):
    r=c.execute(s,a).fetchone(); return r[0] if r else None

W0, W1 = '2023-09-04','2026-09-04'
print("A. DENOMINATOR AUDIT -------------------------------------------------")
print("total rows            :", one("SELECT COUNT(*) FROM daily_bar_cache"))
print("valid-date rows       :", one("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"))
print("invalid-date rows     :", one("SELECT COUNT(*) FROM daily_bar_cache WHERE NOT (trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')"))
print("in-window rows        :", one("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND trade_date BETWEEN ? AND ?", W0, W1))
print("BEFORE window rows    :", one("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND trade_date < ?", W0))
print("AFTER window rows     :", one("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND trade_date > ?", W1))
print("min/max trade_date    :", q("SELECT MIN(trade_date),MAX(trade_date) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"))
print("invalid trade_date ex :", q("SELECT trade_date,COUNT(*) FROM daily_bar_cache WHERE NOT (trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]') GROUP BY 1 ORDER BY 2 DESC LIMIT 5"))
print()
print("distinct symbols in window:", one("SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ?", W0, W1))
print("symbol prefix census (window):")
for r in q("""SELECT CASE WHEN symbol GLOB 'sh*' OR symbol GLOB 'sz*' OR symbol GLOB 'bj*' THEN substr(symbol,1,2)
                         WHEN symbol GLOB '[0-9]*' THEN 'numeric'
                         ELSE 'other' END pfx, COUNT(DISTINCT symbol) nsym, COUNT(*) nrow
              FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ? GROUP BY 1 ORDER BY nrow DESC""", W0, W1):
    print("   ", r)
print("sample symbols:", [r[0] for r in q("SELECT DISTINCT symbol FROM daily_bar_cache LIMIT 15")])
print()
print("B. TIMESTAMP FORMAT AUDIT --------------------------------------------")
print("created_at NULL       :", one("SELECT COUNT(*) FROM daily_bar_cache WHERE created_at IS NULL"))
print("updated_at NULL       :", one("SELECT COUNT(*) FROM daily_bar_cache WHERE updated_at IS NULL"))
print("created_at with 'T'   :", one("SELECT COUNT(*) FROM daily_bar_cache WHERE created_at LIKE '%T%'"))
print("created_at with ' '   :", one("SELECT COUNT(*) FROM daily_bar_cache WHERE created_at LIKE '% %'"))
print("updated_at with 'T'   :", one("SELECT COUNT(*) FROM daily_bar_cache WHERE updated_at LIKE '%T%'"))
print("updated_at with ' '   :", one("SELECT COUNT(*) FROM daily_bar_cache WHERE updated_at LIKE '% %'"))
print("sample created/updated:")
for r in q("SELECT symbol,trade_date,created_at,updated_at,source,adjustment_mode,quality_status FROM daily_bar_cache LIMIT 6"):
    print("   ", r)
c.close()
