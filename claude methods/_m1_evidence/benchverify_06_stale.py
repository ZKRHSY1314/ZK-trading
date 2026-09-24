import sqlite3
OP=r"D:/codex-A股交易/trading_local.sqlite3"
c=sqlite3.connect(f"file:{OP}?mode=ro", uri=True); c.row_factory=sqlite3.Row
q=lambda s,p=(): c.execute(s,p).fetchall()
print("### R. When did SH000300 bars land in daily_bar_cache vs when runs executed?")
for r in q("""SELECT MIN(created_at) first_ins, MAX(created_at) last_ins, COUNT(*) n
              FROM daily_bar_cache WHERE symbol='SH000300'"""):
    print("  SH000300 created_at:", dict(r))
for r in q("SELECT MIN(created_at), MAX(created_at) FROM historical_backtest_runs"):
    print("  runs created_at range:", tuple(r))
print("  runs created BEFORE first SH000300 insert:",
      q("""SELECT COUNT(*) FROM historical_backtest_runs
           WHERE created_at < (SELECT MIN(created_at) FROM daily_bar_cache WHERE symbol='SH000300')""")[0][0])
print()
print("### S. per-run: bars of SH000300 already inserted at that run's created_at (point-in-time)")
for r in q("""SELECT r.id, r.created_at,
              (SELECT COUNT(*) FROM daily_bar_cache d
                WHERE d.symbol='SH000300' AND d.quality_status='ready'
                  AND d.trade_date>=r.start_date AND d.trade_date<=r.end_date
                  AND d.created_at <= r.created_at) avail
              FROM historical_backtest_runs r ORDER BY r.id"""):
    if r["id"] in (1,7,8,12,13,18,19,30,37,38,39):
        print(f"  run {r['id']:>2} created {r['created_at']}  SH000300 bars available then = {r['avail']}")
