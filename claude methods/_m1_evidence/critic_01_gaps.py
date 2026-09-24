import sqlite3, os, json
TL=r"D:/codex-A股交易/trading_local.sqlite3"
MH=r"D:/codex-A股交易/market_history.sqlite3"
def ro(p):
    c=sqlite3.connect("file:%s?mode=ro"%p, uri=True); c.row_factory=sqlite3.Row; return c
def p(t,rows):
    print("### "+t)
    for r in rows: print("   ", tuple(r))
    print()

tl=ro(TL); mh=ro(MH)
print("journal_mode tl:", tl.execute("PRAGMA journal_mode;").fetchone()[0],
      "| mh:", mh.execute("PRAGMA journal_mode;").fetchone()[0]); print()

# 1 field availability / NULL census
p("C1 daily_bar_cache NULL census (all rows)", tl.execute("""
SELECT COUNT(*) rows,
 SUM(open IS NULL) n_open, SUM(high IS NULL) n_high, SUM(low IS NULL) n_low,
 SUM(close IS NULL) n_close, SUM(volume IS NULL) n_vol, SUM(amount IS NULL) n_amt,
 SUM(source IS NULL OR source='') n_src, SUM(created_at IS NULL) n_cre, SUM(updated_at IS NULL) n_upd
FROM daily_bar_cache"""))
p("C1b daily_bar_cache NULL census (quality_status='ready' only)", tl.execute("""
SELECT COUNT(*) rows, SUM(open IS NULL) n_open, SUM(high IS NULL) n_high, SUM(low IS NULL) n_low,
 SUM(close IS NULL) n_close, SUM(volume IS NULL) n_vol, SUM(amount IS NULL) n_amt
FROM daily_bar_cache WHERE quality_status='ready'"""))
p("C2 daily_bars NULL census", mh.execute("""
SELECT COUNT(*) rows, SUM(open IS NULL) n_open, SUM(volume IS NULL) n_vol, SUM(amount IS NULL) n_amt,
 SUM(provider IS NULL OR provider='') n_prov, SUM(available_at IS NULL) n_av, SUM(fetched_at IS NULL) n_fe,
 SUM(row_hash IS NULL OR row_hash='') n_hash, SUM(ingest_run_id IS NULL) n_run,
 SUM(quality_status IS NULL OR quality_status='') n_q
FROM daily_bars"""))

# 2 UNIT TEST: amount/(volume*close) by source  -> 100 => volume in hand & amount in CNY
p("C3 UNIT PROBE daily_bar_cache: median-ish ratio amount/(volume*close) by source", tl.execute("""
WITH x AS (SELECT source, amount/(volume*close) r FROM daily_bar_cache
           WHERE amount IS NOT NULL AND volume>0 AND close>0 AND quality_status='ready' AND length(trade_date)=10)
SELECT source, COUNT(*) n, ROUND(MIN(r),4) mn, ROUND(AVG(r),4) avg, ROUND(MAX(r),4) mx,
       SUM(r BETWEEN 95 AND 105) near100, SUM(r BETWEEN 0.95 AND 1.05) near1
FROM x GROUP BY source ORDER BY n DESC"""))
p("C3b UNIT PROBE daily_bars by provider", mh.execute("""
WITH x AS (SELECT provider, amount/(volume*close) r FROM daily_bars
           WHERE amount IS NOT NULL AND volume>0 AND close>0)
SELECT provider, COUNT(*) n, ROUND(MIN(r),4) mn, ROUND(AVG(r),4) avg, ROUND(MAX(r),4) mx,
       SUM(r BETWEEN 95 AND 105) near100, SUM(r BETWEEN 0.95 AND 1.05) near1
FROM x GROUP BY provider ORDER BY n DESC"""))
p("C3c volume_unit declared vs source, daily_bar_cache", tl.execute("""
SELECT source, volume_unit, COUNT(*) FROM daily_bar_cache GROUP BY 1,2 ORDER BY 3 DESC LIMIT 20"""))

# 3 calendar sanity: weekday distribution + weekend sessions + longest gap in dense period
p("C4 weekday of distinct sessions (0=Sun..6=Sat) in cache window", tl.execute("""
SELECT strftime('%w', trade_date) dow, COUNT(DISTINCT trade_date) FROM daily_bar_cache
WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04' AND length(trade_date)=10 GROUP BY 1 ORDER BY 1"""))
rows=[r[0] for r in tl.execute("""SELECT DISTINCT trade_date FROM daily_bar_cache
 WHERE trade_date BETWEEN '2024-06-24' AND '2026-09-03' AND length(trade_date)=10 ORDER BY 1""")]
import datetime as dt
gaps=[]
for a,b in zip(rows, rows[1:]):
    d=(dt.date.fromisoformat(b)-dt.date.fromisoformat(a)).days
    if d>4: gaps.append((a,b,d))
print("### C5 dense-period sessions:",len(rows),"  calendar gaps >4d:",len(gaps))
for g in sorted(gaps,key=lambda x:-x[2])[:12]: print("   ",g)
print()

# 4 symbols in cache absent from instruments
mh_syms=set(r[0] for r in mh.execute("SELECT symbol FROM instruments"))
c_syms=set(r[0] for r in tl.execute("SELECT DISTINCT symbol FROM daily_bar_cache"))
print("### C6 cache symbols NOT in instruments:", len(c_syms-mh_syms), sorted(c_syms-mh_syms)[:20])
print("### C6b instruments symbols with ZERO cache bars:", len(mh_syms-c_syms), sorted(mh_syms-c_syms)[:20]); print()

# 5 benchmark coverage vs dense sessions
bench=set(r[0] for r in tl.execute("SELECT trade_date FROM daily_bar_cache WHERE symbol='SH000300' AND length(trade_date)=10"))
dense=set(rows)
print("### C7 SH000300 rows:",len(bench)," dense sessions:",len(dense),
      " dense sessions WITHOUT benchmark:",len(dense-bench),
      " missing tail:",sorted(dense-bench)[-6:] if dense-bench else None)
print("    benchmark dates outside dense set:",len(bench-dense), sorted(bench-dense)[:6]); print()

# 6 tables census both dbs (calendar/suspension/corp action?)
p("C8 trading_local tables matching calendar|halt|suspend|dividend|split|corp|adj", tl.execute("""
SELECT name FROM sqlite_master WHERE type='table' AND (
 name LIKE '%calendar%' OR name LIKE '%halt%' OR name LIKE '%suspend%' OR name LIKE '%dividend%'
 OR name LIKE '%split%' OR name LIKE '%corp%' OR name LIKE '%adj%' OR name LIKE '%session%')"""))
print("### C8b trading_local total tables:", tl.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]); print()

# 7 backfill denominator: 5167 by exchange (BJ history is unobtainable per report)
p("C9 instruments list_date<='2023-09-04' by exchange", mh.execute("""
SELECT exchange, COUNT(*) FROM instruments WHERE list_date<='2023-09-04' AND list_date IS NOT NULL AND list_date<>''
GROUP BY 1 ORDER BY 2 DESC"""))

# 8 fold population: distinct symbols/rows per Plan-B test window
for nm,a,b in [("B_f1_test","2025-07-28","2025-11-10"),("B_f2_test","2025-12-09","2026-03-26"),("B_f3_test","2026-04-27","2026-08-06")]:
    r=tl.execute("""SELECT COUNT(*), COUNT(DISTINCT symbol), COUNT(DISTINCT trade_date) FROM daily_bar_cache
      WHERE trade_date BETWEEN ? AND ? AND quality_status='ready' AND adjustment_mode='qfq'""",(a,b)).fetchone()
    print("### C10 %s %s..%s rows=%d syms=%d sessions=%d"%(nm,a,b,r[0],r[1],r[2]))
print()

# 9 stale rows: where do the 187,025 stale updated_at rows live (which symbols/dates)?
p("C11 stale updated_at<2026-08 rows: exchange/date spread", tl.execute("""
SELECT substr(updated_at,1,7) m, COUNT(*) rows, COUNT(DISTINCT symbol) syms, MIN(trade_date), MAX(trade_date)
FROM daily_bar_cache GROUP BY 1 ORDER BY 1"""))

# 10 mh provider distribution vs report claim
p("C12 daily_bars provider x rows x symbols", mh.execute("""
SELECT provider, COUNT(*), COUNT(DISTINCT symbol), MIN(trade_date), MAX(trade_date) FROM daily_bars GROUP BY 1 ORDER BY 2 DESC"""))
