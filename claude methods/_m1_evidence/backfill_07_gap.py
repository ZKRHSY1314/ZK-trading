import sqlite3, os, datetime as dt
ROOT=r"D:\codex-A股交易"
tl=sqlite3.connect(f"file:{os.path.join(ROOT,'trading_local.sqlite3')}?mode=ro",uri=True); tl.row_factory=sqlite3.Row
mh=sqlite3.connect(f"file:{os.path.join(ROOT,'market_history.sqlite3')}?mode=ro",uri=True); mh.row_factory=sqlite3.Row
def q(c,sql,params=()):
    print("SQL:"," ".join(sql.split()))
    out=[dict(r) for r in c.execute(sql,params).fetchall()]
    for r in out[:25]: print("   ",r)
    if len(out)>25: print(f"    ... {len(out)} rows total")
    print(); return out

print("### 1. absolute earliest/latest bar anywhere")
q(tl,"SELECT MIN(trade_date) mn, MAX(trade_date) mx FROM daily_bar_cache WHERE length(trade_date)=10")
q(mh,"SELECT MIN(trade_date) mn, MAX(trade_date) mx FROM daily_bars")

print("### 2. observed session dates: count + density vs weekdays")
d=q(tl,"SELECT DISTINCT trade_date FROM daily_bar_cache WHERE length(trade_date)=10 ORDER BY trade_date")
dates=[dt.date.fromisoformat(r["trade_date"]) for r in d]
first,last=dates[0],dates[-1]
wd=sum(1 for i in range((last-first).days+1) if (first+dt.timedelta(days=i)).weekday()<5)
print(f"observed_sessions={len(dates)} first={first} last={last} weekdays_in_span={wd} session_per_weekday={len(dates)/wd:.4f}")
ws=dt.date(2023,9,4); we=dt.date(2026,9,4)
wd_win=sum(1 for i in range((we-ws).days+1) if (ws+dt.timedelta(days=i)).weekday()<5)
gap_end=first-dt.timedelta(days=1)
wd_gap=sum(1 for i in range((gap_end-ws).days+1) if (ws+dt.timedelta(days=i)).weekday()<5)
print(f"window {ws}..{we}: weekdays={wd_win}  estimated_sessions={wd_win*len(dates)/wd:.0f} (measured density)")
print(f"head gap {ws}..{gap_end}: weekdays={wd_gap}  estimated_missing_sessions={wd_gap*len(dates)/wd:.0f}")
print()

print("### 3. modal per-symbol depth (confirms the 500-bar API/code cap)")
q(tl,"""WITH per AS (SELECT symbol, COUNT(*) n FROM daily_bar_cache
        WHERE length(trade_date)=10 GROUP BY symbol)
        SELECT n AS bars_per_symbol, COUNT(*) AS symbols FROM per
        GROUP BY n ORDER BY symbols DESC LIMIT 12""")

print("### 4. symbols by exchange prefix (indices excluded)")
q(tl,"""SELECT CASE WHEN symbol LIKE 'SH000%' OR symbol LIKE 'SZ399%' THEN 'INDEX'
                    ELSE substr(symbol,1,2) END AS grp,
        COUNT(DISTINCT symbol) AS symbols FROM daily_bar_cache GROUP BY grp ORDER BY symbols DESC""")

print("### 5. instruments in market_history: listed-before-window-start, still active in window")
q(mh,"""SELECT status, COUNT(*) FROM instruments GROUP BY status""")
q(mh,"""SELECT exchange, COUNT(*) FROM instruments GROUP BY exchange""")
q(mh,"""SELECT COUNT(*) AS listed_on_or_before_window_start
        FROM instruments WHERE list_date IS NOT NULL AND list_date <= '2023-09-04'
          AND exchange IN ('SH','SZ','BJ')""")
q(mh,"""SELECT COUNT(*) AS listed_during_window
        FROM instruments WHERE list_date > '2023-09-04' AND list_date <= '2026-09-04'
          AND exchange IN ('SH','SZ','BJ')""")
q(mh,"""SELECT COUNT(*) AS delisted_during_window
        FROM instruments WHERE delist_date IS NOT NULL AND delist_date BETWEEN '2023-09-04' AND '2026-09-04'""")
q(mh,"""SELECT COUNT(*) AS null_list_date FROM instruments WHERE list_date IS NULL""")

print("### 6. amount (成交额) presence per source in the window - what a re-pull would fix")
q(tl,"""SELECT source, COUNT(*) AS rows, SUM(CASE WHEN amount IS NULL THEN 1 ELSE 0 END) AS amount_null
        FROM daily_bar_cache WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04'
        GROUP BY source ORDER BY amount_null DESC""")
q(tl,"""SELECT COUNT(DISTINCT symbol) AS symbols_with_any_null_amount FROM daily_bar_cache
        WHERE amount IS NULL AND length(trade_date)=10""")
