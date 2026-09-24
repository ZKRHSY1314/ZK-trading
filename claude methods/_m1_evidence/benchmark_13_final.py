import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
OP = r"D:/codex-A股交易/trading_local.sqlite3"
MH = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
op=ro(OP); mh=ro(MH)

print("### Q31 any SZ399* / SH000* index-shaped symbols hiding in either store")
for lbl,c,t in (("daily_bar_cache",op,"daily_bar_cache"),("market_history.daily_bars",mh,"daily_bars")):
    q=f"SELECT symbol, COUNT(*) FROM {t} WHERE symbol LIKE 'SZ399%' OR symbol LIKE 'SH000%' OR symbol LIKE 'BJ899%' OR symbol LIKE '%399%' GROUP BY symbol ORDER BY symbol LIMIT 20"
    print(f"  {lbl} SQL:", q)
    rows=c.execute(q).fetchall()
    print("   ", rows if rows else "NONE")

print("\n### Q32 market_history.instruments: is any index there at all?")
for q in ("SELECT COUNT(*) FROM instruments WHERE exchange='INDEX'",
          "SELECT COUNT(*) FROM instruments WHERE asset_type<>'stock'",
          "SELECT DISTINCT asset_type FROM instruments",
          "SELECT COUNT(*) FROM instruments WHERE symbol LIKE '%000300%' OR symbol LIKE '%399006%'",
          "SELECT DISTINCT board FROM instruments"):
    print("  SQL:", q, "->", mh.execute(q).fetchall())

print("\n### Q33 universe_snapshots content (the only universe evidence)")
for r in mh.execute("SELECT id, universe_name, snapshot_date, provider, member_count, substr(metadata_json,1,120) FROM universe_snapshots ORDER BY snapshot_date"):
    print("   ", r)

print("\n### Q34 benchmark coverage split around 2024-06-19 within research window")
q="""WITH cal AS (SELECT trade_date FROM daily_bar_cache
      WHERE length(symbol)=8 AND substr(symbol,1,2) IN ('SH','SZ','BJ') AND symbol NOT LIKE 'SH00%'
      GROUP BY trade_date HAVING COUNT(DISTINCT symbol)>=100)
SELECT
 (SELECT COUNT(*) FROM cal WHERE trade_date BETWEEN '2023-09-04' AND '2026-09-04') cal_window,
 (SELECT COUNT(*) FROM cal WHERE trade_date BETWEEN '2023-09-04' AND '2024-06-18') cal_before_bench,
 (SELECT MIN(trade_date) FROM cal) cal_first,
 (SELECT COUNT(*) FROM daily_bar_cache WHERE symbol='SH000300' AND trade_date BETWEEN '2023-09-04' AND '2026-09-04') bench_window"""
print("SQL:", q.replace("\n"," "))
print("   ", op.execute(q).fetchone())

print("\n### Q35 benchmark bar field completeness")
q="SELECT symbol, SUM(amount IS NULL) amount_null, SUM(volume IS NULL) vol_null, SUM(open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL) ohlc_null, COUNT(DISTINCT adjustment_mode), COUNT(DISTINCT volume_unit), COUNT(DISTINCT source), MIN(updated_at), MAX(updated_at) FROM daily_bar_cache WHERE symbol IN ('SH000300','SH000001') GROUP BY symbol"
print("SQL:", q)
for r in op.execute(q): print("   ", r)
q="SELECT COUNT(*) FROM daily_bar_cache WHERE symbol IN ('SH000300','SH000001') AND (high<low OR high<close OR low>close OR close<=0)"
print("SQL(OHLC violations):", q, "->", op.execute(q).fetchone()[0])

print("\n### Q36 settings default benchmark symbol")
import subprocess
op.close(); mh.close()
