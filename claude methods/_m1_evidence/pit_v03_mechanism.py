import sqlite3
TL = r"D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True); c.execute("PRAGMA query_only=ON")
q=lambda s,p=():list(c.execute(s,p))

print("### 7. The 2026-07-15 bulk re-ingest event")
print("G0 created_at minute-clusters for the 90 subjects (top 12):")
for r in q("""SELECT substr(created_at,1,16) m, COUNT(*) rows_, COUNT(DISTINCT symbol) syms
  FROM daily_bar_cache WHERE symbol IN (SELECT DISTINCT subject FROM forecast_decisions WHERE scope='stock')
  GROUP BY 1 ORDER BY rows_ DESC LIMIT 12"""): print("   ",r)
print("G1 created_at == updated_at ratio for those 90 subjects:",
  q("""SELECT SUM(created_at=updated_at), SUM(created_at<>updated_at), COUNT(*) FROM daily_bar_cache
       WHERE symbol IN (SELECT DISTINCT subject FROM forecast_decisions WHERE scope='stock')"""))
print("G2 whole-table created_at date histogram (top 10):")
for r in q("SELECT substr(created_at,1,10) d, COUNT(*) FROM daily_bar_cache GROUP BY 1 ORDER BY 2 DESC LIMIT 10"): print("   ",r)

print("\n### 8. CONTRADICTION COUNT: engine's own record vs created_at, restricted to the 2,915 flagged pairs")
rows=q("""WITH d AS (SELECT DISTINCT decision_id,subject,decision_cutoff,
             substr(decision_cutoff,1,10) cd, replace(substr(decision_cutoff,1,19),'T',' ') ct,
             json_extract(features_json,'$.bars_count') bc,
             json_extract(features_json,'$.market_data.latest_trade_date') ltd
           FROM forecast_decisions WHERE scope='stock')
  SELECT d.decision_id,d.subject,d.cd,d.ct,d.bc,d.ltd,
    (SELECT COUNT(*) FROM daily_bar_cache b WHERE b.symbol=d.subject AND b.trade_date<=d.cd
       AND b.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND b.created_at<=d.ct) avail,
    (SELECT COUNT(*) FROM daily_bar_cache b WHERE b.symbol=d.subject AND b.trade_date<=d.cd
       AND b.trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND b.created_at>d.ct) late
  FROM d""")
flagged=[r for r in rows if r[7]>0]
print("H0 flagged pairs (late>0):", len(flagged), "of", len(rows))
contra=[r for r in flagged if (r[4] or 0) > r[6]]
print("H1 flagged pairs CONTRADICTED by engine's own bars_count (bars_count > avail):", len(contra))
print("H2 flagged pairs where avail==0 yet engine read bars_count>0:", len([r for r in flagged if r[6]==0 and (r[4] or 0)>0]))
print("H3 flagged pairs NOT contradicted (avail >= bars_count):", len([r for r in flagged if (r[4] or 0)<=r[6]]))
print("H4 flagged pairs by cutoff date:")
from collections import Counter
for k,v in sorted(Counter(r[2] for r in flagged).items()): print("   ",k,v)
print("H5 CONTRADICTED pairs by cutoff date:")
for k,v in sorted(Counter(r[2] for r in contra).items()): print("   ",k,v)
print("H6 also: engine's recorded latest_trade_date newer than newest bar available per created_at?")
n=0
for did,sub,cd,ct,bc,ltd,avail,late in flagged:
    if not ltd: continue
    mx=q("""SELECT MAX(trade_date) FROM daily_bar_cache WHERE symbol=? AND created_at<=?
            AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'""",(sub,ct))[0][0]
    if mx is None or ltd>mx: n+=1
print("   pairs where engine reported a latest_trade_date newer than anything created_at says existed:", n)
c.close()
