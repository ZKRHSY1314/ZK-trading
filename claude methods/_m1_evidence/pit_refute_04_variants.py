import sqlite3
OP=r"D:/codex-A股交易/trading_local.sqlite3"
c=sqlite3.connect(f"file:{OP}?mode=ro", uri=True)
def one(l,s,*a):
    v=c.execute(s,a).fetchone(); print(f"{l:74s} {v[0]}   ({v[0]/3900*100:.2f}%)"); return v[0]
D="(SELECT DISTINCT decision_id, subject, decision_cutoff dc, substr(decision_cutoff,1,10) cd FROM forecast_decisions WHERE scope='stock') d"
print("### L. HUNT FOR 2,821 — variant probes on the same 3,900 pairs ###")
one("L1 day<=cd, updated_day>cd (mine)", f"SELECT COUNT(*) FROM {D} WHERE EXISTS(SELECT 1 FROM daily_bar_cache b WHERE b.symbol=d.subject AND b.trade_date<=d.cd AND substr(b.updated_at,1,10)>d.cd)")
one("L2 full-ts: trade_date<=dc, updated_at>dc", f"SELECT COUNT(*) FROM {D} WHERE EXISTS(SELECT 1 FROM daily_bar_cache b WHERE b.symbol=d.subject AND b.trade_date<=d.dc AND b.updated_at>d.dc)")
one("L3 + created_at<=cd (bar existed at cutoff)", f"SELECT COUNT(*) FROM {D} WHERE EXISTS(SELECT 1 FROM daily_bar_cache b WHERE b.symbol=d.subject AND b.trade_date<=d.cd AND substr(b.updated_at,1,10)>d.cd AND substr(b.created_at,1,10)<=d.cd)")
one("L4 + restated flag (upd_day<>cre_day) & created<=cd", f"SELECT COUNT(*) FROM {D} WHERE EXISTS(SELECT 1 FROM daily_bar_cache b WHERE b.symbol=d.subject AND b.trade_date<=d.cd AND substr(b.updated_at,1,10)<>substr(b.created_at,1,10) AND substr(b.updated_at,1,10)>d.cd AND substr(b.created_at,1,10)<=d.cd)")
one("L5 full-ts created_at>dc? (space-vs-T bug) trade<=dc, upd>dc, cre<=dc", f"SELECT COUNT(*) FROM {D} WHERE EXISTS(SELECT 1 FROM daily_bar_cache b WHERE b.symbol=d.subject AND b.trade_date<=d.dc AND b.updated_at>d.dc AND b.created_at<=d.dc)")
one("L6 strict trade_date<cd", f"SELECT COUNT(*) FROM {D} WHERE EXISTS(SELECT 1 FROM daily_bar_cache b WHERE b.symbol=d.subject AND b.trade_date<d.cd AND substr(b.updated_at,1,10)>d.cd)")
one("L7 window-restricted bars 2023-09-04..2026-09-04", f"SELECT COUNT(*) FROM {D} WHERE EXISTS(SELECT 1 FROM daily_bar_cache b WHERE b.symbol=d.subject AND b.trade_date BETWEEN '2023-09-04' AND d.cd AND substr(b.updated_at,1,10)>d.cd)")

print("\n### M. BAR-ROWS COVERED (their 1,170,781) ###")
for lbl,cond in [("M1 upd_day>cd","substr(b.updated_at,1,10)>d.cd"),
                 ("M2 upd_day>cd AND cre_day<=cd","substr(b.updated_at,1,10)>d.cd AND substr(b.created_at,1,10)<=d.cd")]:
    v=c.execute(f"SELECT COUNT(*) FROM (SELECT DISTINCT b.symbol,b.trade_date FROM {D} JOIN daily_bar_cache b ON b.symbol=d.subject AND b.trade_date<=d.cd WHERE {cond})").fetchone()
    print(f"   {lbl:40s} distinct bar-rows touched: {v[0]}")

print("\n### N. INDEX CONTAMINATION IN THE 89.02% DENOMINATOR ###")
W="trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND trade_date BETWEEN '2023-09-04' AND '2026-09-04'"
print("N1 the 2 SH0* symbols:", c.execute("SELECT symbol,COUNT(*) FROM daily_bar_cache WHERE symbol LIKE 'SH0%' GROUP BY symbol").fetchall())
print("N2 the 6-char symbols:", c.execute("SELECT symbol,COUNT(*) FROM daily_bar_cache WHERE length(symbol)=6 GROUP BY symbol").fetchall())
tot=c.execute(f"SELECT COUNT(*) FROM daily_bar_cache WHERE {W}").fetchone()[0]
res=c.execute(f"SELECT COUNT(*) FROM daily_bar_cache WHERE {W} AND substr(updated_at,1,10)<>substr(created_at,1,10)").fetchone()[0]
print(f"N3 ALL rows      : {res}/{tot} = {res/tot*100:.2f}%")
tot2=c.execute(f"SELECT COUNT(*) FROM daily_bar_cache WHERE {W} AND length(symbol)=8 AND symbol NOT LIKE 'SH0%'").fetchone()[0]
res2=c.execute(f"SELECT COUNT(*) FROM daily_bar_cache WHERE {W} AND length(symbol)=8 AND symbol NOT LIKE 'SH0%' AND substr(updated_at,1,10)<>substr(created_at,1,10)").fetchone()[0]
print(f"N4 stocks only   : {res2}/{tot2} = {res2/tot2*100:.2f}%")
print("N5 distinct symbols restated at least once:", c.execute(f"SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache WHERE {W} AND substr(updated_at,1,10)<>substr(created_at,1,10)").fetchone()[0], "of", c.execute("SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache").fetchone()[0])
print("N6 top created->updated day pairs:")
for r in c.execute(f"SELECT substr(created_at,1,10),substr(updated_at,1,10),COUNT(*) FROM daily_bar_cache WHERE {W} GROUP BY 1,2 ORDER BY 3 DESC LIMIT 8"):
    print("    ",r)
print("\n### O. IS THERE ANY VINTAGE/AUDIT TABLE ANYWHERE? ###")
print("O1 trading_local tables w/ version|vintage|audit|history|snapshot|revision:",
  [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%version%' OR name LIKE '%vintage%' OR name LIKE '%audit%' OR name LIKE '%histor%' OR name LIKE '%snapshot%' OR name LIKE '%revis%')")])
print("O2 triggers on daily_bar_cache:", c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND tbl_name='daily_bar_cache'").fetchone()[0])
c.close()
