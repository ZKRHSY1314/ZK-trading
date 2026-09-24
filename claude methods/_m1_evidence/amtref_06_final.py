import sqlite3
H=r"D:/codex-A股交易/market_history.sqlite3"; C=r"D:/codex-A股交易/trading_local.sqlite3"
con=sqlite3.connect(f"file:{H}?mode=ro",uri=True)
con.execute("ATTACH DATABASE ? AS cache", (f"file:{C}?mode=ro",))
def q(l,s):
    print("\n### "+l); print("SQL:",' '.join(s.split()))
    for r in con.execute(s).fetchall()[:20]: print("   ",r)
q("F1 the 5 amount<=0 hist rows","SELECT symbol,trade_date,amount,provider FROM daily_bars WHERE amount IS NOT NULL AND amount<=0")
q("F2 index contamination check: any non-stock asset_type in daily_bars?",
  "SELECT i.asset_type,i.exchange,COUNT(*) FROM daily_bars b JOIN instruments i USING(symbol) GROUP BY 1,2")
q("F3 orphan hist rows with no instrument row",
  "SELECT COUNT(*) FROM daily_bars b LEFT JOIN instruments i USING(symbol) WHERE i.symbol IS NULL")
q("F4 regression concentrated 2024-08..2026-01",
  """SELECT SUM(CASE WHEN b.trade_date<'2026-02-01' THEN 1 ELSE 0 END) legacy_era,
            SUM(CASE WHEN b.trade_date>='2026-02-01' THEN 1 ELSE 0 END) recent_era
     FROM daily_bars b JOIN cache.daily_bar_cache c ON c.symbol=b.symbol AND c.trade_date=b.trade_date
     WHERE (b.amount IS NULL OR b.amount<=0) AND c.amount>0""")
con.close()
