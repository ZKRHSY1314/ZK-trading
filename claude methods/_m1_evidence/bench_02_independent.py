# -*- coding: utf-8 -*-
import sqlite3, re, sys
sys.stdout.reconfigure(encoding="utf-8")
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)

W0, W1 = "2023-09-04", "2026-09-04"

c = ro(MH)
print("### A. instruments: distinct asset_type / board / status / provider (NOT just exchange)")
for col in ("asset_type","board","status","provider","exchange"):
    q = f"SELECT {col}, COUNT(*) FROM instruments GROUP BY {col} ORDER BY 2 DESC"
    print(f"  SQL: {q}")
    for v,n in c.execute(q).fetchall(): print(f"      {col}={v!r:28s} {n}")

print("\n### B. instruments.name searched for index/ETF wording (their SQL never touched name)")
q = ("SELECT symbol,name,exchange,asset_type,board FROM instruments WHERE "
     "name LIKE '%指数%' OR name LIKE '%指%' OR name LIKE '%ETF%' OR name LIKE '%沪深%' "
     "OR name LIKE '%中证%' OR name LIKE '%上证%' OR name LIKE '%深证%' OR name LIKE '%创业板指%' "
     "OR name LIKE '%基金%' OR name LIKE '%LOF%' OR name LIKE '%index%' OR name LIKE '%Index%'")
print("  SQL:", q)
rows = c.execute(q).fetchall()
print(f"      matches = {len(rows)}")
for r in rows[:40]: print("      ", r)
print("  name NULL/empty count:",
      c.execute("SELECT COUNT(*) FROM instruments WHERE name IS NULL OR trim(name)=''").fetchone()[0])

print("\n### C. FULL symbol-shape census of instruments (regex in python, no prefix guessing)")
syms = [r[0] for r in c.execute("SELECT symbol FROM instruments").fetchall()]
stock_re = re.compile(r"^(SH6[0-9]{5}|SZ(00|30)[0-9]{4}|BJ(43|83|87|92|9[0-9])[0-9]{4})$")
buckets = {}
for s in syms:
    buckets.setdefault("STOCK_SHAPE" if stock_re.match(s) else "NON_STOCK_SHAPE", []).append(s)
for k,v in buckets.items(): print(f"      {k}: {len(v)}")
print("      non-stock-shaped examples:", buckets.get("NON_STOCK_SHAPE", [])[:30])

print("\n### D. Index-code test using REAL CN index numbering, applied to instruments AND daily_bars")
# SH000xxx/SH950xxx = SSE&CSI indices; SZ399xxx = SZSE indices; BJ899xxx = BSE index
idx_re = re.compile(r"^(SH(000|950)[0-9]{3}|SZ399[0-9]{3}|BJ899[0-9]{3}|000300|000905|000016|399006|399001|000001)$")
print("      instruments matching index shape:", [s for s in syms if idx_re.match(s)])
dsyms = [r[0] for r in c.execute("SELECT DISTINCT symbol FROM daily_bars").fetchall()]
print("      daily_bars distinct symbols:", len(dsyms))
print("      daily_bars matching index shape:", [s for s in dsyms if idx_re.match(s)])
print("      daily_bars symbols NOT stock-shaped:", [s for s in dsyms if not stock_re.match(s)][:30])

print("\n### E. Is daily_bars.symbol a strict subset of instruments? (orphan check)")
q = "SELECT COUNT(DISTINCT b.symbol) FROM daily_bars b LEFT JOIN instruments i ON i.symbol=b.symbol WHERE i.symbol IS NULL"
print("  SQL:", q, "->", c.execute(q).fetchone()[0])

print("\n### F. universe_snapshots — is any of the 12 a BENCHMARK/index universe?")
q = "SELECT id,universe_name,snapshot_date,provider,member_count,metadata_json FROM universe_snapshots ORDER BY snapshot_date"
print("  SQL:", q)
for r in c.execute(q).fetchall(): print("      ", r[:5], (r[5] or "")[:160])

print("\n### G. universe_members: any member that is not a plain stock? any weight (index weights)?")
q = "SELECT COUNT(*), COUNT(weight), MIN(weight), MAX(weight) FROM universe_members"
print("  SQL:", q, "->", c.execute(q).fetchone())
c.close()
