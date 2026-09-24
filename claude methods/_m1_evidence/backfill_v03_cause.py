import sqlite3
OP = r"D:\codex-A股交易\trading_local.sqlite3"
MH = r"D:\codex-A股交易\market_history.sqlite3"
def q(c,s,a=()): return c.execute(s,a).fetchall()
op = sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
mh = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)

print("### J. Is 2024-04-09 the 500th-session-back fingerprint?")
dates = [r[0] for r in q(op,"SELECT DISTINCT trade_date FROM daily_bar_cache WHERE length(trade_date)=10 ORDER BY trade_date")]
print("J1 total distinct sessions in cache:", len(dates), "first:",dates[0],"last:",dates[-1])
print("J2 500th session counting BACK from last (dates[-500]):", dates[-500])
print("J3 the 500-session window would start at %s, but data starts %s -> floor is %d sessions DEEPER than one 500-pull" %
      (dates[-500], dates[0], len(dates)-500))
print("J4 500 sessions FORWARD from the floor ends at:", dates[499])

print()
print("### K. created_at forensics: WHEN were the deepest rows written?")
print("K1 earliest-session rows, created_at range:",
      q(op,"SELECT MIN(created_at), MAX(created_at), COUNT(*) FROM daily_bar_cache WHERE trade_date='2024-04-09'"))
print("K2 created_at DATE histogram for rows with trade_date<'2024-07-01' (top 8 write-days):",
      q(op,"SELECT substr(created_at,1,10) d, COUNT(*) n, MIN(trade_date), MAX(trade_date) FROM daily_bar_cache WHERE trade_date<'2024-07-01' GROUP BY d ORDER BY n DESC LIMIT 8"))
print("K3 overall created_at span of whole cache:",
      q(op,"SELECT MIN(created_at), MAX(created_at) FROM daily_bar_cache"))
print("K4 for the biggest write-day, what trade_date span did it land?",
      q(op,"""SELECT substr(created_at,1,10) d, COUNT(*) n, MIN(trade_date), MAX(trade_date),
              COUNT(DISTINCT trade_date) sess FROM daily_bar_cache GROUP BY d ORDER BY n DESC LIMIT 6"""))

print()
print("### L. per-symbol coverage — their 146 x 5167 assumes 100% attendance. Test that.")
print("L1 row-count histogram top 8:",
      q(op,"WITH per AS (SELECT symbol,COUNT(*) n FROM daily_bar_cache WHERE length(trade_date)=10 GROUP BY symbol) SELECT n,COUNT(*) FROM per GROUP BY n ORDER BY 2 DESC LIMIT 8"))
print("L2 the 501-row cohort: min/max trade_date (is it the 500-clamp fingerprint?)",
      q(op,"""WITH per AS (SELECT symbol,COUNT(*) n FROM daily_bar_cache WHERE length(trade_date)=10 GROUP BY symbol)
              SELECT COUNT(*) syms, MIN(b.trade_date), MAX(b.trade_date) FROM per JOIN daily_bar_cache b USING(symbol)
              WHERE per.n=501"""))
print("L3 attendance among symbols listed <=2023-09-04 that are IN the cache, over the 587 observed sessions:")
listed = set(r[0] for r in q(mh,"SELECT symbol FROM instruments WHERE list_date IS NOT NULL AND list_date<>'' AND date(list_date)<='2023-09-04'"))
rows = q(op,"SELECT symbol, COUNT(*) FROM daily_bar_cache WHERE length(trade_date)=10 GROUP BY symbol")
cnt = {s:n for s,n in rows}
present = [cnt[s] for s in listed if s in cnt]
missing = [s for s in listed if s not in cnt]
import statistics
print("   listed<=window_start: %d ; present in cache: %d ; absent entirely: %d" % (len(listed), len(present), len(missing)))
print("   attendance over 587 sessions: mean=%.1f median=%.0f  => mean ratio=%.4f" %
      (statistics.mean(present), statistics.median(present), statistics.mean(present)/587))
print("L4 THEIR estimate 146*5167 = %d" % (146*5167))
print("L5 attendance-adjusted, 141 gap sessions: 141*5167*%.4f = %d" %
      (statistics.mean(present)/587, int(141*5167*statistics.mean(present)/587)))

print()
print("### M. ingest_runs — did any run ever ATTEMPT a pre-2024-04-09 range?")
cols = [r[1] for r in q(mh,"PRAGMA table_info(ingest_runs)")]
print("M1 cols:", cols)
print("M2 runs:", q(mh,"SELECT MIN(started_at), MAX(started_at), COUNT(*) FROM ingest_runs") if 'started_at' in cols else "n/a")
for c in cols:
    if 'date' in c.lower() or 'window' in c.lower() or 'start' in c.lower() or 'end' in c.lower():
        try: print("   M3 %s min/max:" % c, q(mh,f'SELECT MIN("{c}"), MAX("{c}") FROM ingest_runs'))
        except Exception as e: print("   err",c,e)
op.close(); mh.close()
