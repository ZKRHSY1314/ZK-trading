import sqlite3
MH = r"D:/codex-A股交易/market_history.sqlite3"
m = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)
q = lambda s, *a: m.execute(s, a).fetchall()
def one(s, *a):
    r = m.execute(s, a).fetchone(); return r[0] if r else None

s1 = "SELECT COUNT(*) FROM daily_bars WHERE substr(replace(updated_at,'T',' '),1,10) <> substr(replace(created_at,'T',' '),1,10)"
print(" created<>updated rows:", format(one(s1), ','))
print(" available_at == fetched_at rows:", format(one("SELECT COUNT(*) FROM daily_bars WHERE available_at = fetched_at"), ','))
s2 = "SELECT COUNT(*) FROM daily_bars WHERE substr(replace(available_at,'T',' '),1,10) <= trade_date"
print(" rows where available_at day <= trade_date (usable PIT):", format(one(s2), ','))
print(" earliest available_at / earliest trade_date:", q("SELECT MIN(available_at), MIN(trade_date) FROM daily_bars"))
print(" available_at day census:")
for r in q("SELECT substr(replace(available_at,'T',' '),1,10) d,COUNT(*) n FROM daily_bars GROUP BY 1 ORDER BY n DESC LIMIT 8"): print("   ", r)
print(" updated_at day census:")
for r in q("SELECT substr(replace(updated_at,'T',' '),1,10) d,COUNT(*) n FROM daily_bars GROUP BY 1 ORDER BY n DESC LIMIT 8"): print("   ", r)
print(" created_at day census:")
for r in q("SELECT substr(replace(created_at,'T',' '),1,10) d,COUNT(*) n FROM daily_bars GROUP BY 1 ORDER BY n DESC LIMIT 8"): print("   ", r)
print(" ingest_runs (last 12):")
for r in q("SELECT id,dataset_name,provider,status,substr(requested_at,1,19),inserted_row_count,updated_row_count FROM ingest_runs ORDER BY id DESC LIMIT 12"): print("   ", r)
print(" ingest totals inserted/updated:", q("SELECT SUM(inserted_row_count),SUM(updated_row_count) FROM ingest_runs"))
print(" instruments exchange census:", q("SELECT exchange,COUNT(*) FROM instruments GROUP BY 1"))
m.close()
