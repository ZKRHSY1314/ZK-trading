# -*- coding: utf-8 -*-
import sqlite3, json
OP = r"D:\codex-A股交易\trading_local.sqlite3"
c = sqlite3.connect(f"file:{OP}?mode=ro", uri=True); cur=c.cursor()
q=lambda s,*a: cur.execute(s,a).fetchall()

print("=== A. Whole-table rows existing at each decision cutoff (created_at<=cutoff, normalized) ===")
for co,nd in q("""SELECT decision_cutoff, COUNT(DISTINCT decision_id) FROM forecast_decisions
                  WHERE scope='stock' GROUP BY decision_cutoff ORDER BY decision_cutoff LIMIT 4"""):
    n = q("SELECT COUNT(*) FROM daily_bar_cache WHERE replace(substr(created_at,1,19),' ','T') <= ?", co[:19])[0][0]
    print(f"  cutoff {co}  rows_in_WHOLE_cache_at_cutoff = {n:,}")

print("\n=== B. THE DECISIVE TEST ===")
print("For each decision, compare bars_count RECORDED IN features_json (what the engine says it read)")
print("against bars present at cutoff under the created_at model.\n")
rows = q("""SELECT decision_id, subject, decision_cutoff, features_json
            FROM forecast_decisions WHERE scope='stock' AND horizon_days=1
            ORDER BY decision_cutoff""")
print(f"  decisions x subject (h=1): {len(rows)}")
impossible = 0; checked = 0; examples = []
by_day = {}
for did, subj, co, fj in rows:
    try: f = json.loads(fj)
    except Exception: continue
    bc = f.get("bars_count")
    if bc is None: continue
    checked += 1
    avail = q("""SELECT COUNT(*) FROM daily_bar_cache WHERE symbol=?
                 AND trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
                 AND trade_date <= ?
                 AND replace(substr(created_at,1,19),' ','T') <= ?""", subj, co[:10], co[:19])[0][0]
    d = co[:10]; by_day.setdefault(d, [0,0])
    by_day[d][1] += 1
    if avail < bc:
        impossible += 1; by_day[d][0] += 1
        if len(examples) < 6:
            examples.append((did[:34], subj, co, bc, avail, f.get("data_quality")))
print(f"  checked={checked}   decisions whose recorded bars_count EXCEEDS bars 'available' at cutoff = {impossible} ({100.0*impossible/checked:.2f}%)")
print("\n  by cutoff day (impossible / checked):")
for d in sorted(by_day): print(f"    {d}  {by_day[d][0]:5d} / {by_day[d][1]:5d}")
print("\n  examples (decision, subject, cutoff, bars_count_recorded, bars_available_by_created_at, data_quality):")
for e in examples: print("   ", e)

print("\n=== C. Was the cache rebuilt? earliest created_at vs earliest trade_date ===")
print("  MIN(created_at) whole table:", q("SELECT MIN(created_at) FROM daily_bar_cache")[0][0])
print("  MIN(trade_date) whole table:", q("SELECT MIN(trade_date) FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'")[0][0])
print("  rows created on 2026-07-15 (single bulk load):",
      q("SELECT COUNT(*) FROM daily_bar_cache WHERE substr(created_at,1,10)='2026-07-15'")[0][0],
      "=", round(100.0*q("SELECT COUNT(*) FROM daily_bar_cache WHERE substr(created_at,1,10)='2026-07-15'")[0][0]/2891617,2), "% of table")
print("  distinct source values and their created_at spans:")
for r in q("""SELECT source, COUNT(*), MIN(created_at), MAX(created_at) FROM daily_bar_cache
              GROUP BY source ORDER BY 2 DESC LIMIT 10"""): print("   ", r)

print("\n=== D. Does a proper point-in-time field exist elsewhere? ===")
MH = r"D:\codex-A股交易\market_history.sqlite3"
c2 = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)
print("  market_history.daily_bars available_at:",
      c2.execute("SELECT COUNT(*), SUM(available_at IS NULL), MIN(available_at), MAX(available_at) FROM daily_bars").fetchall())
c2.close(); c.close()
