import sqlite3, json, collections
OP=r"D:/codex-A股交易/trading_local.sqlite3"
c=sqlite3.connect(f"file:{OP}?mode=ro", uri=True); c.row_factory=sqlite3.Row
q=lambda s,p=(): c.execute(s,p).fetchall()

rows=q("SELECT id,config_json,metrics_json,benchmark_json,execution_warnings_json,created_at,completed_at FROM historical_backtest_runs ORDER BY id")

print("### E. metrics_json key census across all 39 runs")
keycount=collections.Counter(); valsets=collections.defaultdict(collections.Counter)
for r in rows:
    m=json.loads(r["metrics_json"])
    for k,v in m.items():
        keycount[k]+=1
        valsets[k][json.dumps(v) if isinstance(v,(dict,list)) else v]+=1
for k in sorted(keycount):
    vs=valsets[k]
    print(f"  {k:32s} present_in={keycount[k]:2d}/39  distinct_values={len(vs):2d}  {list(vs.items())[:4]}")
print()

print("### F. benchmark_json -- IS THE BENCHMARK ACTUALLY POPULATED? (the audited dimension)")
bstats=collections.Counter()
sample=None
for r in rows:
    b=json.loads(r["benchmark_json"])
    if not b: bstats["EMPTY {}"]+=1; continue
    bstats["nonempty"]+=1
    if sample is None: sample=(r["id"],b)
    keys=tuple(sorted(b.keys())); bstats[f"keys={keys}"]+=1
print(" ", dict(bstats))
if sample:
    rid,b=sample
    print(f"  sample run {rid}:")
    for k,v in b.items():
        if isinstance(v,list):
            print(f"    {k}: list len={len(v)} head={v[:3]} tail={v[-2:]}")
        else:
            print(f"    {k}: {v!r}")
print()

print("### G. execution_warnings_json")
wc=collections.Counter()
for r in rows:
    w=json.loads(r["execution_warnings_json"])
    wc[f"len={len(w)}"]+=1
    for item in w[:50]:
        wc["WARN:"+ (json.dumps(item)[:160])]+=1
for k,v in wc.most_common(30): print(f"  {v:3d}  {k}")
print()

print("### H. config_json distinct shapes")
cfgs=collections.Counter()
for r in rows:
    cfg=json.loads(r["config_json"])
    cfgs[json.dumps(cfg,sort_keys=True)]+=1
for s,n in cfgs.most_common():
    print(f"  n={n}: {s[:1200]}")
