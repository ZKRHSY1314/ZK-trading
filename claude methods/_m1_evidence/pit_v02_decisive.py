import sqlite3, json, statistics
TL = r"D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True); c.execute("PRAGMA query_only=ON")
q=lambda s,p=():list(c.execute(s,p))

print("### 4. MECHANISM: when was each subject's history first ingested vs decision cutoffs")
print("E0 daily_bar_cache created_at global range:", q("SELECT MIN(created_at),MAX(created_at) FROM daily_bar_cache"))
print("E1 per-subject first-ingest histogram (date of MIN(created_at)), 90 subjects:")
for r in q("""SELECT substr(created_at,1,10) d, COUNT(*) n FROM
   (SELECT symbol, MIN(created_at) created_at FROM daily_bar_cache
    WHERE symbol IN (SELECT DISTINCT subject FROM forecast_decisions WHERE scope='stock')
      AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' GROUP BY symbol)
   GROUP BY 1 ORDER BY 1"""): print("   ",r)
print("E2 decision cutoff date histogram (130 decision_ids):")
for r in q("""SELECT substr(decision_cutoff,1,10) d, COUNT(DISTINCT decision_id) n
   FROM forecast_decisions WHERE scope='stock' GROUP BY 1 ORDER BY 1"""): print("   ",r)

print("\n### 5. DECISIVE CROSS-CHECK: recorded bars_count vs bars actually present per created_at")
rows = q("""SELECT DISTINCT decision_id, subject, decision_cutoff,
            json_extract(features_json,'$.bars_count'),
            json_extract(features_json,'$.data_quality'),
            json_extract(features_json,'$.market_data.latest_trade_date')
            FROM forecast_decisions WHERE scope='stock'""")
print("F0 rows pulled:", len(rows), " with non-null bars_count:", sum(1 for r in rows if r[3] is not None))
print("F1 data_quality values:", q("""SELECT json_extract(features_json,'$.data_quality') dq, COUNT(*)
     FROM forecast_decisions WHERE scope='stock' GROUP BY 1"""))

# per (subject,cutoff) compute available-at-cutoff count vs recorded bars_count
det=[]
for did,sub,cut,bc,dq,ltd in rows:
    if bc is None: continue
    cutd=cut[:10]; cutts=cut[:19].replace('T',' ')
    avail = q("""SELECT COUNT(*) FROM daily_bar_cache WHERE symbol=? AND trade_date<=?
                 AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND created_at<=?""",(sub,cutd,cutts))[0][0]
    total = q("""SELECT COUNT(*) FROM daily_bar_cache WHERE symbol=? AND trade_date<=?
                 AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'""",(sub,cutd))[0][0]
    det.append((did,sub,cut,bc,avail,total,ltd))

print("F2 pairs with bars_count recorded:", len(det))
zero_avail = [d for d in det if d[4]==0]
short = [d for d in det if 0 < d[4] < d[3]]
ok    = [d for d in det if d[4] >= d[3]]
print("F3 available_at_cutoff == 0 but engine reported bars_count>0 :", len(zero_avail))
print("F4 available_at_cutoff < recorded bars_count (nonzero)       :", len(short))
print("F5 available_at_cutoff >= recorded bars_count (consistent)   :", len(ok))
print("F6 sample of the impossible ones (bars_count vs avail vs total-now):")
for d in zero_avail[:8]: print("    ",d)
print("F7 sample of consistent ones:")
for d in ok[:5]: print("    ",d)

print("\n### 6. Are the FLAGGED bars recent (decision-relevant) or ancient backfill?")
for r in q("""WITH d AS (SELECT DISTINCT decision_id,subject,substr(decision_cutoff,1,10) cd,
                 replace(substr(decision_cutoff,1,19),'T',' ') ct FROM forecast_decisions WHERE scope='stock')
  SELECT CASE WHEN julianday(d.cd)-julianday(b.trade_date) <= 30 THEN 'a_within_30d'
              WHEN julianday(d.cd)-julianday(b.trade_date) <= 400 THEN 'b_31_400d'
              ELSE 'c_over_400d' END bucket,
         COUNT(*) pairbar, COUNT(DISTINCT b.symbol||b.trade_date) distinct_bars
  FROM d JOIN daily_bar_cache b ON b.symbol=d.subject AND b.trade_date<=d.cd
     AND b.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND b.created_at>d.ct
  GROUP BY 1 ORDER BY 1"""): print("   ",r)
c.close()
