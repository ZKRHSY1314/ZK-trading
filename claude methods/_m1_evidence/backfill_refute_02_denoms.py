import sqlite3, datetime as dt
L = r"D:/codex-A股交易/trading_local.sqlite3"
H = r"D:/codex-A股交易/market_history.sqlite3"
def ro(p): return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
lc, hc = ro(L), ro(H)
def q(con, sql, p=()):
    print("SQL:", " ".join(sql.split()))
    rs = con.execute(sql, p).fetchall()
    for r in rs[:30]: print("   ->", r)
    if len(rs) > 30: print(f"   ... ({len(rs)} rows)")
    print()
    return rs

print("### A. global_market_bars real columns")
print([r[1] for r in lc.execute("PRAGMA table_info(global_market_bars)").fetchall()])
print()

print("### B. Sessions present in covered sub-range, and holes inside it")
cov = q(lc, "SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache "
            "WHERE trade_date BETWEEN '2024-04-09' AND '2026-09-04' AND length(trade_date)=10")
print("### B2. weekday count in each range (exact, python calendar)")
def weekdays(a,b):
    a=dt.date.fromisoformat(a); b=dt.date.fromisoformat(b); n=0
    while a<=b:
        if a.weekday()<5: n+=1
        a+=dt.timedelta(days=1)
    return n
wd_cov = weekdays('2024-04-09','2026-09-04')
wd_gap = weekdays('2023-09-04','2024-04-08')
wd_win = weekdays('2023-09-04','2026-09-04')
print(f"weekdays covered 2024-04-09..2026-09-04 = {wd_cov}")
print(f"weekdays gap     2023-09-04..2024-04-08 = {wd_gap}")
print(f"weekdays window  2023-09-04..2026-09-04 = {wd_win}")
sess_cov = cov[0][0]
print(f"observed sessions in covered sub-range = {sess_cov}")
print(f"holiday weekdays dropped in covered sub-range = {wd_cov - sess_cov}")
rate = sess_cov / wd_cov
print(f"observed session/weekday rate = {rate:.5f}")
print(f"=> projected gap sessions = {wd_gap} * rate = {wd_gap*rate:.1f}")
print()
print("### B3. gap-range holiday weekdays enumerated by hand (CN exchange closures)")
cn_hol = ["2023-09-29","2023-10-02","2023-10-03","2023-10-04","2023-10-05","2023-10-06",
          "2024-01-01","2024-02-09","2024-02-12","2024-02-13","2024-02-14","2024-02-15",
          "2024-02-16","2024-04-04","2024-04-05"]
print(f"enumerated closed weekdays in gap = {len(cn_hol)} -> gap sessions = {wd_gap - len(cn_hol)}")
print()

print("### C. Denominator audit: what is 5,566 and what is 5,167?")
q(lc, "SELECT COUNT(DISTINCT symbol) FROM daily_bar_cache")
q(hc, "SELECT COUNT(*) FROM instruments")
q(hc, "SELECT exchange, asset_type, COUNT(*) FROM instruments GROUP BY exchange, asset_type ORDER BY 3 DESC")
q(hc, "SELECT COUNT(*) FROM instruments WHERE list_date IS NOT NULL AND list_date <> ''")
print("### C2. instruments listed on/before window start 2023-09-04, WITH and WITHOUT indices")
q(hc, "SELECT COUNT(*) FROM instruments WHERE list_date IS NOT NULL AND list_date <> '' AND list_date <= '2023-09-04'")
q(hc, "SELECT exchange, COUNT(*) FROM instruments WHERE list_date <= '2023-09-04' AND list_date <> '' GROUP BY exchange")
print("### C3. same, EXCLUDING indices, and also requiring not-yet-delisted at window start")
q(hc, "SELECT COUNT(*) FROM instruments WHERE list_date <= '2023-09-04' AND list_date <> '' "
      "AND exchange <> 'INDEX' AND (delist_date IS NULL OR delist_date='' OR delist_date > '2023-09-04')")
print("### C4. how many instruments have NO list_date at all (unclassifiable)")
q(hc, "SELECT COUNT(*) FROM instruments WHERE list_date IS NULL OR list_date=''")
print("### C5. index symbols present in the cache (are indices being counted as stocks?)")
q(lc, "SELECT COUNT(DISTINCT c.symbol) FROM daily_bar_cache c "
      "WHERE c.symbol IN (SELECT symbol FROM instruments_x)" if False else
      "SELECT 1")
lc.close(); hc.close()
