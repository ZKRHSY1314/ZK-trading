import sqlite3
OP=r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
c=ro(OP)
q=lambda s,*a: c.execute(s,a).fetchall()
def one(label, sql, *a):
    v=c.execute(sql,a).fetchone()
    print(f"{label:62s} {v}")
    return v

print("### A. DENOMINATOR SANITY (daily_bar_cache) ###")
one("A1 total rows", "SELECT COUNT(*) FROM daily_bar_cache")
one("A2 distinct (symbol,trade_date)", "SELECT COUNT(*) FROM (SELECT DISTINCT symbol,trade_date FROM daily_bar_cache)")
one("A3 distinct symbols", "SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache")
one("A4 min/max trade_date", "SELECT MIN(trade_date),MAX(trade_date) FROM daily_bar_cache")
one("A5 rows malformed trade_date",
    "SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'")
one("A6 rows STRICTLY BEFORE window (<2023-09-04)",
    "SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND trade_date < '2023-09-04'")
one("A7 rows AFTER window (>2026-09-04)",
    "SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND trade_date > '2026-09-04'")
one("A8 rows IN window (their denominator)",
    "SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'")

print("\n### B. SYMBOL NAMESPACE — ARE INDICES IN THE DENOMINATOR? ###")
print("B1 symbol prefix histogram (first 3 chars), top 25:")
for r in q("SELECT substr(symbol,1,3) p, COUNT(DISTINCT symbol) nsym, COUNT(*) nrow FROM daily_bar_cache GROUP BY p ORDER BY nrow DESC LIMIT 25"):
    print("   ",r)
print("B2 sample symbols:", [r[0] for r in q("SELECT DISTINCT symbol FROM daily_bar_cache ORDER BY symbol LIMIT 10")])
print("B3 sample symbols desc:", [r[0] for r in q("SELECT DISTINCT symbol FROM daily_bar_cache ORDER BY symbol DESC LIMIT 10")])
print("B4 symbol length histogram:")
for r in q("SELECT length(symbol) L, COUNT(DISTINCT symbol), COUNT(*) FROM daily_bar_cache GROUP BY L ORDER BY L"):
    print("   ",r)

print("\n### C. created_at / updated_at STRUCTURE ###")
one("C1 created_at NULL", "SELECT COUNT(*) FROM daily_bar_cache WHERE created_at IS NULL")
one("C2 updated_at NULL", "SELECT COUNT(*) FROM daily_bar_cache WHERE updated_at IS NULL")
one("C3 created_at len histogram", "SELECT 1")
for r in q("SELECT length(created_at), COUNT(*) FROM daily_bar_cache GROUP BY 1"):
    print("    created_at len:",r)
for r in q("SELECT length(updated_at), COUNT(*) FROM daily_bar_cache GROUP BY 1"):
    print("    updated_at len:",r)
print("C4 sample created/updated pairs:")
for r in q("SELECT symbol,trade_date,created_at,updated_at FROM daily_bar_cache LIMIT 5"):
    print("   ",r)

print("\n### D. RESTATEMENT COUNT — MY OWN, WITH DIRECTION ###")
W="trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'"
one("D1 window rows, updated_at > created_at (full ts, strictly later)",
    f"SELECT COUNT(*) FROM daily_bar_cache WHERE {W} AND updated_at IS NOT NULL AND created_at IS NOT NULL AND updated_at > created_at")
one("D2 window rows, updated_at < created_at (EARLIER = anomaly)",
    f"SELECT COUNT(*) FROM daily_bar_cache WHERE {W} AND updated_at IS NOT NULL AND created_at IS NOT NULL AND updated_at < created_at")
one("D3 window rows, DAY differs (their metric, either direction)",
    f"SELECT COUNT(*) FROM daily_bar_cache WHERE {W} AND updated_at IS NOT NULL AND substr(updated_at,1,10) <> substr(created_at,1,10)")
one("D4 window rows, LATER DAY only",
    f"SELECT COUNT(*) FROM daily_bar_cache WHERE {W} AND updated_at IS NOT NULL AND created_at IS NOT NULL AND substr(updated_at,1,10) > substr(created_at,1,10)")
one("D5 window rows, EARLIER DAY only",
    f"SELECT COUNT(*) FROM daily_bar_cache WHERE {W} AND updated_at IS NOT NULL AND created_at IS NOT NULL AND substr(updated_at,1,10) < substr(created_at,1,10)")
one("D6 window rows, same day but different timestamp",
    f"SELECT COUNT(*) FROM daily_bar_cache WHERE {W} AND updated_at IS NOT NULL AND created_at IS NOT NULL AND substr(updated_at,1,10)=substr(created_at,1,10) AND updated_at<>created_at")
one("D7 window rows, updated_at == created_at exactly",
    f"SELECT COUNT(*) FROM daily_bar_cache WHERE {W} AND updated_at = created_at")
c.close()
