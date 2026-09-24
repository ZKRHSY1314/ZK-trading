import sqlite3
MH = r"D:\codex-A股交易\market_history.sqlite3"
TL = r"D:\codex-A股交易\trading_local.sqlite3"
c = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)
c.execute("PRAGMA query_only=ON")
c.execute("ATTACH DATABASE ? AS tl", (f"file:{TL}?mode=ro",))
def q(label, sql, params=()):
    print("-"*78); print(label); print("SQL:", " ".join(sql.split()))
    for r in c.execute(sql, params): print("   ", r)

# A. Does amount agree EVEN WHERE prices disagree? -> proves amount is adjustment-invariant,
#    so copying cache.amount onto a differently-rebased qfq row is legitimate.
q("A. both-amount rows: cross-tab of price agreement vs amount agreement",
  """WITH j AS (SELECT d.close dc, c.close cc, d.amount da, c.amount ca
       FROM daily_bars d JOIN tl.daily_bar_cache c
         ON c.symbol=d.symbol AND c.trade_date=d.trade_date
       WHERE d.amount IS NOT NULL AND c.amount IS NOT NULL AND d.close>0 AND d.amount>0)
     SELECT CASE WHEN abs(cc-dc)/dc < 0.0001 THEN 'price_same' ELSE 'price_DIFFERS' END pb,
            CASE WHEN abs(ca-da)/da < 0.0001 THEN 'amount_same' ELSE 'amount_DIFFERS' END ab,
            COUNT(*) n FROM j GROUP BY 1,2 ORDER BY 3 DESC""")

# B. fetched_at of the amount-NULL rows: stale snapshot, or mislabeled?
q("B. amount-NULL rows: provider x fetched_at date",
  """SELECT provider, substr(fetched_at,1,10) fetched_day, COUNT(*) n
     FROM daily_bars WHERE amount IS NULL GROUP BY 1,2 ORDER BY 3 DESC LIMIT 10""")

q("B2. rows WITH amount: provider x fetched_at date",
  """SELECT provider, substr(fetched_at,1,10) fetched_day, COUNT(*) n
     FROM daily_bars WHERE amount IS NOT NULL GROUP BY 1,2 ORDER BY 3 DESC LIMIT 10""")

# C. ingest_runs mechanism claim
q("C. ingest_runs: last 20, with row counts actually attributable via ingest_run_id",
  """SELECT r.id, r.started_at, r.status,
            (SELECT COUNT(*) FROM daily_bars b WHERE b.ingest_run_id=r.id) bars_written
     FROM ingest_runs r ORDER BY r.id DESC LIMIT 20""")

q("C2. ingest_runs columns",
  """SELECT sql FROM sqlite_master WHERE name='ingest_runs'""")

# D. per-symbol bar depth: is the refreshed tail really ~150 bars/symbol?
q("D. per-symbol count of amount-NOT-NULL bars (the refreshed tail), distribution",
  """WITH t AS (SELECT symbol, SUM(CASE WHEN amount IS NOT NULL THEN 1 ELSE 0 END) n
              FROM daily_bars GROUP BY symbol)
     SELECT n bars_with_amount, COUNT(*) symbols FROM t
     GROUP BY 1 ORDER BY 2 DESC LIMIT 10""")

q("D2. max trade_date among amount-NULL vs amount-NOT-NULL (is the split a date cutoff?)",
  """SELECT CASE WHEN amount IS NULL THEN 'null' ELSE 'notnull' END k,
            MIN(trade_date), MAX(trade_date), COUNT(*) FROM daily_bars GROUP BY 1""")
c.close()
