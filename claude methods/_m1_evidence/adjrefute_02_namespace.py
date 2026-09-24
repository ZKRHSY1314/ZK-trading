import sqlite3
from collections import defaultdict
OP = r"D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
print("### symbol namespace shapes in window", flush=True)
rows = c.execute("""
SELECT symbol, COUNT(*) n, MIN(trade_date) d0, MAX(trade_date) d1, COUNT(DISTINCT source) nsrc
FROM daily_bar_cache
WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'
GROUP BY symbol""").fetchall()
def shape(s):
    if s[:2] in ('BJ','SH','SZ') and s[2:].isdigit(): return 'PREFIXED_'+s[:2]
    if s.isdigit() and len(s)==6: return 'BARE6'
    return 'OTHER:'+s
sh = defaultdict(list)
for s,n,d0,d1,ns in rows: sh[shape(s)].append((s,n,d0,d1,ns))
for k,v in sorted(sh.items(), key=lambda x:-len(x[1]))[:12]:
    print(f"  {k:16s} {len(v):5d} symbols   e.g. {[x[0] for x in v[:5]]}", flush=True)
print("\n### do bare and prefixed forms collide (same underlying security twice)?", flush=True)
bare = {x[0] for x in sh.get('BARE6',[])}
pref = set()
for k in sh:
    if k.startswith('PREFIXED_'):
        pref |= {x[0] for x in sh[k]}
coll = {b for b in bare if any(p[2:]==b for p in pref)}
print(f"  bare6 symbols: {len(bare)}   prefixed: {len(pref)}   colliding cores: {len(coll)} -> {sorted(coll)[:20]}", flush=True)
print("\n### the non-'ready' / non-qfq rows the backtest actually sees", flush=True)
for r in c.execute("""
SELECT symbol, adjustment_mode, quality_status, source, COUNT(*), MIN(trade_date), MAX(trade_date)
FROM daily_bar_cache
WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'
  AND adjustment_mode <> 'qfq'
GROUP BY 1,2,3,4 ORDER BY 5 DESC LIMIT 25"""):
    print("  ", r, flush=True)
print("\n### how many symbols would the backtest load, and are the 2 index syms among them?", flush=True)
for r in c.execute("""
SELECT symbol, COUNT(*), MIN(trade_date), MAX(trade_date), quality_status
FROM daily_bar_cache
WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04' AND source='akshare.stock_zh_index_daily'
GROUP BY 1"""):
    print("  ", r, flush=True)
print("\n### earliest data anywhere in cache (is the 3y window even populated?)", flush=True)
print("  ", c.execute("SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'").fetchone(), flush=True)
print("  rows in 2023-09-04..2024-04-08:", c.execute("SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2024-04-08'").fetchone(), flush=True)
