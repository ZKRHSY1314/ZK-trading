import sqlite3
MH = r"D:\codex-A股交易\market_history.sqlite3"
TL = r"D:\codex-A股交易\trading_local.sqlite3"
c = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)
c.execute("PRAGMA query_only=ON")
c.execute("ATTACH DATABASE ? AS tl", (f"file:{TL}?mode=ro",))

def q(label, sql, params=()):
    print("-"*78); print(label); print("SQL:", " ".join(sql.split()))
    for r in c.execute(sql, params): print("   ", r)

# 1. Independent formulation: aggregate ONCE over the amount-NULL population and
#    classify every row, so the pieces must sum to 1,955,651. No cherry-picked filter.
q("1. FULL partition of the 1,955,651 amount-NULL rows by cache availability",
  """SELECT CASE
              WHEN c.symbol IS NULL THEN 'A_no_cache_row_at_all'
              WHEN c.amount IS NULL THEN 'B_cache_row_but_amount_also_null'
              WHEN c.quality_status <> 'ready' THEN 'C_cache_amount_but_not_ready'
              WHEN c.adjustment_mode <> 'qfq' THEN 'D_cache_amount_ready_but_not_qfq'
              ELSE 'E_REPAIRABLE_ready_qfq_amount'
            END bucket, COUNT(*) n
     FROM daily_bars d LEFT JOIN tl.daily_bar_cache c
       ON c.symbol=d.symbol AND c.trade_date=d.trade_date
     WHERE d.amount IS NULL
     GROUP BY 1 ORDER BY 2 DESC""")

q("1b. sanity: does the partition sum to the amount-NULL total?",
  """SELECT COUNT(*) total_amount_null FROM daily_bars WHERE amount IS NULL""")

q("1c. fan-out guard: repairable counted as rows vs distinct (symbol,trade_date)",
  """SELECT COUNT(*) rows, COUNT(DISTINCT d.symbol||'|'||d.trade_date) cells,
            COUNT(DISTINCT d.symbol) syms
     FROM daily_bars d JOIN tl.daily_bar_cache c
       ON c.symbol=d.symbol AND c.trade_date=d.trade_date
     WHERE d.amount IS NULL AND c.amount IS NOT NULL
       AND c.quality_status='ready' AND c.adjustment_mode='qfq'""")

# 2. Is the repair VALID? Compare the same-cell OHLC to see whether cache row is the same bar.
q("2. Value agreement on repairable cells: close price relative diff distribution",
  """WITH j AS (
       SELECT d.close dc, c.close cc, d.volume dv, c.volume cv
       FROM daily_bars d JOIN tl.daily_bar_cache c
         ON c.symbol=d.symbol AND c.trade_date=d.trade_date
       WHERE d.amount IS NULL AND c.amount IS NOT NULL
         AND c.quality_status='ready' AND c.adjustment_mode='qfq'
         AND d.close>0 AND c.close>0)
     SELECT CASE
              WHEN abs(cc-dc)/dc < 0.0001 THEN 'a_identical_<0.01%'
              WHEN abs(cc-dc)/dc < 0.01   THEN 'b_<1%'
              WHEN abs(cc-dc)/dc < 0.10   THEN 'c_1-10%'
              WHEN abs(cc-dc)/dc < 0.50   THEN 'd_10-50%'
              ELSE 'e_>50%_DIFFERENT_BAR' END band, COUNT(*) n
     FROM j GROUP BY 1 ORDER BY 1""")

# 3. Unit sanity: is cache.amount really yuan turnover, cross-checked against
#    market_history rows that ALREADY have an amount from the same akshare feed.
q("3. Control: rows where BOTH stores have amount -> ratio cache/mh",
  """WITH j AS (SELECT d.amount da, c.amount ca FROM daily_bars d
       JOIN tl.daily_bar_cache c ON c.symbol=d.symbol AND c.trade_date=d.trade_date
       WHERE d.amount IS NOT NULL AND c.amount IS NOT NULL AND d.amount>0 AND c.amount>0)
     SELECT CASE WHEN abs(ca/da-1)<0.0001 THEN 'a_equal'
                 WHEN abs(ca/da-1)<0.01 THEN 'b_<1%'
                 WHEN ca/da BETWEEN 9000 AND 11000 THEN 'c_x10000_unit_shift'
                 WHEN ca/da BETWEEN 0.00009 AND 0.00011 THEN 'd_div10000'
                 ELSE 'e_other' END band, COUNT(*) n
     FROM j GROUP BY 1 ORDER BY 2 DESC""")

# 4. Provider mismatch: reproduce with explicit totals + a denominator I control.
q("4. provider vs source mismatch, with joined-total denominator",
  """SELECT (SELECT COUNT(*) FROM daily_bars d JOIN tl.daily_bar_cache c
              ON c.symbol=d.symbol AND c.trade_date=d.trade_date) joined_rows,
            (SELECT COUNT(*) FROM daily_bars d JOIN tl.daily_bar_cache c
              ON c.symbol=d.symbol AND c.trade_date=d.trade_date
              WHERE d.provider<>c.source) mismatched,
            (SELECT COUNT(*) FROM daily_bars) mh_total""")

q("4b. top provider/source mismatch pairs",
  """SELECT d.provider, c.source, COUNT(*) n FROM daily_bars d
     JOIN tl.daily_bar_cache c ON c.symbol=d.symbol AND c.trade_date=d.trade_date
     WHERE d.provider<>c.source GROUP BY 1,2 ORDER BY 3 DESC LIMIT 8""")

# 5. Cache rows never promoted
q("5. ready+qfq cache rows with NO matching daily_bars cell (never promoted)",
  """SELECT COUNT(*) n, COUNT(DISTINCT c.symbol) syms, MIN(c.trade_date), MAX(c.trade_date)
     FROM tl.daily_bar_cache c LEFT JOIN daily_bars d
       ON d.symbol=c.symbol AND d.trade_date=c.trade_date
     WHERE d.symbol IS NULL AND c.quality_status='ready' AND c.adjustment_mode='qfq'""")

q("5b. of those unpromoted, how many symbols are not even in instruments (FK would block)",
  """SELECT COUNT(*) n FROM (
       SELECT DISTINCT c.symbol FROM tl.daily_bar_cache c
       LEFT JOIN daily_bars d ON d.symbol=c.symbol AND d.trade_date=c.trade_date
       WHERE d.symbol IS NULL AND c.quality_status='ready' AND c.adjustment_mode='qfq'
         AND c.symbol NOT IN (SELECT symbol FROM instruments))""")
c.close()
