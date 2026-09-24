import sqlite3
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
m = ro(MH); q=lambda s,*a: m.execute(s,a).fetchall()
def one(s,*a):
    r=m.execute(s,a).fetchone(); return r[0] if r else None
print("G. MARKET_HISTORY VINTAGE FIELDS")
print(" rows                :", f"{one('SELECT COUNT(*) FROM daily_bars'):,}")
print(" distinct (sym,date) :", f"{one('SELECT COUNT(*) FROM (SELECT DISTINCT symbol,trade_date FROM daily_bars)'):,}")
print(" distinct row_hash   :", f"{one('SELECT COUNT(DISTINCT row_hash) FROM daily_bars'):,}")
print(" adjustment_mode     :", q("SELECT adjustment_mode,COUNT(*) FROM daily_bars GROUP BY 1"))
print(" trade_date range    :", q("SELECT MIN(trade_date),MAX(trade_date) FROM daily_bars"))
print(" provider census     :", q("SELECT provider,COUNT(*) FROM daily_bars GROUP BY 1 ORDER BY 2 DESC LIMIT 10"))
print(" fetched_at day census:")
for r in q("SELECT substr(replace(fetched_at,'T',' '),1,10) d,COUNT(*) n FROM daily_bars GROUP BY 1 ORDER BY n DESC LIMIT 12"):
    print("   ", r)
print(" available_at NULL   :", f"{one('SELECT COUNT(*) FROM daily_bars WHERE available_at IS NULL'):,}")
print(" available_at sample :", q("SELECT available_at,trade_date,fetched_at FROM daily_bars WHERE available_at IS NOT NULL LIMIT 5"))
print(" created_at<>updated_at rows:", f"{one(chr(10).join(['SELECT COUNT(*) FROM daily_bars WHERE substr(replace(updated_at,chr(84),chr(32)),1,10) <> substr(replace(created_at,chr(84),chr(32)),1,10)'])):,}")
print(" updated_at day census:")
for r in q("SELECT substr(replace(updated_at,'T',' '),1,10) d,COUNT(*) n FROM daily_bars GROUP BY 1 ORDER BY n DESC LIMIT 8"):
    print("   ", r)
print(" created_at day census:")
for r in q("SELECT substr(replace(created_at,'T',' '),1,10) d,COUNT(*) n FROM daily_bars GROUP BY 1 ORDER BY n DESC LIMIT 8"):
    print("   ", r)
print(" ingest_runs:")
for r in q("SELECT id,dataset_name,provider,adjustment_mode,status,substr(requested_at,1,19),inserted_row_count,updated_row_count FROM ingest_runs ORDER BY id DESC LIMIT 12"):
    print("   ", r)
print(" instruments exchange census:", q("SELECT exchange,COUNT(*) FROM instruments GROUP BY 1"))
m.close()
