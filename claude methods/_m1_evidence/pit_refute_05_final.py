import sqlite3
OP=r"D:/codex-A股交易/trading_local.sqlite3"
MH=r"D:/codex-A股交易/market_history.sqlite3"
o=sqlite3.connect(f"file:{OP}?mode=ro",uri=True)
m=sqlite3.connect(f"file:{MH}?mode=ro",uri=True)

print("### P. HARD CEILING ON BAR-ROWS — can 1,170,781 even exist? ###")
print("P1 distinct stock subjects in decisions:", o.execute("SELECT COUNT(DISTINCT subject) FROM forecast_decisions WHERE scope='stock'").fetchone()[0])
print("P2 TOTAL bar rows in daily_bar_cache for those 90 subjects (ALL dates, no cutoff):",
  o.execute("SELECT COUNT(*) FROM daily_bar_cache WHERE symbol IN (SELECT DISTINCT subject FROM forecast_decisions WHERE scope='stock')").fetchone()[0])
print("P3 distinct (symbol,trade_date) reachable by ANY stock pair at/below its cutoff:",
  o.execute("""SELECT COUNT(*) FROM (SELECT DISTINCT b.symbol,b.trade_date FROM
    (SELECT DISTINCT subject, substr(decision_cutoff,1,10) cd FROM forecast_decisions WHERE scope='stock') d
    JOIN daily_bar_cache b ON b.symbol=d.subject AND b.trade_date<=d.cd)""").fetchone()[0])
print("P4 NON-deduplicated sum of pre-cutoff bars over affected pairs (what they likely summed):",
  o.execute("""SELECT COUNT(*) FROM
    (SELECT DISTINCT decision_id,subject,substr(decision_cutoff,1,10) cd FROM forecast_decisions WHERE scope='stock') d
    JOIN daily_bar_cache b ON b.symbol=d.subject AND b.trade_date<=d.cd
    WHERE substr(b.updated_at,1,10)>d.cd""").fetchone()[0])
print("P5 NON-dedup sum over ALL 3900 pairs:",
  o.execute("""SELECT COUNT(*) FROM
    (SELECT DISTINCT decision_id,subject,substr(decision_cutoff,1,10) cd FROM forecast_decisions WHERE scope='stock') d
    JOIN daily_bar_cache b ON b.symbol=d.subject AND b.trade_date<=d.cd""").fetchone()[0])

print("\n### Q. market_history VINTAGE LEGS ###")
print("Q1 daily_bars rows:", m.execute("SELECT COUNT(*) FROM daily_bars").fetchone()[0])
print("Q2 distinct (symbol,trade_date):", m.execute("SELECT COUNT(*) FROM (SELECT DISTINCT symbol,trade_date FROM daily_bars)").fetchone()[0])
print("Q3 distinct row_hash:", m.execute("SELECT COUNT(DISTINCT row_hash) FROM daily_bars").fetchone()[0])
print("Q4 adjustment_mode dist:", m.execute("SELECT adjustment_mode,COUNT(*) FROM daily_bars GROUP BY 1").fetchall())
print("Q5 available_at distinct values:", m.execute("SELECT COUNT(DISTINCT available_at) FROM daily_bars").fetchone()[0])
print("Q6 available_at sample:", m.execute("SELECT DISTINCT available_at FROM daily_bars LIMIT 3").fetchall())
print("Q7 training_dataset_manifests rows:", m.execute("SELECT COUNT(*) FROM training_dataset_manifests").fetchone()[0])
print("Q8 max distinct vintages per (symbol,trade_date):",
  m.execute("SELECT MAX(n) FROM (SELECT COUNT(*) n FROM daily_bars GROUP BY symbol,trade_date)").fetchone()[0])
print("Q9 market_history tables w/ vintage/version/audit/revision:",
  [r[0] for r in m.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%vintage%' OR name LIKE '%version%' OR name LIKE '%audit%' OR name LIKE '%revis%')")])

print("\n### R. FINAL HEADLINE NUMBERS (mine) ###")
tot=o.execute("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'").fetchone()[0]
res=o.execute("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND trade_date BETWEEN '2023-09-04' AND '2026-09-04' AND substr(updated_at,1,10)>substr(created_at,1,10)").fetchone()[0]
print(f"R1 restated-on-later-day rows: {res}/{tot} = {res/tot*100:.2f}%")
print(f"R2 affected stock pairs: 3630/3900 = {3630/3900*100:.2f}%")
print(f"R3 affected stock decision ROWS: 18150/19500 = {18150/19500*100:.2f}%")
print(f"R4 affected of ALL decision rows: 18150/20082 = {18150/20082*100:.2f}%")
o.close(); m.close()
