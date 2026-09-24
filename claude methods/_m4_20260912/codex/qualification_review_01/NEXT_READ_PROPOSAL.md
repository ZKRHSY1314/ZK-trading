# M4-03B proposal — one bounded read-only development replay (for Codex review; NOT authorization to execute)

Status: **proposed**. Owner if dispatched: Claude (existing session). Reviewer: Codex. Nothing below has been run; this task (M4-03A) opened no connection. The proposal names exactly what a single M4-03B task would read, compute and write, and what it can and cannot prove given `QUALIFICATION_MATRIX.md`.

## 1. Frozen inputs (byte-pinned; a mismatch aborts before any connection)

| Role | Path (project-relative) | SHA-256 | Bytes |
|---|---|---|---|
| trading store | `claude methods/_m2_codex_implementation_20260910/staging_runs/ths_v2_20260910_041710_97ef9c09/run_ths_v2_20260910_041710_97ef9c09/trading.sqlite3` | `c0b26660ab903541e7e213ee312c565be73547bb3cc8c142486999717e3edeca` | 38 969 344 |
| history mirror | `…/run_ths_v2_20260910_041710_97ef9c09/history.sqlite3` | `eda17434ab67496c33eed275b35045c140bad72802b4dcbf981ff22422c53003` | 10 604 544 |
| qualification bundle | `claude methods/_m2_codex_implementation_20260910/qualification_v2_reviewed.json` | `992bd79ce9d2e38d1a0a8ae2f9890cd26daebcd3d2ab664d5caab171ec3e0f37` | — |
| metadata index | `claude methods/_m3_20260910/codex/metadata_index_01/index.json` | `14f1bad7d393b4e15bf73111a9d96a78c8b156784f9ccbb084d6b606d3a152e9` | — |
| calendar | `backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json` | `f1f1ce33c5cceb5c530c3271fc951405cb5624d2f30becec85dc7a85fd47e656` | — |
| universe | `claude methods/_m1_closure/pilot_symbols.csv` | `97e251ae84fc927486127a96b4966ed8fc59fac0b744b7d6f186b2b1548886fe` | — |
| audit reference | `claude methods/_m3_20260910/codex/development_input_audit_01/result.json` | `dd3ac6ffde13ba0127a39163d23e3cebb148ca9a93f90d25c17cd4a22402d157` | — |
| engines (frozen) | `backend/app/research/m4_execution.py` / `m4_portfolio.py` / `m4_risk.py` | `83a28b54…` / `2b3eec83…` / `faec444e…` (policy hashes `9bea8348…` / `633f78d9…` / `013f1580…`) | — |

Pre-read and post-read: `sha256`, `st_size`, `st_mtime_ns` of every input; `-wal` / `-shm` / `-journal` must not exist next to either store before or after; any difference → the run is marked `input_modified` and its outputs are discarded (kept only as a failure receipt).

## 2. Connection and SQL (exactly the accepted M3 reconciliation surface; nothing new)

* URI: `file:<posix path>?mode=ro&immutable=1` (`sqlite3.connect(uri, uri=True, isolation_level=None)`); `conn.enable_load_extension(False)`; `PRAGMA query_only=ON` then `PRAGMA query_only` read back and required `== 1`; `set_authorizer` allowing only `SQLITE_SELECT`, `SQLITE_READ`, `SQLITE_FUNCTION` and read-only pragmas (`table_info`, `page_count`, `page_size`, `schema_version`, `query_only`, `index_list`, `index_info`), everything else (write, `ATTACH`, `DETACH`, DDL) → `SQLITE_DENY`. Audit hook: `sqlite3.connect` allowed only for the two exact URIs above (any other path or flag → abort); `socket.*`, `subprocess.*`, `os.system`, `os.exec*`/`spawn*`/`fork` denied; every `open` for writing outside the output folder denied; bytecode disabled. Exactly two connections, both closed and re-verified.
* Queries (SQL text + bound parameters + row counts are logged verbatim; expected counts from the frozen audit; a mismatch aborts):

| # | Store | SQL | Params | Expected rows |
|---|---|---|---|---|
| Q1 | trading | `SELECT symbol, trade_date, open, high, low, close, volume, amount, source, quality_status, adjustment_mode, volume_unit FROM daily_bar_cache WHERE trade_date <= ? ORDER BY symbol, trade_date` | `('2025-03-31',)` | 27 900 |
| Q2 | history | `SELECT symbol, trade_date, adjustment_mode, open, high, low, close, volume, amount, provider, fetched_at, ingest_run_id FROM daily_bars WHERE trade_date <= ? ORDER BY symbol, trade_date` | `('2025-03-31',)` | 27 900 |
| Q3 | trading | `SELECT symbol, trade_date, raw_sha256, request_sha256, producer_sha256, parser_sha256, capture_receipt_sha256, capture_producer_manifest_sha256, observed_at, point_index, qualification_sha256, source_name, source_name_status FROM row_evidence WHERE trade_date <= ? ORDER BY symbol, trade_date` | `('2025-03-31',)` | 27 900 |
| Q4 | both | `SELECT symbol, trade_date, classification FROM coverage_inventory WHERE trade_date <= ? ORDER BY symbol, trade_date` | `('2025-03-31',)` | 28 100 each |
| Q5 | both | `SELECT symbol, trade_date, evidence_sha256, record_json FROM suspension_records WHERE trade_date <= ? ORDER BY symbol, trade_date` | `('2025-03-31',)` | 200 each |
| Q6 | trading | `SELECT symbol, record_sha256, record_json FROM qualification_records ORDER BY symbol` | `()` | 52 |
| Q7 | trading | `SELECT symbol FROM instruments` | `()` | 52 |
| Q8 | both | `SELECT contract_json FROM dataset_contract` | `()` | 1 each |
| Q9 | history | `SELECT id, run_id FROM ingest_runs` | `()` | 1 (`ths_v2_20260910_041710_97ef9c09`) |
| Q10 | trading | `SELECT COUNT(*) FROM daily_bar_cache WHERE trade_date > ?` | `('2025-03-31',)` | count only; those rows are never selected |

No `SELECT *`, no other table, no row with `trade_date > '2025-03-31'` is ever fetched: validation (2025-04-01…2025-12-31) and final holdout (2026-01-01…2026-09-04) stay untouched. Row-level acceptance replicates the frozen reader's rules (numeric equality between stores, `adjustment_mode='none'`, `quality_status='qualified_candidate'`, `source='tonghuashun'`, lineage in the frozen capture list, `observed_at == fetched_at == capture.observed_at`, key in `expected_price_dates`, coverage `price` / `full_day_suspension` partition, suspension `evidence_sha256` = hash of the frozen ledger entry); every exclusion is listed with its reason; expected totals 17 402 development stock prices, 9 242 warmup stock prices, 756 + 500 index prices, 152 development halt keys.

## 3. Development / warmup limits (deterministic, declared before the read)

* Decision sessions: the 378 frozen calendar sessions `2023-09-04 … 2025-03-31`, decided at `D 16:00:00+08:00` (= close + 3600 s, the M3 `close+3600s` convention). The last decision whose order can be attempted inside the window is `2025-03-28` (next session `2025-03-31`); intents created at `2025-03-31` are recorded as `expired_beyond_window` and never attempted (no price of `2025-04-01` is read).
* Warmup: only bars with `trade_date` in the 250 frozen sessions `2022-08-24 … 2023-09-01` (exactly the 250 sessions preceding `2023-09-04` in the pinned calendar) are consumed for features; rows before `2022-08-24` (the M2 halt-extended selections of SZ002656 / SH600110 / SH600226) are reconciled but not consumed. Count predicate: `warmup_bars(symbol) = |{rows : symbol, '2022-08-24' <= trade_date <= '2023-09-01'}| <= 250`; the frozen audit already fixes the depth per symbol (36 stocks with 250, BJ920001 167, BJ920006 75, 12 with 0).
* The rule below needs 20 valid prior bars; the funnel reports `bars_available_at_decision` so the depth shortfall is visible, never silently filled.

## 4. Deterministic baseline and eligibility funnel (no result-based selection)

Baseline **B0 — 20-bar SMA crossing**, fixed here and not tuned: at decision session `D` for symbol `s`, `signal = close(D) > SMA20(D) and close(D-1) <= SMA20(D-1)` where `SMA20(D)` is the mean of the 20 most recent *valid price bars* ending at `D` and the 20 preceding calendar sessions contain no halt key (otherwise `indeterminate`, counted, not traded). Benchmark `SH000300`. Engine parameters fixed: `RiskPolicy(max_position_weight 0.05, max_gross_exposure 0.60, min_cash_reserve 0, stop_loss 0.05, profit_target 0.10, max_holding 20, cooldown 5, max_mark_age 0, max_gap 0.02, intent_expiry 1, exit_priority (stop_loss, profit_target, max_holding), entry_phase open_auction, exit_phase open_auction)`, initial cash `1 000 000.00` (hypothetical), fee schedule `HYPOTHETICAL_FIXTURE_FEES_A` (0.0004 / 0.0004 / 6.00 / 0.00002 / 0.0008, `provenance=hypothetical_fixture`, effective 2022-08-24…2025-03-31, boards = the declared code-prefix boards), assumptions `slippage 0.002, participation 0.10, tick 0.01, lot 100, T+1`, `unknown_state_assumptions = (('st_status','not_st'), ('band_state','band'), ('listing_state','seasoned'))`.

Evidence mapping (every non-contemporaneous field labelled; the 2026 capture instant is preserved in `source_ref`, never rewritten):

| Kernel / risk input | Frozen field | Label |
|---|---|---|
| decision marks / `Decision.inputs` | `close(D)` from Q1 | `available_at` **assumed** `D 16:00:00+08:00` (`source_ref = "ASSUMED_AVAILABILITY:close+3600s; captured <row_evidence.observed_at>"`) |
| calendar | frozen sessions, `09:30`/`15:00` `+08:00` | `available_at` assumed `2022-08-24T00:00:00+08:00`, `source_ref = "ASSUMED:exchange_calendar_published_in_advance; file f1f1ce33…"`, `halted_sessions=()` declared *none known* |
| `PriceObservation` for the `D+1` open-auction attempt | `open(D+1)` | `kind=predeclared_assumption`, `assumption_ref = "ASSUMPTION:daily_bar_open_equals_0930_auction_print"` (evidence grade `assumed`) |
| `TradabilityEvidence` | price row present → `status=tradable`; halt key → `suspended`; `limit_state` from `close(D+1)` vs assumed band; `st_status`/`band_state`/`listing_state` `unknown` → declared | `observed_at/available_at` assumed `D+1 09:25:00+08:00`; band = `round_tick(close(D) × (1 ± ratio))` with ratio by code-prefix board (main 0.10, STAR/ChiNext 0.20, BSE 0.30) — an assumption, ST unknown |
| `LiquidityCapacity` | **STRICT variant:** `None` → `unfilled: capacity_unproven`; **ASSUMED variant:** `quantity = order quantity`, `kind=predeclared_assumption`, `basis="hypothetical_full_fill"`, `assumption_ref="ASSUMPTION:full_fill_capacity_not_market_evidence"` | daily volume is **never** used as capacity; `order_quantity / volume(D+1)` is reported as a bar diagnostic only |
| `Instrument.board` | code-prefix group | `listing_evidence_ref` = metadata index entry (official for 9 BJ, pilot-level otherwise); first 5 sessions after `listing_date` excluded (new listing) |
| `FeeSchedule` / `ExecutionAssumptions` | fixtures above | `hypothetical_fixture` |
| corporate actions | 3 known ex-dates inside the window (BJ920000 2024-06-05, 2024-09-30; SH600011 2024-07-11) | a position window that contains a known ex-date is excluded from PnL statistics and flagged; every position carries `adjustment_uncertainty=true` |

Funnel (counts only, reported at every stage, both variants, no stage may be reordered after seeing results):
`symbol-sessions 50×378 = 18 900 → listed 17 554 → price row 17 402 → not in first 5 listing sessions → 20 valid bars & no halt in lookback → signal true → not held / no live intent / not in cooldown → next session inside window → intent sized by the risk layer (zero_size counted) → attempt at D+1 open: STRICT unfilled(capacity_unproven) | ASSUMED filled / unfilled (limit, band, gap) → exits (stop / target / max holding; halts leave positions open) → performance at 2025-03-31 close vs SH000300`.

Determinism: the whole run is executed twice in-process with identical inputs and must produce identical record hash chains; the run id is derived from input hashes + policy hashes, not from a clock.

## 5. Outputs and write scope

Only `claude methods/_m4_20260912/claude_03b/` (new): `run_m4_03b_replay.py`, `runs/<run_id>/{receipt.json, sql_log.json, reconciliation.json, funnel.json, engine_records.jsonl.gz, ledger_records.jsonl.gz, performance.json}`, `REPORT.md`, `artifact_manifest.json` (last). A run refuses to overwrite an existing run folder. No file outside the folder, no accepted module, no freeze, no Codex evidence, no PLAN/state is touched; nothing staged or committed.

## 6. What this read could prove — and what it cannot fix

Could prove (all pool-conditional, all under the assumption set above):
1. the accepted kernel → ledger → risk chain runs end-to-end on 17 402 real bar shapes with real halts (5 symbols, 152 keys) and known ex-dates, deterministically (identical hashes on re-run);
2. the **strict** count: number of attempts that reach the kernel with only contemporaneous evidence = expected **0 fills** (`capacity_unproven` and the availability rejections), reported truthfully;
3. the **assumed-grade** count: how many B0 signals, intents, fills, exits and what hypothetical PnL vs SH000300 arise under the declared assumptions — the first "expected non-zero trades" figure on real bars, or truthfully zero if B0 never crosses under the exclusions;
4. the exact exclusion ledger (warmup depth, halts, new listings, ex-date windows, zero-size, expiry beyond window).

Cannot fix (missing metadata, out of this read's power): historical availability of any bar (strict PIT stays false), historical ST status and true daily bands, phase-level capacity / queue depth, sourced fee tariffs with effective dates, corporate-action completeness (splits/bonus/rights), delisting events (survivor pool), vendor value accuracy, independent source corroboration. Therefore the M4 acceptance item "…on eligible historical data" remains **unmet** after M4-03B; the honest deliverable is "synthetic proof + assumed-grade development replay + strict count 0", not historical execution evidence.

## 7. Acceptance conditions Codex can check

* Receipt shows exactly two connections to the two URIs, `query_only` read back `1`, authorizer installed, zero denied events, input hashes/sizes/mtimes identical before and after, no sidecars, SQL log equal to the table in §2 with the expected row counts.
* Funnel counts sum consistently stage by stage; STRICT fills = 0; every ASSUMED fill record carries `evidence_grade='assumed'` and lists its assumption ids; every position carries `adjustment_uncertainty=true`; no record dated after 2025-03-31; no `available_at` earlier than the bar's own close.
* Two in-process runs produce identical chain hashes; the report separates synthetic proof / assumed replay / strict historical evidence and states the unmet requirement.
