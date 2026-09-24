import sqlite3, os, json, datetime as dt
ROOT=r"D:\codex-A股交易"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro",uri=True)
mh=ro(os.path.join(ROOT,"market_history.sqlite3")); mh.row_factory=sqlite3.Row
SQL="""SELECT id, dataset_name, status, requested_at, created_at,
              processed_symbol_count, inserted_row_count, updated_row_count,
              json_extract(parameters_json,'$.bars_per_symbol') AS bars_per_symbol
       FROM ingest_runs ORDER BY id"""
print("SQL:", " ".join(SQL.split()))
rows=[dict(r) for r in mh.execute(SQL).fetchall()]
def parse(s):
    s=str(s).replace("T"," ")
    if "+" in s: s=s.split("+")[0]
    return dt.datetime.fromisoformat(s.strip())
tot_sym=tot_rows=0; tot_sec=0.0
per=[]
for r in rows:
    # requested_at is local +08:00, created_at is UTC -> convert
    ra=parse(r["requested_at"]); ca=parse(r["created_at"])+dt.timedelta(hours=8)
    sec=(ca-ra).total_seconds()
    rowsw=r["inserted_row_count"]+r["updated_row_count"]
    per.append((r["id"],r["dataset_name"],r["status"],sec,r["processed_symbol_count"],rowsw,r["bars_per_symbol"]))
    if sec>0:
        tot_sec+=sec; tot_sym+=r["processed_symbol_count"]; tot_rows+=rowsw
print(f"{'id':>4} {'dataset':34} {'status':9} {'sec':>8} {'syms':>6} {'rows':>9} {'bars/sym':>8} {'sym/s':>8} {'rows/s':>10}")
for i,d,s,sec,sy,rw,bps in per:
    sps=f"{sy/sec:.2f}" if sec>0 else "-"
    rps=f"{rw/sec:.0f}" if sec>0 else "-"
    print(f"{i:>4} {d[:34]:34} {s:9} {sec:>8.1f} {sy:>6} {rw:>9} {str(bps):>8} {sps:>8} {rps:>10}")
print()
print(f"TOTAL over runs with sec>0: seconds={tot_sec:.1f} symbols={tot_sym} rows_written={tot_rows}")
print(f"  aggregate symbols/s = {tot_sym/tot_sec:.2f}   rows/s = {tot_rows/tot_sec:.0f}")
print()
allrows=sum(r["inserted_row_count"]+r["updated_row_count"] for r in rows)
allsym=sum(r["processed_symbol_count"] for r in rows)
print(f"ALL 100 runs: symbols_processed={allsym} rows_written={allrows} inserted={sum(r['inserted_row_count'] for r in rows)} updated={sum(r['updated_row_count'] for r in rows)}")
first=parse(rows[0]["created_at"]); last=parse(rows[-1]["created_at"])
print(f"first_run_created_at={rows[0]['created_at']} last={rows[-1]['created_at']} span_days={(last-first).total_seconds()/86400:.1f}")
