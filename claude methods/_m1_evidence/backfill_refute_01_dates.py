import sqlite3
L = r"D:/codex-A股交易/trading_local.sqlite3"
H = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

W0, W1 = '2023-09-04', '2026-09-04'
lc, hc = ro(L), ro(H)

def show(title, sql, con, params=()):
    print(f"--- {title}")
    print(f"    SQL: {' '.join(sql.split())}")
    for r in con.execute(sql, params).fetchall():
        print("    ->", r)
    print()

print("########## Q1  daily_bar_cache absolute date extremes, NO length filter")
show("cache min/max raw (no length filter -- catches string-format outliers)",
     "SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM daily_bar_cache", lc)

print("########## Q2  any trade_date NOT in 10-char ISO form? (string-compare bug hunt)")
show("non-ISO trade_date values",
     "SELECT length(trade_date) AS L, COUNT(*), MIN(trade_date), MAX(trade_date) "
     "FROM daily_bar_cache GROUP BY L ORDER BY L", lc)

print("########## Q3  rows STRICTLY BEFORE the claimed floor 2024-04-09, both DBs")
show("cache rows < 2024-04-09 (lexicographic, ISO-safe)",
     "SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date < '2024-04-09'", lc)
show("cache rows in 2023-09-04..2024-04-08",
     "SELECT COUNT(*), COUNT(DISTINCT symbol), COUNT(DISTINCT trade_date) FROM daily_bar_cache "
     "WHERE trade_date >= '2023-09-04' AND trade_date <= '2024-04-08'", lc)
show("hist daily_bars min/max + rows < 2024-04-09",
     "SELECT MIN(trade_date), MAX(trade_date), COUNT(*), "
     "SUM(CASE WHEN trade_date < '2024-04-09' THEN 1 ELSE 0 END) FROM daily_bars", hc)
show("hist daily_bars min per adjustment_mode (do qfq/hfq reach further back?)",
     "SELECT adjustment_mode, MIN(trade_date), MAX(trade_date), COUNT(*), COUNT(DISTINCT symbol) "
     "FROM daily_bars GROUP BY adjustment_mode", hc)

print("########## Q4  OTHER local tables that could hold pre-2024-04-09 daily bars")
show("global_market_bars extremes",
     "SELECT MIN(trade_date), MAX(trade_date), COUNT(*), COUNT(DISTINCT symbol) FROM global_market_bars", lc)
for t in ("technical_indicators","capital_flow_snapshots","full_market_feature_state","sector_membership_history"):
    cols = [r[1] for r in lc.execute(f"PRAGMA table_info({t})").fetchall()]
    dcol = next((c for c in cols if c in ("trade_date","as_of_date","snapshot_date","date","effective_date")), None)
    print(f"--- {t}: date col = {dcol}; cols = {cols[:12]}")
    if dcol:
        print(f"    SQL: SELECT MIN({dcol}), MAX({dcol}), COUNT(*) FROM {t}")
        print("    ->", lc.execute(f"SELECT MIN({dcol}), MAX({dcol}), COUNT(*) FROM {t}").fetchone())
    print()

print("########## Q5  cache floor: is it uniform, or do SOME symbols reach earlier?")
show("distinct earliest-date-per-symbol, 20 earliest",
     "SELECT first_d, COUNT(*) n FROM (SELECT symbol, MIN(trade_date) first_d FROM daily_bar_cache GROUP BY symbol) "
     "GROUP BY first_d ORDER BY first_d LIMIT 20", lc)

print("########## Q6  distinct sessions actually present in window, per DB and UNIONED")
show("cache distinct sessions in window",
     "SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date BETWEEN ? AND ?", lc, (W0,W1))
show("hist distinct sessions in window",
     "SELECT COUNT(DISTINCT trade_date) FROM daily_bars WHERE trade_date BETWEEN ? AND ?", hc, (W0,W1))
lc.close(); hc.close()
