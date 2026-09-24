# -*- coding: utf-8 -*-
import sqlite3
MH = r"D:/codex-A股交易/market_history.sqlite3"
TL = r"D:/codex-A股交易/trading_local.sqlite3"
c = sqlite3.connect(f"file:{MH}?mode=ro", uri=True)
c.execute("ATTACH DATABASE ? AS tl", (f"file:{TL}?mode=ro",))
def q(label, sql, params=()):
    print("\n### " + label); print("SQL: " + " ".join(sql.split()))
    cur = c.execute(sql, params); rows = cur.fetchall()
    print(" | ".join(d[0] for d in cur.description))
    for r in rows[:40]: print(" | ".join("NULL" if v is None else str(v) for v in r))
    return rows

# C1: is daily_bars.available_at literally daily_bar_cache.updated_at (upstream cache write clock)?
q("C1 available_at vs upstream daily_bar_cache.updated_at (joined on symbol,trade_date)",
  """SELECT COUNT(*) matched_pairs,
            SUM(CASE WHEN b.available_at = c.updated_at THEN 1 ELSE 0 END) equal_to_cache_updated_at,
            SUM(CASE WHEN b.available_at = c.created_at THEN 1 ELSE 0 END) equal_to_cache_created_at,
            SUM(CASE WHEN b.available_at <> c.updated_at AND b.available_at <> c.created_at
                     THEN 1 ELSE 0 END) equal_to_neither
     FROM daily_bars b JOIN tl.daily_bar_cache c
       ON c.symbol = b.symbol AND c.trade_date = b.trade_date""")

# C2: does the cache's own clock carry any knowability signal? (control: same lag test upstream)
q("C2 upstream daily_bar_cache.updated_at lag vs trade_date (control group)",
  """SELECT COUNT(*) n, COUNT(DISTINCT substr(updated_at,1,10)) distinct_update_days,
            MIN(updated_at) min_upd, MAX(updated_at) max_upd,
            SUM(CASE WHEN julianday(substr(updated_at,1,10))-julianday(trade_date) <= 1
                     THEN 1 ELSE 0 END) lag_le1
     FROM tl.daily_bar_cache""")

# C3: does market_history hold ANY row whose available_at precedes the first bulk session?
q("C3 rows with available_at earlier than the first session timestamp",
  """SELECT COUNT(*) n FROM daily_bars WHERE available_at < '2026-07-15T14:15:18'""")

# C4: research-window coverage that a HONEST PIT filter would yield at a mid-window cutoff
q("C4 at cutoff 2025-06-30 - trade_date filter vs available_at filter (stocks, qfq)",
  """SELECT
       (SELECT COUNT(*) FROM daily_bars WHERE trade_date <= '2025-06-30') rows_by_trade_date,
       (SELECT COUNT(DISTINCT symbol) FROM daily_bars WHERE trade_date <= '2025-06-30') syms_by_trade_date,
       (SELECT COUNT(*) FROM daily_bars WHERE available_at <= '2025-06-30T23:59:59') rows_by_available_at,
       (SELECT COUNT(DISTINCT symbol) FROM daily_bars WHERE available_at <= '2025-06-30T23:59:59') syms_by_available_at""")

# C5: distinct available_at count per session day - is it 4 timestamps or 4 days of many timestamps?
q("C5 distinct available_at timestamps per session day",
  """SELECT substr(available_at,1,10) day, COUNT(DISTINCT available_at) distinct_ts,
            MIN(available_at) lo, MAX(available_at) hi, COUNT(*) n
     FROM daily_bars GROUP BY day ORDER BY day""")
c.close()
