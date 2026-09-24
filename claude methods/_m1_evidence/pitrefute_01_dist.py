import sqlite3
OP = r"D:\codex-A股交易\trading_local.sqlite3"
c = sqlite3.connect(f"file:{OP}?mode=ro", uri=True); cur=c.cursor()
q=lambda s,*a: cur.execute(s,a).fetchall()

print("### A. created_at / updated_at global distribution in daily_bar_cache")
print(q("SELECT MIN(created_at),MAX(created_at),MIN(updated_at),MAX(updated_at),COUNT(*) FROM daily_bar_cache"))
print("\n created_at by DAY (top 20 by count):")
for r in q("SELECT substr(created_at,1,10) d, COUNT(*) n FROM daily_bar_cache GROUP BY d ORDER BY n DESC LIMIT 20"): print("  ",r)
print("\n n distinct created_at days:", q("SELECT COUNT(DISTINCT substr(created_at,1,10)) FROM daily_bar_cache"))
print("\n created_at NULL count:", q("SELECT COUNT(*) FROM daily_bar_cache WHERE created_at IS NULL"))

print("\n### B. decision cutoffs")
print(" distinct cutoffs:", q("SELECT COUNT(DISTINCT decision_cutoff) FROM forecast_decisions WHERE scope='stock'"))
print(" min/max cutoff:", q("SELECT MIN(decision_cutoff),MAX(decision_cutoff) FROM forecast_decisions WHERE scope='stock'"))
print(" distinct decision_id:", q("SELECT COUNT(DISTINCT decision_id) FROM forecast_decisions WHERE scope='stock'"))
print(" distinct subject:", q("SELECT COUNT(DISTINCT subject) FROM forecast_decisions WHERE scope='stock'"))
print(" distinct (decision_id,subject) pairs:", q("SELECT COUNT(*) FROM (SELECT DISTINCT decision_id,subject FROM forecast_decisions WHERE scope='stock')"))
print(" distinct (decision_id,subject,cutoff) triples:", q("SELECT COUNT(*) FROM (SELECT DISTINCT decision_id,subject,decision_cutoff FROM forecast_decisions WHERE scope='stock')"))
print("\n cutoff day histogram:")
for r in q("SELECT substr(decision_cutoff,1,10) d, COUNT(DISTINCT decision_id) nd, COUNT(*) n FROM forecast_decisions WHERE scope='stock' GROUP BY d ORDER BY d"): print("  ",r)

print("\n### C. the 90 subjects: are any indices / non-stocks?")
subs=[r[0] for r in q("SELECT DISTINCT subject FROM forecast_decisions WHERE scope='stock'")]
print(" subjects:", subs)
print("\n bar rows in cache for those subjects:")
ph=",".join("?"*len(subs))
print(q(f"SELECT COUNT(*) FROM daily_bar_cache WHERE symbol IN ({ph})",*subs))
print(" distinct symbols present:", q(f"SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE symbol IN ({ph})",*subs))
print("\n### D. writer semantics probe: rows where created_at > updated_at? (normalize T/space)")
print(q("SELECT COUNT(*) FROM daily_bar_cache WHERE replace(created_at,' ','T') > replace(updated_at,' ','T')"))
print(" rows where created_at day != updated_at day:", q("SELECT COUNT(*) FROM daily_bar_cache WHERE substr(created_at,1,10)<>substr(updated_at,1,10)"))
c.close()
