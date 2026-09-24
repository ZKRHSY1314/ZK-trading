import sqlite3, textwrap
MH = 'file:D:/codex-A股交易/market_history.sqlite3?mode=ro'
c = sqlite3.connect(MH, uri=True)
c.row_factory = sqlite3.Row
def q(label, sql, params=()):
    print('='*78); print(label); print(textwrap.dedent(sql).strip()); print('-'*78)
    for r in c.execute(sql, params):
        print(dict(r))
    print()

# --- A. NULL-SAFE equality (their '<>' silently drops NULL rows) -------------
q('A1 NULL-safe divergence census (IS NOT catches NULLs; <> does not)', """
SELECT COUNT(*) AS total_rows,
       SUM(CASE WHEN available_at IS NULL THEN 1 ELSE 0 END) AS avail_null,
       SUM(CASE WHEN fetched_at  IS NULL THEN 1 ELSE 0 END) AS fetch_null,
       SUM(CASE WHEN available_at IS NOT fetched_at THEN 1 ELSE 0 END) AS nullsafe_differ,
       SUM(CASE WHEN available_at <> fetched_at THEN 1 ELSE 0 END) AS naive_differ,
       SUM(CASE WHEN TRIM(available_at) IS NOT TRIM(fetched_at) THEN 1 ELSE 0 END) AS trimmed_differ,
       SUM(CASE WHEN available_at IS NOT updated_at THEN 1 ELSE 0 END) AS differ_from_updated_at,
       COUNT(DISTINCT available_at) AS distinct_avail_values
FROM daily_bars
""")

# --- B. format census: any 10-char (trade_date fallback) / tz-suffixed values?
q('A2 format census of available_at (string-comparison safety)', """
SELECT LENGTH(available_at) AS len,
       (available_at LIKE '%T%') AS has_T,
       (available_at LIKE '%Z' OR available_at LIKE '%+%') AS has_tz,
       COUNT(*) AS n, MIN(available_at) AS lo, MAX(available_at) AS hi
FROM daily_bars GROUP BY len, has_T, has_tz ORDER BY n DESC
""")

# --- C. adjustment_mode / provider partitions: is any subset PIT-correct? ----
q('A3 partition by adjustment_mode + provider + quality_status', """
SELECT adjustment_mode, provider, quality_status, COUNT(*) n,
       COUNT(DISTINCT symbol) syms,
       MIN(trade_date) td_lo, MAX(trade_date) td_hi,
       MIN(available_at) av_lo, MAX(available_at) av_hi,
       SUM(CASE WHEN available_at IS NOT fetched_at THEN 1 ELSE 0 END) differ
FROM daily_bars GROUP BY 1,2,3 ORDER BY n DESC
""")

# --- D. ingest_run linkage --------------------------------------------------
q('A4 ingest_run_id linkage (is available_at run-scoped?)', """
SELECT CASE WHEN ingest_run_id IS NULL THEN 'NULL' ELSE 'set' END AS run_id_state,
       COUNT(*) n FROM daily_bars GROUP BY 1
""")
c.close()
