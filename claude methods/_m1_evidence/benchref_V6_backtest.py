import sqlite3, json
TL="D:/codex-A股交易/trading_local.sqlite3"
c=sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
print("### P. benchmark_symbol used by the 39 backtest runs")
for r in c.execute("SELECT benchmark_symbol, COUNT(*), MIN(start_date), MAX(end_date), data_source FROM historical_backtest_runs GROUP BY benchmark_symbol, data_source").fetchall():
    print("   ",r)
print()
print("### Q. Are those backtest windows inside the benchmark's life (2024-06-19..2026-09-02)?")
for r in c.execute("""SELECT id,start_date,end_date,status,benchmark_symbol,
   length(benchmark_json) blen, substr(benchmark_json,1,120) head
   FROM historical_backtest_runs ORDER BY id DESC LIMIT 8""").fetchall():
    print("   ",r)
print()
print("   runs whose start_date precedes benchmark start 2024-06-19:",
   c.execute("SELECT COUNT(*) FROM historical_backtest_runs WHERE start_date < '2024-06-19'").fetchone()[0], "/ 39")
print("   distinct (start_date,end_date):", c.execute("SELECT DISTINCT start_date,end_date FROM historical_backtest_runs ORDER BY 1").fetchall()[:15])
print()
print("### R. what benchmark_json actually holds (is it a real series or empty?)")
row=c.execute("SELECT benchmark_json FROM historical_backtest_runs WHERE benchmark_json IS NOT NULL AND length(benchmark_json)>2 ORDER BY id DESC LIMIT 1").fetchone()
if row:
    try:
        j=json.loads(row[0]); print("   type:",type(j).__name__, "| keys/len:", list(j)[:12] if isinstance(j,dict) else len(j))
        print("   sample:", json.dumps(j, ensure_ascii=False)[:400])
    except Exception as e: print("   unparsed:", row[0][:300])
print()
print("### S. execution_warnings_json mentioning benchmark (37 runs) — what do they say?")
seen=set()
for (w,) in c.execute("SELECT execution_warnings_json FROM historical_backtest_runs WHERE execution_warnings_json LIKE '%benchmark%'").fetchall():
    for item in (json.loads(w) if w and w.strip().startswith('[') else [w]):
        s=str(item)[:200]
        if 'benchmark' in s.lower() and s not in seen:
            seen.add(s); print("   -",s)
    if len(seen)>=8: break
c.close()
