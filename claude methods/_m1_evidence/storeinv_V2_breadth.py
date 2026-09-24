import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
tl, mh = ro(TL), ro(MH); a, b = tl.cursor(), mh.cursor()
GL = "trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'"

print("### 5. INDEX CONTAMINATION: classify cache symbols against market_history.instruments")
inst = dict(b.execute("SELECT symbol, exchange FROM instruments").fetchall())
atyp = dict(b.execute("SELECT symbol, asset_type FROM instruments").fetchall())
print(" instruments exchange breakdown:", b.execute(
  "SELECT exchange, COUNT(*) FROM instruments GROUP BY exchange ORDER BY 2 DESC").fetchall())
print(" instruments asset_type breakdown:", b.execute(
  "SELECT asset_type, COUNT(*) FROM instruments GROUP BY asset_type ORDER BY 2 DESC").fetchall())
cache_syms = [r[0] for r in a.execute(f"SELECT DISTINCT symbol FROM daily_bar_cache WHERE {GL}").fetchall()]
idx = [s for s in cache_syms if inst.get(s) == 'INDEX']
unk = [s for s in cache_syms if s not in inst]
print(f" cache distinct symbols={len(cache_syms)}  classified INDEX={len(idx)}  not-in-instruments={len(unk)}")
print(f" -> STOCK-ONLY denominator (cache) = {len(cache_syms)-len(idx)-0} incl unknown; strict-known-nonindex = {len([s for s in cache_syms if s in inst and inst[s]!='INDEX'])}")
print(" sample INDEX syms:", idx[:10], " sample unknown:", unk[:10])

print()
print("### 6. BREADTH RAMP -- distinct STOCK symbols per session (indices excluded), first 40 sessions")
idxset = set(idx)
rows = a.execute(f"SELECT trade_date, symbol FROM daily_bar_cache WHERE {GL} AND trade_date<'2024-08-01'").fetchall()
from collections import defaultdict
per = defaultdict(set)
for d, s in rows: per[d].add(s)
ds = sorted(per)
print(f" sessions present before 2024-08-01: {len(ds)}")
for d in ds[:40]:
    allsym = len(per[d]); stock = len(per[d]-idxset)
    print(f"   {d}  all={allsym:5d}  stock-only={stock:5d}")

print()
print("### 7. FIRST SESSION crossing multiple breadth thresholds (stock-only) -- is 4000 arbitrary?")
allrows = a.execute(f"SELECT trade_date, symbol FROM daily_bar_cache WHERE {GL}").fetchall()
per2 = defaultdict(set)
for d, s in allrows: per2[d].add(s)
sess = sorted(per2)
counts = {d: len(per2[d]-idxset) for d in sess}
for thr in (100, 500, 1000, 2000, 3000, 4000, 4500, 5000):
    first = next((d for d in sess if counts[d] >= thr), None)
    print(f"   first session with >= {thr:5d} stocks: {first}")
print(f" median stock breadth over all {len(sess)} sessions:",
      sorted(counts.values())[len(counts)//2], " max:", max(counts.values()))
tl.close(); mh.close()
