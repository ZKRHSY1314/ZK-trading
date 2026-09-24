import sqlite3

OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"


def ro(p):
    c = sqlite3.connect("file:" + p + "?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


op = ro(OP)
mh = ro(MH)


def show(title, sql, conn=None, params=(), cap=40):
    conn = conn or op
    print("\n### " + title)
    print("SQL: " + " ".join(sql.split()))
    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception as e:
        print("  ERROR:", e)
        return []
    for r in rows[:cap]:
        print("   ", dict(r))
    if len(rows) > cap:
        print("    ... %d rows total" % len(rows))
    return rows


print("=" * 100)
print("G. Are the 5,566 admitted symbols really all stocks? (index / ETF contamination)")
print("=" * 100)

show("G1 market_history.instruments exchange + asset_type census",
     """SELECT exchange, asset_type, board, COUNT(*) AS n
        FROM instruments GROUP BY exchange, asset_type, board ORDER BY n DESC""", conn=mh)

adm = [r["symbol"] for r in op.execute(
    "SELECT DISTINCT symbol FROM daily_bar_cache WHERE quality_status='ready'")]
print("\n  admitted symbols: %d" % len(adm))


def prefix_bucket(s):
    u = s.upper()
    if u.startswith("SH"):
        core = u[2:]
    elif u.startswith("SZ"):
        core = u[2:]
    elif u.startswith("BJ"):
        core = u[2:]
    else:
        core = u
    return u[:2] + "|" + core[:3]


from collections import Counter
c = Counter(prefix_bucket(s) for s in adm)
print("  admitted symbols by exchange|code-prefix (top 30):")
for k, v in c.most_common(30):
    print("    %-10s %d" % (k, v))

print("\n  SQL basis: SELECT DISTINCT symbol FROM daily_bar_cache WHERE quality_status='ready'")

# non-stock buckets: SH000/SH510/SH511/SH512/SH513/SH515/SH518/SH560/SH561/SH562/SH563/SH588
# SZ399/SZ159, BJ899
NONSTOCK_PREFIXES = ("SH|000", "SH|510", "SH|511", "SH|512", "SH|513", "SH|515",
                     "SH|516", "SH|517", "SH|518", "SH|560", "SH|561", "SH|562",
                     "SH|563", "SH|588", "SZ|399", "SZ|159", "BJ|899")
nonstock = [s for s in adm if prefix_bucket(s) in NONSTOCK_PREFIXES]
print("\n  admitted symbols whose code shape is INDEX or ETF: %d" % len(nonstock))
print("    -> %s" % sorted(nonstock)[:40])
print("  admitted symbols with A-share stock code shape: %d" % (len(adm) - len(nonstock)))

print("\n" + "=" * 100)
print("H. Does ANY simulated P&L exist in this system today? (tests the impact clause)")
print("=" * 100)

tabs = [r["name"] for r in op.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
pnl_tabs = [t for t in tabs if any(k in t.lower() for k in
            ("backtest", "simulation", "paper", "pnl", "position", "fill", "equity", "trade"))]
print("  candidate P&L-bearing tables: %s" % pnl_tabs)
for t in pnl_tabs:
    n = op.execute("SELECT COUNT(*) FROM \"%s\"" % t).fetchone()[0]
    print("    %-45s rows=%d   [SQL: SELECT COUNT(*) FROM %s]" % (t, n, t))

show("H1 do the 39 runs report any non-zero return metric?",
     """SELECT COUNT(*) AS runs,
               SUM(CASE WHEN metrics_json LIKE '%"total_return": 0.0%'
                         OR metrics_json LIKE '%"total_return":0.0%' THEN 1 ELSE 0 END) AS zero_return_runs
        FROM historical_backtest_runs""")

show("H2 sample metrics_json of run 39",
     """SELECT id, substr(metrics_json,1,400) AS metrics, substr(benchmark_json,1,300) AS bench,
               substr(execution_warnings_json,1,300) AS warns
        FROM historical_backtest_runs WHERE id=39""")

show("H3 daily equity - does equity ever leave initial cash?",
     """SELECT COUNT(*) AS eq_rows,
               COUNT(DISTINCT equity) AS distinct_equity_values,
               MIN(equity) AS min_eq, MAX(equity) AS max_eq
        FROM historical_backtest_daily_equity""")

print("\n" + "=" * 100)
print("I. The one malformed trade_date - is it admitted by the engine?")
print("=" * 100)

show("I1 malformed date rows and their quality_status",
     """SELECT symbol, trade_date, length(trade_date) AS len, quality_status, source
        FROM daily_bar_cache WHERE length(trade_date) <> 10""")

print("\n" + "=" * 100)
print("J. Would switching to market_history gain anything? (universe + span)")
print("=" * 100)

show("J1 market_history.daily_bars span and symbol count",
     """SELECT COUNT(*) AS rows_, COUNT(DISTINCT symbol) AS syms,
               MIN(trade_date) AS mn, MAX(trade_date) AS mx
        FROM daily_bars""", conn=mh)

show("J2 market_history rows inside the research window",
     """SELECT COUNT(*) AS rows_, COUNT(DISTINCT symbol) AS syms
        FROM daily_bars
        WHERE trade_date >= '2023-09-04' AND trade_date <= '2026-09-04'""", conn=mh)

show("J3 cache span",
     """SELECT MIN(trade_date) AS mn, MAX(trade_date) AS mx, COUNT(DISTINCT trade_date) AS d
        FROM daily_bar_cache WHERE quality_status='ready'""")

show("J4 market_history distinct trade dates",
     """SELECT COUNT(DISTINCT trade_date) AS d FROM daily_bars""", conn=mh)
