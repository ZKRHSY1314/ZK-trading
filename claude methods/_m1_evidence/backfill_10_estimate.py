# Backfill cost model. Inputs marked MEASURED come from the SQL/log evidence in
# backfill_0*.out.txt; inputs marked ASSUMED are stated explicitly.
BR_CACHE_TABLE   = 505_012_224 / 2_891_617   # MEASURED dbstat
BR_CACHE_TOTAL   = 896_618_496 / 2_891_617   # MEASURED dbstat (table + 5 indexes)
BR_HIST_TABLE    = 835_710_976 / 2_787_736   # MEASURED dbstat
BR_HIST_TOTAL    = 1_224_204_288 / 2_787_736 # MEASURED dbstat (table + 4 indexes)
print(f"bytes/row daily_bar_cache  table={BR_CACHE_TABLE:.1f}  table+idx={BR_CACHE_TOTAL:.1f}")
print(f"bytes/row daily_bars       table={BR_HIST_TABLE:.1f}  table+idx={BR_HIST_TOTAL:.1f}")
print()

# MEASURED network throughput, symbols/second, whole-sweep averages
SINA_AVG = 5020/6470.1
THS_AVG  = 5100/9822.9
THS_AVG2 = 550/1124.2
BJ_AVG   = 340/753.8
print(f"MEASURED sym/s  sina_full_sweep={SINA_AVG:.3f}  ths_close_refresh={THS_AVG:.3f} "
      f"ths_partial={THS_AVG2:.3f}  bj_ths={BJ_AVG:.3f}")
# MEASURED instantaneous band from logs (slowest / fastest printed rate)
SINA_LO, SINA_HI = 0.45, 0.79   # sina_resumable_20260903.log
THS_LO,  THS_HI  = 0.45, 0.79   # daily_close_refresh.log / refresh_to_close.log
print(f"MEASURED instantaneous band sina {SINA_LO}-{SINA_HI}/s, ths {THS_LO}-{THS_HI}/s")
print()

N_STOCKS     = 5561      # MEASURED instruments SH+SZ+BJ
N_PRE_WINDOW = 5167      # MEASURED instruments list_date <= 2023-09-04
M_HEAD       = 146       # MEASURED-density estimate of missing sessions 2023-09-04..2024-04-08
M_WINDOW     = 733       # MEASURED-density estimate of sessions in the full window
INTERIOR     = 4673      # MEASURED interior holes inside observed spans

def est(label, symbols, sessions, req_per_symbol, lo, hi, extra_rows=0):
    rows = symbols*sessions + extra_rows
    reqs = symbols*req_per_symbol
    t_lo, t_hi = symbols/hi, symbols/lo
    print(f"{label}")
    print(f"  symbols={symbols:,}  sessions/symbol={sessions}  rows={rows:,}  requests={reqs:,}")
    print(f"  wall clock {t_lo/3600:.1f}h .. {t_hi/3600:.1f}h  (at {lo}-{hi} sym/s)")
    print(f"  storage trading_local  table={rows*BR_CACHE_TABLE/2**20:,.0f} MiB  "
          f"table+idx={rows*BR_CACHE_TOTAL/2**20:,.0f} MiB")
    print(f"  storage market_history table={rows*BR_HIST_TABLE/2**20:,.0f} MiB  "
          f"table+idx={rows*BR_HIST_TOTAL/2**20:,.0f} MiB")
    print(f"  combined table+idx     {rows*(BR_CACHE_TOTAL+BR_HIST_TOTAL)/2**20:,.0f} MiB")
    print()

est("A. HEAD GAP 2023-09-04..2024-04-08, Sina full-history path (1 request/symbol)",
    N_PRE_WINDOW, M_HEAD, 1, SINA_LO, SINA_HI)
est("A'. HEAD GAP, upper bound over every catalogued stock",
    N_STOCKS, M_HEAD, 1, SINA_LO, SINA_HI)
est("B. FULL-WINDOW RE-PULL 2023-09-04..2026-09-04, Sina (1 request/symbol)",
    N_STOCKS, M_WINDOW, 1, SINA_LO, SINA_HI)
est("C. INTERIOR HOLES only (4,673 rows across 759 symbols), Sina",
    759, 0, 1, SINA_LO, SINA_HI, extra_rows=INTERIOR)
est("D. AMOUNT REPAIR: re-pull the 4,948 symbols carrying >=1 NULL amount, Sina",
    4948, 0, 1, SINA_LO, SINA_HI, extra_rows=0)
print("D note: 306,543 existing rows are UPDATEd in place (303,449 tencent.fqkline.qfq +")
print("        3,094 tencent...unit_verified); net new storage ~0, but the WAL/page churn")
print("        touches ~306,543 * 174.7 B = %.0f MiB of table pages." % (306543*BR_CACHE_TABLE/2**20))
print()
print("E. DB->DB PROMOTION (daily_bar_cache -> market_history), MEASURED 50.74 sym/s, 2,161 rows/s")
for label, rows, syms in [("head gap A", N_PRE_WINDOW*M_HEAD, N_PRE_WINDOW),
                          ("full window B", N_STOCKS*M_WINDOW, N_STOCKS)]:
    print(f"  {label}: {rows:,} rows -> {rows/2161/60:.0f} min by rows, {syms/50.74/60:.0f} min by symbols")
