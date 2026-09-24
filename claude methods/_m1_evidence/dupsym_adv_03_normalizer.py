import sqlite3, re, sys
sys.path.insert(0, r"D:/codex-A股交易/backend")
OP = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True); c.row_factory = sqlite3.Row; return c
op = ro(OP)
def q(sql, p=()):
    return [dict(r) for r in op.execute(sql, p).fetchall()]
def show(t, rows, n=25):
    print("="*90); print(t)
    if not rows: print("    <empty>")
    for r in rows[:n]: print("   ", r)
    if len(rows) > n: print(f"    ... {len(rows)-n} more")

# reimplement the shipped normalizer locally (no app import, no storage init)
def normalize_a_share_code(symbol):
    m = re.search(r"(\d{6})", symbol)
    if not m: raise ValueError(symbol)
    return m.group(1)
def with_exchange_prefix(symbol):
    code = normalize_a_share_code(symbol)
    return f"SH{code}" if code.startswith(("6","9")) else f"SZ{code}"

print("### Applying the SHIPPED normalizer to the 4 bare spellings")
real = {r["code"]: r["syms"] for r in q("""
SELECT substr(symbol,3) AS code, GROUP_CONCAT(DISTINCT symbol) AS syms
FROM daily_bar_cache WHERE LENGTH(symbol)=8 GROUP BY substr(symbol,3)""")}
for bare in ["000001","300750","600519","920099"]:
    mapped = with_exchange_prefix(bare)
    exists = q("SELECT COUNT(*) n FROM daily_bar_cache WHERE symbol=?", (mapped,))[0]["n"]
    print(f"   bare {bare} -> normalizer says {mapped:9s} | rows for that spelling in cache = {exists:6d} "
          f"| spellings actually carrying code {bare}: {real.get(bare)}")

show("N1 does SH920099 exist at all?", q("SELECT symbol, COUNT(*) n FROM daily_bar_cache WHERE symbol IN ('SH920099','BJ920099') GROUP BY symbol"))

show("N2 BLAST RADIUS of with_exchange_prefix: prefixed symbols the rule would MISROUTE", q("""
SELECT CASE WHEN substr(symbol,3,1) IN ('6','9') THEN 'SH' ELSE 'SZ' END AS rule_says,
       substr(symbol,1,2) AS actual_prefix,
       COUNT(DISTINCT symbol) AS n_securities, COUNT(*) AS n_rows
FROM daily_bar_cache WHERE LENGTH(symbol)=8
GROUP BY rule_says, actual_prefix ORDER BY rule_says, actual_prefix"""))

show("N3 the misrouted set (rule=SH but actually BJ) - sample", q("""
SELECT DISTINCT symbol FROM daily_bar_cache
WHERE LENGTH(symbol)=8 AND substr(symbol,3,1) IN ('6','9') AND substr(symbol,1,2)<>'SH'
ORDER BY symbol LIMIT 12"""))

show("N4 CRITICAL: can with_exchange_prefix EVER emit SH000001? (code '000001' starts with '0')", [{
  "with_exchange_prefix('000001')": with_exchange_prefix("000001"),
  "starts_with_6_or_9": "000001".startswith(("6","9")),
  "verdict": "SH000001 is UNREACHABLE from bare code 000001 via the shipped normalizer"}])

show("N5 shadow-row created_at vs newest backtest run created_at (were any runs contaminated?)", q("""
SELECT (SELECT MIN(created_at) FROM daily_bar_cache WHERE LENGTH(symbol)=6) AS shadow_first_written,
       (SELECT MAX(created_at) FROM daily_bar_cache WHERE LENGTH(symbol)=6) AS shadow_last_written,
       (SELECT MAX(created_at) FROM historical_backtest_runs) AS newest_backtest_run,
       (SELECT COUNT(*) FROM historical_backtest_runs
          WHERE created_at >= (SELECT MIN(created_at) FROM daily_bar_cache WHERE LENGTH(symbol)=6)) AS runs_after_shadow_appeared"""))

show("N6 bare rows by source (writer path that produced them)", q("""
SELECT source, COUNT(*) n_rows, COUNT(DISTINCT symbol) n_syms
FROM daily_bar_cache WHERE LENGTH(symbol)=6 GROUP BY source ORDER BY n_rows DESC"""))
