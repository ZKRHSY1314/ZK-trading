import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
TL = r"D:/codex-A股交易/trading_local.sqlite3"; MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
tl, mh = ro(TL), ro(MH); a, b = tl.cursor(), mh.cursor()
GL = "trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"

print("### 8. PER-SYMBOL DEPTH -- cache (group by symbol) vs mh (group by symbol AND by symbol+adj_mode)")
q = (f"SELECT MAX(n), MIN(n), COUNT(*) FROM (SELECT symbol, COUNT(DISTINCT trade_date) n "
     f"FROM daily_bar_cache WHERE {GL} GROUP BY symbol)")
print(" cache  max/min/nsym:", a.execute(q).fetchone())
q = (f"SELECT MAX(n) FROM (SELECT symbol, COUNT(DISTINCT trade_date) n FROM daily_bars WHERE {GL} GROUP BY symbol)")
print(" mh by symbol only (all adj modes pooled)  max distinct dates:", b.execute(q).fetchone()[0])
q = (f"SELECT MAX(n) FROM (SELECT symbol, adjustment_mode, COUNT(*) n FROM daily_bars WHERE {GL} "
     f"GROUP BY symbol, adjustment_mode)")
print(" mh by (symbol,adjustment_mode)  max rows:", b.execute(q).fetchone()[0])
print(" mh adjustment_mode breakdown:", b.execute(
  "SELECT adjustment_mode, COUNT(*), COUNT(DISTINCT symbol) FROM daily_bars GROUP BY adjustment_mode").fetchall())

for thr in (730, 600, 587, 538):
    q = (f"SELECT COUNT(*) FROM (SELECT symbol, COUNT(DISTINCT trade_date) n FROM daily_bar_cache "
         f"WHERE {GL} GROUP BY symbol HAVING n >= {thr})")
    c1 = a.execute(q).fetchone()[0]
    q = (f"SELECT COUNT(*) FROM (SELECT symbol, COUNT(DISTINCT trade_date) n FROM daily_bars "
         f"WHERE {GL} GROUP BY symbol HAVING n >= {thr})")
    c2 = b.execute(q).fetchone()[0]
    print(f"   symbols with >= {thr} distinct sessions:  cache={c1}  mh={c2}")

print()
print("### 9. THE 6 SYMBOLS NOT IN instruments (incl. real indices SH000001/SH000300) -- do THEY reach back further?")
for s in ('000001','300750','600519','920099','SH000001','SH000300'):
    r = a.execute("SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM daily_bar_cache WHERE symbol=?", (s,)).fetchone()
    print(f"   cache {s:10s} min={r[0]} max={r[1]} n={r[2]}")

print()
print("### 10. EVERY OTHER DATE-BEARING TABLE -- does ANY hold pre-2023-09-04 or pre-2024-04-09 market history?")
probes_tl = [("capital_flow_snapshots","trade_date"),("historical_backtest_daily_equity","trade_date"),
 ("full_market_feature_state","trade_date"),("full_market_feature_state","as_of_date"),
 ("global_market_bars","bar_time"),("forecast_decisions","available_at"),
 ("sector_membership_snapshots","effective_date"),("symbol_fundamental_snapshot","as_of"),
 ("trade_records","trade_date"),("trade_cases","trade_date"),("disclosure_facts","available_at"),
 ("dataset2_staging_records","signal_date"),("full_market_feature_runs","as_of_date"),
 ("stock_profiles","launch_date")]
for t, c in probes_tl:
    try:
        r = a.execute(f'SELECT MIN("{c}"), MAX("{c}"), COUNT(*) FROM "{t}" WHERE "{c}" IS NOT NULL').fetchone()
        print(f"   TL {t}.{c}: min={r[0]} max={r[1]} n={r[2]}")
    except Exception as e: print(f"   TL {t}.{c}: ERR {e}")
r = a.execute("SELECT MIN(start_date), MAX(end_date), COUNT(*) FROM historical_backtest_runs").fetchone()
print(f"   TL historical_backtest_runs: earliest start_date={r[0]} latest end_date={r[1]} n={r[2]}")
print("   TL backtest runs claiming start_date < 2024-06-24:",
      a.execute("SELECT COUNT(*) FROM historical_backtest_runs WHERE start_date < '2024-06-24'").fetchone()[0])
for t, c in [("universe_snapshots","snapshot_date"),("instruments","list_date"),("instruments","delist_date")]:
    r = b.execute(f'SELECT MIN("{c}"), MAX("{c}"), COUNT(*) FROM "{t}" WHERE "{c}" IS NOT NULL').fetchone()
    print(f"   MH {t}.{c}: min={r[0]} max={r[1]} n={r[2]}")
print("   MH daily_bars.available_at min/max:", b.execute(
  "SELECT MIN(available_at), MAX(available_at) FROM daily_bars WHERE available_at IS NOT NULL").fetchone())

print()
print("### 11. WRITE HISTORY of the cache (was it one bounded backfill?)")
print("   cache created_at min/max:", a.execute("SELECT MIN(created_at), MAX(created_at) FROM daily_bar_cache").fetchone())
print("   rows by created_at month vs the MIN trade_date they reached:")
for r in a.execute(f"SELECT substr(created_at,1,7) m, COUNT(*), MIN(trade_date), MAX(trade_date) "
                   f"FROM daily_bar_cache WHERE {GL} GROUP BY m ORDER BY m").fetchall():
    print("     ", r)
tl.close(); mh.close()
