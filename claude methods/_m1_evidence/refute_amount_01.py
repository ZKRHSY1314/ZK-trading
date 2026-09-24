import sqlite3, json
LOC = r"D:/codex-A股交易/trading_local.sqlite3"
HIS = r"D:/codex-A股交易/market_history.sqlite3"
con = sqlite3.connect(f"file:{HIS}?mode=ro", uri=True)
con.execute(f"ATTACH DATABASE 'file:{LOC}?mode=ro' AS cache")
q = lambda s: con.execute(s).fetchall()

def show(t, s):
    print("="*90); print(t); print("-- SQL:", " ".join(s.split())); 
    for r in q(s): print("   ", r)

# 0. schema sanity
show("hist schema", "SELECT sql FROM main.sqlite_master WHERE name='daily_bars'")

# 1. TOTAL rows and NULL amount, hist -- reproduce denominator
show("A1 hist totals", """
SELECT COUNT(*) total,
       SUM(amount IS NULL) amt_null,
       SUM(amount IS NOT NULL AND amount<=0) amt_zeroneg,
       SUM(amount>0) amt_pos,
       ROUND(100.0*SUM(amount IS NULL)/COUNT(*),4) pct_null
FROM main.daily_bars""")

# 2. by adjustment_mode  -- the PK has 3 modes; is NULL amount mode-specific?
show("A2 hist by adjustment_mode", """
SELECT adjustment_mode, COUNT(*) rows, SUM(amount IS NULL) amt_null,
       ROUND(100.0*SUM(amount IS NULL)/COUNT(*),3) pct_null
FROM main.daily_bars GROUP BY adjustment_mode ORDER BY rows DESC""")

# 3. CACHE side: what is the cache's OWN amount health? (claim implies cache is good)
show("A3 cache totals", """
SELECT COUNT(*) total,
       SUM(amount IS NULL) amt_null,
       SUM(amount IS NOT NULL AND amount<=0) amt_zeroneg,
       SUM(amount>0) amt_pos,
       ROUND(100.0*SUM(amount IS NULL OR amount<=0)/COUNT(*),4) pct_unusable
FROM cache.daily_bar_cache""")

show("A4 cache by source", """
SELECT source, COUNT(*) rows, SUM(amount IS NULL) amt_null,
       SUM(amount IS NOT NULL AND amount<=0) amt_zeroneg
FROM cache.daily_bar_cache GROUP BY source ORDER BY rows DESC LIMIT 25""")

show("A5 hist by provider", """
SELECT provider, adjustment_mode, COUNT(*) rows, SUM(amount IS NULL) amt_null
FROM main.daily_bars GROUP BY provider, adjustment_mode ORDER BY rows DESC LIMIT 25""")
