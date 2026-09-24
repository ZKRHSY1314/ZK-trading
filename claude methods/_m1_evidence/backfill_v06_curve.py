import sqlite3
op = sqlite3.connect(r"file:D:\codex-A股交易\trading_local.sqlite3?mode=ro", uri=True)
rows = op.execute("""SELECT trade_date, COUNT(DISTINCT symbol) c FROM daily_bar_cache
                     WHERE trade_date BETWEEN '2024-04-09' AND '2024-07-15' GROUP BY trade_date ORDER BY trade_date""").fetchall()
print("date        symbols")
for d,c in rows: print(f"{d}  {c}")
print()
first_dense = next(d for d,c in rows if c > 4000)
print("FIRST session with >4000 symbols:", first_dense)
n = op.execute("SELECT COUNT(DISTINCT trade_date) FROM daily_bar_cache WHERE trade_date >= ? AND trade_date <= '2026-09-04'",(first_dense,)).fetchone()[0]
print("sessions from that dense floor to window end:", n)
op.close()
