import sqlite3
TL = r"D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True); c.execute("PRAGMA query_only=ON")
q=lambda s,p=():list(c.execute(s,p))
print("### 9. Were decision ROWS written after their own cutoff? (backdating check)")
for r in q("""SELECT substr(decision_cutoff,1,10) cut_date, substr(created_at,1,10) row_written,
   COUNT(DISTINCT decision_id) dids, COUNT(*) n
   FROM forecast_decisions WHERE scope='stock' GROUP BY 1,2 ORDER BY 1,2"""): print("   ",r)
print("\nI1 rows where forecast_decisions.created_at < decision_cutoff (written BEFORE cutoff):",
  q("""SELECT COUNT(*) FROM forecast_decisions WHERE scope='stock'
       AND created_at < replace(substr(decision_cutoff,1,19),'T',' ')"""))
print("I2 data_quality for the avail==0 pairs (cutoffs 07-12/07-13):",
  q("""SELECT substr(decision_cutoff,1,10), json_extract(features_json,'$.data_quality'), COUNT(*)
       FROM forecast_decisions WHERE scope='stock' AND substr(decision_cutoff,1,10) IN ('2026-07-12','2026-07-13')
       GROUP BY 1,2"""))
print("\n### 10. Final independent restatement numbers")
print("J0 distinct bars implicated / total bars for the 90 subjects:",
  q("""WITH d AS (SELECT DISTINCT subject,substr(decision_cutoff,1,10) cd,
        replace(substr(decision_cutoff,1,19),'T',' ') ct FROM forecast_decisions WHERE scope='stock')
     SELECT (SELECT COUNT(*) FROM (SELECT DISTINCT b.symbol,b.trade_date FROM d JOIN daily_bar_cache b
        ON b.symbol=d.subject AND b.trade_date<=d.cd AND b.created_at>d.ct
        AND b.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')),
       (SELECT COUNT(*) FROM daily_bar_cache WHERE symbol IN (SELECT DISTINCT subject FROM forecast_decisions WHERE scope='stock'))"""))
print("J1 share of WHOLE cache stamped 2026-07-15:",
  q("SELECT SUM(substr(created_at,1,10)='2026-07-15'), COUNT(*) FROM daily_bar_cache"))
print("J2 daily_bar_cache has an available_at / point-in-time column?:",
  [r[1] for r in q("PRAGMA table_info(daily_bar_cache)")])
c.close()
