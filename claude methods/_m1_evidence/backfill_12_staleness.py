import sqlite3, os
ROOT=r"D:\codex-A股交易"
mh=sqlite3.connect(f"file:{os.path.join(ROOT,'market_history.sqlite3')}?mode=ro",uri=True); mh.row_factory=sqlite3.Row
mh.execute("ATTACH DATABASE ? AS tl", (f"file:{os.path.join(ROOT,'trading_local.sqlite3')}?mode=ro",))
def q(sql,n=20):
    print("SQL:"," ".join(sql.split()))
    out=[dict(r) for r in mh.execute(sql).fetchall()]
    for r in out[:n]: print("   ",r)
    print(); return out
print("### market_history amount NULL by provider")
q("""SELECT provider, COUNT(*) rows, SUM(amount IS NULL) amount_null,
            MIN(trade_date) mn, MAX(trade_date) mx, MAX(fetched_at) last_fetch
     FROM daily_bars GROUP BY provider ORDER BY amount_null DESC""")
print("### rows where trading_local HAS amount but market_history does NOT (repairable with zero network cost)")
q("""SELECT COUNT(*) AS repairable_rows
     FROM daily_bars d JOIN tl.daily_bar_cache c
       ON c.symbol=d.symbol AND c.trade_date=d.trade_date
     WHERE d.amount IS NULL AND c.amount IS NOT NULL
       AND c.quality_status='ready' AND c.adjustment_mode='qfq'""")
print("### rows where the two stores disagree on provenance")
q("""SELECT d.provider AS hist_provider, c.source AS cache_source, COUNT(*) rows
     FROM daily_bars d JOIN tl.daily_bar_cache c
       ON c.symbol=d.symbol AND c.trade_date=d.trade_date
     WHERE d.provider <> c.source GROUP BY 1,2 ORDER BY rows DESC LIMIT 10""")
print("### rows present in trading_local but absent from market_history (promotion backlog)")
q("""SELECT COUNT(*) AS cache_rows_not_promoted
     FROM tl.daily_bar_cache c LEFT JOIN daily_bars d
       ON c.symbol=d.symbol AND c.trade_date=d.trade_date AND d.adjustment_mode='qfq'
     WHERE d.symbol IS NULL AND length(c.trade_date)=10
       AND c.quality_status='ready' AND c.adjustment_mode='qfq'""")
print("### last fetched_at distribution in market_history")
q("""SELECT substr(fetched_at,1,10) day, COUNT(*) rows FROM daily_bars
     GROUP BY day ORDER BY day DESC LIMIT 10""")
