# -*- coding: utf-8 -*-
"""INDEPENDENT re-derivation of the over-limit price-move claim. READ-ONLY."""
import sqlite3, sys, collections, json
sys.stdout.reconfigure(encoding='utf-8')
TL = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
W0, W1 = "2023-09-04", "2026-09-04"

con = sqlite3.connect("file:" + TL + "?mode=ro", uri=True)
con.execute("PRAGMA query_only=ON")
print("sqlite version", sqlite3.sqlite_version)


def q(title, sql, params=()):
    print("\n### " + title)
    print("SQL: " + " ".join(sql.split()))
    rows = con.execute(sql, params).fetchall()
    for r in rows[:40]:
        print("   ", r)
    if len(rows) > 40:
        print("    ... (%d rows total)" % len(rows))
    return rows


q("0a actual date extent of daily_bar_cache (NO window filter)",
  "SELECT MIN(trade_date), MAX(trade_date), COUNT(*), COUNT(DISTINCT trade_date), COUNT(DISTINCT symbol) FROM daily_bar_cache")
q("0b rows whose trade_date fails the ISO glob",
  "SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'")
q("0c rows outside the stated research window",
  "SELECT SUM(trade_date < '2023-09-04'), SUM(trade_date > '2026-09-04'), COUNT(*) FROM daily_bar_cache")
q("0d rows in the first 7 months of the stated window (2023-09-04..2024-04-08)",
  "SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date >= '2023-09-04' AND trade_date <= '2024-04-08'")
q("0e sessions per year, whole table",
  "SELECT substr(trade_date,1,4), COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date), COUNT(*) FROM daily_bar_cache GROUP BY 1 ORDER BY 1")
q("0f the four six-char symbols",
  "SELECT symbol, COUNT(*), MIN(trade_date), MAX(trade_date), source, adjustment_mode FROM daily_bar_cache WHERE length(symbol)=6 GROUP BY symbol")
q("0g index-sourced rows",
  "SELECT symbol, COUNT(*), source, adjustment_mode FROM daily_bar_cache WHERE source LIKE '%index%' GROUP BY symbol")
q("0h demo/error rows",
  "SELECT symbol, trade_date, close, source, adjustment_mode FROM daily_bar_cache WHERE source IN ('demo_seed_fixture','error')")
q("0i qfq close level census (tick-rounding exposure)",
  "SELECT SUM(close<0.5), SUM(close>=0.5 AND close<1), SUM(close>=1 AND close<2), SUM(close>=2 AND close<3), SUM(close>=3), MIN(close) FROM daily_bar_cache WHERE close IS NOT NULL")
q("0j closes carrying more than 2 decimal places",
  "SELECT SUM(abs(close*100 - round(close*100)) > 1e-6), COUNT(*) FROM daily_bar_cache WHERE close IS NOT NULL")

mi = {}
mcon = sqlite3.connect("file:" + MH + "?mode=ro", uri=True)
mcon.execute("PRAGMA query_only=ON")
for sym, name, board, exch, atype, ld, dd, st in mcon.execute(
        "SELECT symbol, name, board, exchange, asset_type, list_date, delist_date, status FROM instruments"):
    mi[sym] = dict(name=name, board=board, exchange=exch, asset_type=atype,
                   list_date=ld, delist_date=dd, status=st)
print("\n### 1a instruments loaded = %d" % len(mi))
print("SQL: SELECT symbol,name,board,exchange,asset_type,list_date,delist_date,status FROM instruments")


def prefix_board(s):
    if s.startswith("SH688") or s.startswith("SH689"):
        return ("star", 0.20)
    if s.startswith("SZ30"):
        return ("chi_next", 0.20)
    if s.startswith("BJ"):
        return ("beijing", 0.30)
    if s.startswith("SH60"):
        return ("sh_main", 0.10)
    if s.startswith("SZ00"):
        return ("sz_main", 0.10)
    return ("other", None)


BOARD_LIMIT = {"sh_main": 0.10, "sz_main": 0.10, "chi_next": 0.20, "star": 0.20, "beijing": 0.30}

SQL = """
SELECT symbol, trade_date, prev_date, close, prev_close, source, prev_source,
       adjustment_mode, quality_status, rn
FROM (
  SELECT symbol, trade_date, close, source, adjustment_mode, quality_status,
         LAG(trade_date) OVER w AS prev_date,
         LAG(close)      OVER w AS prev_close,
         LAG(source)     OVER w AS prev_source,
         ROW_NUMBER()    OVER w AS rn
  FROM daily_bar_cache
  WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
    AND trade_date BETWEEN ? AND ?
  WINDOW w AS (PARTITION BY symbol ORDER BY trade_date)
)
WHERE prev_close IS NOT NULL AND close IS NOT NULL AND prev_close > 0
"""
print("\n### 2 INDEPENDENT SCAN (SQL window functions, not a python loop)")
print("SQL: " + " ".join(SQL.split()))

sessions = [r[0] for r in con.execute(
    "SELECT DISTINCT trade_date FROM daily_bar_cache "
    "WHERE trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' "
    "AND trade_date BETWEEN ? AND ? ORDER BY trade_date", (W0, W1))]
sidx = {d: i for i, d in enumerate(sessions)}
print("    calendar sessions in window = %d  (%s .. %s)" % (len(sessions), sessions[0], sessions[-1]))

events = []
n_pairs = 0
for sym, td, pd_, close, pclose, src, psrc, mode, qs, rn in con.execute(SQL, (W0, W1)):
    n_pairs += 1
    ret = close / pclose - 1.0
    if abs(ret) <= 0.10:
        continue
    inst = mi.get(sym)
    board = inst["board"] if inst and inst.get("board") else None
    pb, plim = prefix_board(sym)
    if board is None:
        board = pb
    lim = BOARD_LIMIT.get(board)
    if lim is None:
        continue
    gap = sidx.get(td, -1) - sidx.get(pd_, -1)
    events.append(dict(sym=sym, d0=pd_, d1=td, pclose=pclose, close=close, ret=ret,
                       board=board, prefix_board=pb, lim=lim, gap=gap, rn=rn,
                       src0=psrc, src1=src, mode=mode, qs=qs,
                       list_date=(inst or {}).get("list_date"),
                       name=(inst or {}).get("name"),
                       status=(inst or {}).get("status")))
print("    consecutive-return pairs scanned = %d ; |ret|>10pct on limit-bearing boards = %d"
      % (n_pairs, len(events)))

disagree = [e for e in events if e["board"] != e["prefix_board"]]
print("\n### 2b events where instruments.board disagrees with the prefix rule: %d" % len(disagree))
for e in disagree[:15]:
    print("    %s inst=%s prefix=%s" % (e["sym"], e["board"], e["prefix_board"]))
allsym_dis = [(s, mi[s]["board"], prefix_board(s)[0]) for s in mi
              if mi[s].get("board") and mi[s]["board"] != prefix_board(s)[0]]
print("    whole instrument universe: %d symbols where board != prefix rule" % len(allsym_dis))
for x in allsym_dis[:15]:
    print("      ", x)

TOL = 0.005
over = [e for e in events if abs(e["ret"]) > e["lim"] + TOL]
print("\n### 3a MY over-limit count (|ret| > board_limit + 0.005), all session gaps")
print("    events=%d  distinct symbols=%d" % (len(over), len(set(e["sym"] for e in over))))
print("    by board: %s" % dict(collections.Counter(e["board"] for e in over)))
over1 = [e for e in over if e["gap"] == 1]
print("### 3b consecutive-session subset (gap==1): events=%d symbols=%d"
      % (len(over1), len(set(e["sym"] for e in over1))))
print("    by board: %s" % dict(collections.Counter(e["board"] for e in over1)))
print("    by source-pair: %s" % dict(collections.Counter((e["src0"], e["src1"]) for e in over1).most_common(8)))

over_their = [e for e in events if abs(e["ret"]) > 0.11 and abs(e["ret"]) > e["lim"] + TOL]
print("### 3c replicating their extra |ret|>0.11 prefilter: events=%d symbols=%d gap1=%d"
      % (len(over_their), len(set(e["sym"] for e in over_their)),
         len([e for e in over_their if e["gap"] == 1])))

json.dump(over, open(r"D:/codex-A股交易/claude methods/_m1_evidence/adjrefute_over.json", "w"), ensure_ascii=False)
print("\n[saved] adjrefute_over.json  n=%d" % len(over))
con.close()
mcon.close()
