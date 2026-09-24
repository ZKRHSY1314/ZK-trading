# -*- coding: utf-8 -*-
import sqlite3
from collections import Counter
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
mh = ro(MH); mh.row_factory = sqlite3.Row
tl = ro(TL); tl.row_factory = sqlite3.Row

print("### K. TL symbol format sample")
print([r[0] for r in tl.execute("SELECT DISTINCT symbol FROM daily_bar_cache LIMIT 12").fetchall()])
print("### K2. TL trade_date sanity (note the 'ERROR' literal seen earlier)")
for r in tl.execute("SELECT trade_date, COUNT(*) n FROM daily_bar_cache "
                    "WHERE LENGTH(trade_date)<>10 GROUP BY trade_date ORDER BY n DESC LIMIT 5"):
    print("   ", dict(r))
print("### K3. TL real max date (length-10 only)")
print(dict(tl.execute("SELECT MIN(trade_date) mn, MAX(trade_date) mx FROM daily_bar_cache "
                      "WHERE LENGTH(trade_date)=10").fetchone()))

print("\n### L. per-symbol bar-count cap in MH daily_bars (is 500 a hard cap?)")
for r in mh.execute("SELECT n_bars, COUNT(*) n_symbols FROM "
                    "(SELECT symbol, COUNT(*) n_bars FROM daily_bars GROUP BY symbol) "
                    "GROUP BY n_bars ORDER BY n_symbols DESC LIMIT 6"):
    print("   ", dict(r))

print("\n### M. SURVIVOR-SNAPSHOT TEST")
print("    instruments.created_at range == when the catalog first existed:")
for r in mh.execute("SELECT SUBSTR(created_at,1,10) d, COUNT(*) n FROM instruments "
                    "GROUP BY d ORDER BY d"):
    print("   ", dict(r))
print("    active count vs newest a_share_official_catalog snapshot member_count:")
print("   active =", mh.execute("SELECT COUNT(*) FROM instruments WHERE status='active'").fetchone()[0])
print("   newest official snapshot =", dict(mh.execute(
  "SELECT snapshot_date, member_count FROM universe_snapshots "
  "WHERE universe_name='a_share_official_catalog' ORDER BY snapshot_date DESC, id DESC LIMIT 1").fetchone()))

print("\n### N. CEASED-TRADING census, correct symbol format, TL daily_bar_cache")
tl_syms = {}
for r in tl.execute("SELECT symbol, MAX(trade_date) mx, MIN(trade_date) mn FROM daily_bar_cache "
                    "WHERE LENGTH(trade_date)=10 GROUP BY symbol").fetchall():
    tl_syms[str(r['symbol'])] = (r['mn'], r['mx'])
print("    TL distinct symbols with valid dates:", len(tl_syms))
mx_all = max(v[1] for v in tl_syms.values())
print("    TL global max trade_date:", mx_all)
ceased = {s:v for s,v in tl_syms.items() if v[1] < '2026-08-01'}
print(f"    TL symbols whose LAST bar < 2026-08-01 (ceased/stale): {len(ceased)}")
byyear = Counter(v[1][:4] for v in ceased.values())
print("    their last-bar year:", dict(sorted(byyear.items())))

print("\n### O. Do those ceased symbols appear in instruments, and with what status?")
inst = {str(r['symbol']): r['status'] for r in mh.execute("SELECT symbol,status FROM instruments").fetchall()}
def variants(s):
    s = str(s)
    return [s, s[2:] if len(s)>6 else s, 'SH'+s, 'SZ'+s, 'BJ'+s]
cnt = Counter()
for s in ceased:
    hit = next((inst[v] for v in variants(s) if v in inst), '<ABSENT from instruments>')
    cnt[hit] += 1
for k,v in cnt.most_common(): print(f"     {k}: {v}")
mh.close(); tl.close()
