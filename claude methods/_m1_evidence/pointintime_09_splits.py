import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
c = sqlite3.connect(f"file:{TL}?mode=ro", uri=True)
SQL=("SELECT trade_date FROM daily_bar_cache WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' "
     "AND trade_date BETWEEN '2023-09-04' AND '2026-09-04' AND quality_status='ready' "
     "GROUP BY trade_date HAVING COUNT(*)>=3000 ORDER BY trade_date")
print("### H1 SQL:", SQL)
days=[r[0] for r in c.execute(SQL)]
print("dense trading days:", len(days), days[0], "..", days[-1])
for k in (60,120,250):
    print(f"  day #{k} (1-indexed) = {days[k-1]}  -> a {k}-day lookback feature is first computable on {days[k-1]}")
print("  index of 2025-01-02 ->", next((i for i,d in enumerate(days) if d>='2025-01-02'), None))
print()
print("### H2 proposed fold boundaries (indices into the dense-day list)")
# warm-up 250 days, then 4 expanding-window folds with 20d purge + 20d embargo
warm = 250
rest = len(days)-warm
print(f"warm-up reserved: {warm} days -> {days[0]} .. {days[warm-1]}")
print(f"days available for train/val/test after warm-up: {rest} -> {days[warm]} .. {days[-1]}")
n_folds=4
test_len = 60
for f in range(n_folds):
    test_end_i = len(days)-1 - f*test_len
    test_start_i = test_end_i - test_len + 1
    if test_start_i <= warm: break
    val_end_i = test_start_i - 1 - 20 - 20      # purge 20 + embargo 20
    val_start_i = val_end_i - 40 + 1
    tr_end_i = val_start_i - 1 - 20 - 20
    tr_start_i = warm
    if tr_end_i - tr_start_i < 60: 
        print(f"fold {n_folds-f}: INSUFFICIENT TRAIN ({tr_end_i-tr_start_i} days) - not viable")
        continue
    print(f"fold {n_folds-f}: train {days[tr_start_i]}..{days[tr_end_i]} ({tr_end_i-tr_start_i+1}d) | "
          f"purge+embargo 40d | val {days[val_start_i]}..{days[val_end_i]} (40d) | purge+embargo 40d | "
          f"test {days[test_start_i]}..{days[test_end_i]} ({test_len}d)")
c.close()

print("\n### H3 market_history restatement check")
m = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)
for lbl,sql in [
 ("rows where updated_at != created_at","SELECT COUNT(*) FROM daily_bars WHERE updated_at <> created_at"),
 ("rows where updated_at != fetched_at","SELECT COUNT(*) FROM daily_bars WHERE updated_at <> fetched_at"),
 ("distinct row_hash count","SELECT COUNT(DISTINCT row_hash) FROM daily_bars"),
 ("distinct (symbol,trade_date) count","SELECT COUNT(*) FROM (SELECT DISTINCT symbol,trade_date FROM daily_bars)"),
 ("rule_regime split","SELECT rule_regime, COUNT(*) FROM daily_bars GROUP BY rule_regime"),
 ("instruments with delist_date","SELECT COUNT(*) FROM instruments WHERE delist_date IS NOT NULL"),
 ("instruments by status","SELECT status, COUNT(*) FROM instruments GROUP BY status"),
 ("instruments list_date after 2023-09-04","SELECT COUNT(*) FROM instruments WHERE list_date > '2023-09-04'"),
 ("instruments list_date null","SELECT COUNT(*) FROM instruments WHERE list_date IS NULL"),
 ("training_dataset_manifests","SELECT COUNT(*) FROM training_dataset_manifests"),
 ("bar_quality_issues","SELECT COUNT(*) FROM bar_quality_issues"),
]:
    print(f"  {lbl}: {m.execute(sql).fetchall()}   |SQL| {sql}")
m.close()
