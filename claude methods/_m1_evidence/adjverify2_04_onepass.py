import sqlite3, collections, datetime as dt
MH = r"D:\codex-A股交易\market_history.sqlite3"
c = sqlite3.connect("file:"+MH.replace("\\","/")+"?mode=ro", uri=True)
c.execute("PRAGMA query_only=ON")

SQL = "SELECT symbol, trade_date, adjustment_mode, available_at, fetched_at, close FROM daily_bars"
print("SQL (single pass):", SQL)

total=0; null_avail=0; ident=0; differ=0
avail_days=collections.Counter(); fetch_days=collections.Counter()
avail_full=collections.Counter()
mode_rows=collections.Counter(); mode_syms=collections.defaultdict(set)
lag_buckets=collections.Counter()
len_avail=collections.Counter()
# PIT: for each as_of, count rows with trade_date<=as_of AND available_at_date<=as_of
ASOFS=['2023-09-04','2024-06-30','2024-12-31','2025-06-30','2025-12-31','2026-06-30',
       '2026-07-15','2026-07-16','2026-07-19','2026-09-03','2026-09-04']
pit={a:0 for a in ASOFS}; pit_raw={a:0 for a in ASOFS}; nofilter={a:0 for a in ASOFS}
keys_both=collections.defaultdict(set)   # (symbol,trade_date) -> set of modes  (sampled)
def jd(s):
    y,m,d=int(s[0:4]),int(s[5:7]),int(s[8:10]); return dt.date(y,m,d).toordinal()

for sym, td, mode, av, fe, close in c.execute(SQL):
    total+=1
    mode_rows[mode]+=1; mode_syms[mode].add(sym)
    if av is None:
        null_avail+=1; lag_buckets['NULL available_at']+=1
    else:
        len_avail[len(av)]+=1
        if av==fe: ident+=1
        else: differ+=1
        ad=av[:10]
        avail_days[ad]+=1
        avail_full[av]+=1
        lag = jd(ad)-jd(td)
        if lag<0: lag_buckets['lag<0 (impossible)']+=1
        elif lag<=1: lag_buckets['lag 0-1d']+=1
        elif lag<=7: lag_buckets['lag 2-7d']+=1
        elif lag<=30: lag_buckets['lag 8-30d']+=1
        else: lag_buckets['lag>30d']+=1
    if fe is not None: fetch_days[fe[:10]]+=1
    for a in ASOFS:
        if td<=a:
            nofilter[a]+=1
            if av is not None and av[:10]<=a: pit[a]+=1
            if av is not None and av<=a: pit_raw[a]+=1

print(f"\n[A1] total={total}  available_at IS NULL={null_avail}")
print(f"[A2] available_at == fetched_at (byte identical): {ident}   differ: {differ}   -> identical share {ident/max(total-null_avail,1):.6%}")
print(f"[A2b] length(available_at) histogram: {dict(len_avail)}")
print(f"\n[A3] distinct FULL available_at timestamps: {len(avail_full)}")
for v,n in sorted(avail_full.items()): print(f"     {v!r}  {n}")
print(f"\n[A4] distinct available_at DATE days: {len(avail_days)}")
for v,n in sorted(avail_days.items()): print(f"     {v}  {n}")
print(f"\n[A5] distinct fetched_at DATE days: {len(fetch_days)}")
for v,n in sorted(fetch_days.items()): print(f"     {v}  {n}")
print("\n[A6] lag(available_at_date - trade_date) buckets:")
for k,v in sorted(lag_buckets.items(), key=lambda x:-x[1]): print(f"     {k:24s} {v:>9}  {v/total:7.4%}")
gt30 = lag_buckets.get('lag>30d',0)
print(f"     >30d total = {gt30} / {total} = {gt30/total:.4%}")
print("\n[PIT] rows visible under a point-in-time filter (trade_date<=as_of AND available_at<=as_of)")
print(f"{'as_of':12s} {'substr10_cmp':>13s} {'rawstring_cmp':>14s} {'no_pit_filter':>14s}")
for a in ASOFS: print(f"{a:12s} {pit[a]:>13} {pit_raw[a]:>14} {nofilter[a]:>14}")
print("\n[A7] adjustment_mode distribution:")
for m,n in mode_rows.items(): print(f"     {m:8s} rows={n:>9} distinct_symbols={len(mode_syms[m])}")
c.close()
