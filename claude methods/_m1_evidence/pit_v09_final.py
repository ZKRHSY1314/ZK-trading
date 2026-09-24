import sqlite3
OP = r"D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{OP}?mode=ro", uri=True); c.execute("PRAGMA query_only=ON")
c.execute("ATTACH DATABASE 'file:D:/codex-A股交易/market_history.sqlite3?mode=ro' AS mh")
def one(s,*a):
    r=c.execute(s,a).fetchone(); return r[0] if r else None
q=lambda s,*a: c.execute(s,a).fetchall()

print("L. WINDOW-COVERAGE REALITY CHECK (their 'window rows' label)")
print("  rows dated 2023-09-04..2024-04-08 (first 218d of research window):",
      one("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2024-04-08'"))
print("  rows dated 2024-04-09..2026-09-04:",
      one("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date BETWEEN '2024-04-09' AND '2026-09-04'"))
print("  => the BETWEEN window filter removes", 2891617 - one("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'"), "row(s) from the table total")
print()
print("M. INDEX CONTAMINATION IN THEIR DENOMINATOR")
idx = one("SELECT COUNT(*) FROM daily_bar_cache WHERE source LIKE '%index%'")
print("  index-sourced rows in daily_bar_cache:", idx, f"({idx/2891616*100:.4f}% of their denominator)")
print("  non-'qfq' rows:", one("SELECT COUNT(*) FROM daily_bar_cache WHERE adjustment_mode <> 'qfq'"))
print("  symbols in cache not in mh.instruments:",
      one("SELECT COUNT(*) FROM (SELECT DISTINCT symbol FROM daily_bar_cache WHERE symbol NOT IN (SELECT symbol FROM mh.instruments))"))
print()
print("N. HEADLINE NUMBERS SIDE BY SIDE")
base = 2891616
rew  = one("""SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
              AND substr(updated_at,1,10) <> substr(created_at,1,10)""")
print(f"  re-written (their metric, reproduced) : {rew:,} / {base:,} = {rew/base*100:.2f}%")
s = """SELECT COUNT(*), SUM(CASE WHEN ABS(b.close-h.close)>1e-6 OR ABS(b.open-h.open)>1e-6
        OR ABS(b.high-h.high)>1e-6 OR ABS(b.low-h.low)>1e-6 THEN 1 ELSE 0 END)
       FROM daily_bar_cache b JOIN mh.daily_bars h ON h.symbol=b.symbol AND h.trade_date=b.trade_date
       AND h.adjustment_mode='qfq' WHERE b.adjustment_mode='qfq'
       AND substr(replace(h.updated_at,'T',' '),1,10) < '2026-09-01'"""
n, ch = q(s)[0]
print(f"  VALUE-changed (my metric)             : {ch:,} / {n:,} comparable = {ch/n*100:.2f}%")
print(f"  as a share of the whole table         : {ch:,} / {base:,} = {ch/base*100:.2f}%  (floor; {base-n:,} rows unmeasurable)")
print()
print("O. DECISION-SIDE SCALE")
print("  distinct stock decision_ids:", one("SELECT COUNT(DISTINCT decision_id) FROM forecast_decisions WHERE scope='stock'"))
print("  distinct stock subjects    :", one("SELECT COUNT(DISTINCT subject) FROM forecast_decisions WHERE scope='stock'"))
print("  distinct cutoff DAYS       :", one("SELECT COUNT(DISTINCT substr(decision_cutoff,1,10)) FROM forecast_decisions WHERE scope='stock'"))
print("  pairs whose cutoff precedes the 2026-09-03 rewrite: ",
      one("SELECT COUNT(*) FROM (SELECT DISTINCT decision_id,subject FROM forecast_decisions WHERE scope='stock' AND substr(decision_cutoff,1,10)<'2026-09-03')"), "/ 3900 = 93.08% (mechanical ceiling)")
c.close()
