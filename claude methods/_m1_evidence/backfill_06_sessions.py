import sqlite3, os, datetime as dt, collections
ROOT=r"D:\codex-A股交易"
mh=sqlite3.connect(f"file:{os.path.join(ROOT,'market_history.sqlite3')}?mode=ro",uri=True); mh.row_factory=sqlite3.Row
SQL="""SELECT id, dataset_name, status, requested_at, created_at,
              processed_symbol_count, inserted_row_count, updated_row_count,
              json_extract(parameters_json,'$.bars_per_symbol') AS bars_per_symbol
       FROM ingest_runs ORDER BY id"""
print("SQL:", " ".join(SQL.split()))
rows=[dict(r) for r in mh.execute(SQL).fetchall()]
def p(s):
    s=str(s).replace("T"," ");
    if "+" in s: s=s.split("+")[0]
    return dt.datetime.fromisoformat(s.strip())
sess=collections.OrderedDict()
for r in rows: sess.setdefault(r["requested_at"],[]).append(r)
print(f"{'session requested_at':26} {'batches':>7} {'syms':>7} {'rows':>9} {'span_s':>8} {'sym/s':>7} {'rows/s':>8} {'bars/sym':>8} status")
grand_s=grand_r=0; grand_t=0.0
for k,v in sess.items():
    if len(v)<2: 
        span=0.0
    else:
        span=(p(v[-1]["created_at"])-p(v[0]["created_at"])).total_seconds()
    syms=sum(x["processed_symbol_count"] for x in v)-v[0]["processed_symbol_count"]
    rws=sum(x["inserted_row_count"]+x["updated_row_count"] for x in v)-(v[0]["inserted_row_count"]+v[0]["updated_row_count"])
    bps=v[0]["bars_per_symbol"]
    st=collections.Counter(x["status"] for x in v).most_common(1)[0][0]
    sps=f"{syms/span:.2f}" if span>0 else "-"
    rps=f"{rws/span:.0f}" if span>0 else "-"
    print(f"{k[:26]:26} {len(v):>7} {syms:>7} {rws:>9} {span:>8.0f} {sps:>7} {rps:>8} {str(bps):>8} {st}")
    if span>0: grand_s+=syms; grand_r+=rws; grand_t+=span
print()
print(f"AGGREGATE (excluding each session's first batch, which has no measurable start):")
print(f"  seconds={grand_t:.0f} symbols={grand_s} rows_written={grand_r}")
print(f"  symbols/s = {grand_s/grand_t:.2f}    rows/s = {grand_r/grand_t:.0f}")
