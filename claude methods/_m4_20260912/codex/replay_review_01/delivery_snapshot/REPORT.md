# M4-03B development replay — REPORT (delivery 01, `ready_for_review`)

Task `M4-03B-DEVELOPMENT-REPLAY-20260912` (task file `8290d8c8…`). Run id `829d42809e978c04` (= sha256(input hash + model hash)[:16]); run folder `claude methods/_m4_20260912/claude_03b/runs/829d42809e978c04`; sealed input hash `a3afa77cb7c4ff529a0f1e20ee4a1db933559ff995fd631ab2261b16bba84e15`; model hash `396ff8dc1aa7896ac5b35524a5b5c5dfef66d6626364b7f3d5753cb47ef2ae94`. Frozen engines `83a28b54…` / `2b3eec83…` / `faec444e…` (policy hashes `9bea8348…` / `633f78d9…` / `013f1580…`), accepted mapping `276cb037…`. Status: **ready_for_review — not accepted; M4_complete=false.**

## 0. Three distinct outcomes (read this first)

1. **Already validated synthetic engine evidence** (M4-01 / M4-02A / M4-02B / M4-03A, unchanged): the kernel, ledger, risk layer and the causal mapping are deterministic and correct on synthetic fixtures; re-confirmed here by 13 focused synthetic tests run inside this task's guard before any historical access (two-symbol global order, causal other-held marks, halts, capacities, censoring, hash determinism, future-suffix control, raw refusals).
2. **This actual assumed historical-shape replay** (calendar slice 2022-08-24…2025-04-01 = 250 warmup sessions + 378 decision sessions 2023-09-04…2025-03-31 + the next legal session as metadata only; B0 fixed, nothing tuned): under the declared assumption set the frozen chain produced the observed counts in §3 — primary branch `assumed_full_fill`: buy attempts 423, buy fills 392, exit intents 410, hypothetical end equity `954371.97` (return `-0.045628`, realized `-43144.69`) versus benchmark SH000300 `0.009966` — **conditional on assumptions, every record graded `assumed`, every position `adjustment_uncertainty=true`; not historical execution evidence.**
3. **Unmet genuine historical execution evidence**: the raw branch (capture instants kept as availability) produced no intents and 0 ledger records; decisions refused the marks/benchmark/signals as `future_evidence` ({'item:future_evidence:benchmark': 378, 'item:future_evidence:mark': 17402, 'item:future_evidence:signal': 959}). The M4 acceptance item "at least one deliberately simple baseline generates expected non-zero trades … on eligible historical data" remains **unmet**: no frozen field carries historical availability, ST/bands/capacity/fees/corporate actions/delistings are assumed or missing (M4-03A matrix), and the pool is a 2026 survivor selection. Assumed nonzero fills and passing guards do not make historical eligibility pass.

## 1. Guarded read (exactly two immutable connections)

* Guard self-check before anything: {'os.system': 'denied', 'probe_file_created': False, 'self_check_denials': 6, 'socket.socket': 'denied', "sqlite3.connect(':memory:')": 'denied', 'sqlite3.connect(unlisted file uri)': 'denied', 'subprocess.run': 'denied', 'write_inside_claude_03b': 'allowed', 'write_outside_claude_03b': 'denied'}. Synthetic validation inside the runner: 13 tests, 0 failures, 0 errors, guard denials during tests 0.
* `history`: `file:D:/codex-A%E8%82%A1%E4%BA%A4%E6%98%93/claude%20methods/_m2_codex_implementation_20260910/staging_runs/ths_v2_20260910_041710_97ef9c09/run_ths_v2_20260910_041710_97ef9c09/history.sqlite3?mode=ro&immutable=1` (uri=True, isolation_level=None, extension loading disabled, `PRAGMA query_only` read back = 1, authorizer: SELECT/READ/FUNCTION + read-only pragmas; everything else SQLITE_DENY).
* `trading`: `file:D:/codex-A%E8%82%A1%E4%BA%A4%E6%98%93/claude%20methods/_m2_codex_implementation_20260910/staging_runs/ths_v2_20260910_041710_97ef9c09/run_ths_v2_20260910_041710_97ef9c09/trading.sqlite3?mode=ro&immutable=1` (uri=True, isolation_level=None, extension loading disabled, `PRAGMA query_only` read back = 1, authorizer: SELECT/READ/FUNCTION + read-only pragmas; everything else SQLITE_DENY).
* Connections opened: **2**; denials during the read: 0; Q10 omitted. Stores before/after/final: identical sha256 / size / mtime_ns, no `-wal`/`-shm`/`-journal` (receipt `stores_before_read`, `stores_after_read`, `stores_final`).
* SQL executed (text, bound parameters, rows):
| # | store | SQL | params | rows |
|---|---|---|---|---|
| Q1_trading_prices | trading | `SELECT symbol, trade_date, open, high, low, close, volume, amount, source, quality_status, adjustment_mode, volume_unit FROM daily_bar_cache WHERE trade_date <= ? ORDER BY symbol, trade_date` | `['2025-03-31']` | 27900 (expected 27900) |
| Q2_history_prices | history | `SELECT symbol, trade_date, adjustment_mode, open, high, low, close, volume, amount, provider, fetched_at, ingest_run_id FROM daily_bars WHERE trade_date <= ? ORDER BY symbol, trade_date` | `['2025-03-31']` | 27900 (expected 27900) |
| Q3_row_evidence | trading | `SELECT symbol, trade_date, raw_sha256, request_sha256, producer_sha256, parser_sha256, capture_receipt_sha256, capture_producer_manifest_sha256, observed_at, point_index, qualification_sha256, source_name, source_name_status FROM row_evidence WHERE trade_date <= ? ORDER BY symbol, trade_date` | `['2025-03-31']` | 27900 (expected 27900) |
| Q4_coverage_trading | trading | `SELECT symbol, trade_date, classification FROM coverage_inventory WHERE trade_date <= ? ORDER BY symbol, trade_date` | `['2025-03-31']` | 28100 (expected 28100) |
| Q4_coverage_history | history | `SELECT symbol, trade_date, classification FROM coverage_inventory WHERE trade_date <= ? ORDER BY symbol, trade_date` | `['2025-03-31']` | 28100 (expected 28100) |
| Q5_suspensions_trading | trading | `SELECT symbol, trade_date, evidence_sha256, record_json FROM suspension_records WHERE trade_date <= ? ORDER BY symbol, trade_date` | `['2025-03-31']` | 200 (expected 200) |
| Q5_suspensions_history | history | `SELECT symbol, trade_date, evidence_sha256, record_json FROM suspension_records WHERE trade_date <= ? ORDER BY symbol, trade_date` | `['2025-03-31']` | 200 (expected 200) |
| Q6_qualification_records | trading | `SELECT symbol, record_sha256, record_json FROM qualification_records ORDER BY symbol` | `[]` | 52 (expected 52) |
| Q7_instruments | trading | `SELECT symbol FROM instruments` | `[]` | 52 (expected 52) |
| Q8_contract_trading | trading | `SELECT contract_json FROM dataset_contract` | `[]` | 1 (expected 1) |
| Q8_contract_history | history | `SELECT contract_json FROM dataset_contract` | `[]` | 1 (expected 1) |
| Q9_ingest_runs | history | `SELECT id, run_id FROM ingest_runs` | `[]` | 1 (expected 1) |

## 2. Reconciliation and sealed input

* Rows: {'Q1_trading_prices': 27900, 'Q2_history_prices': 27900, 'Q3_row_evidence': 27900, 'Q4_coverage_history': 28100, 'Q4_coverage_trading': 28100, 'Q5_suspensions_history': 200, 'Q5_suspensions_trading': 200, 'Q6_qualification_records': 52, 'Q7_instruments': 52, 'Q8_contract_history': 1, 'Q8_contract_trading': 1, 'Q9_ingest_runs': 1}; accepted price keys **27900**, accepted halt keys **200**, exclusions **0**; numeric digest `9d91bc0bed833870…` equals the prior development audit's `numeric_rows_sha256` → **True**; bars by role/segment {'benchmark:development': 756, 'benchmark:warmup': 500, 'stock:development': 17402, 'stock:warmup': 9194}; rows before the warmup window reconciled but not consumed: 48.
* Calendar: `YYYYMMDD -> YYYY-MM-DD before comparison`; slice 2022-08-24 … 2025-04-01 (629 sessions = 250 warmup + 378 development + the next legal session 2025-04-01, whose prices are never read).
* Warmup depths inside the fixed window 2022-08-24…2023-09-01 (recomputed here, not asserted from the audit): stocks with 250 bars **33**, with 0 bars **12**; partial: BJ920001=167, BJ920006=75, SH600110=242, SH600226=249, SZ002656=211.
* Sealed input hash `a3afa77cb7c4ff529a0f1e20ee4a1db933559ff995fd631ab2261b16bba84e15` over 27852 bars and 200 halt keys for 50 stocks + 2 indices; all repeats and branches consumed this one in-memory snapshot without reconnecting.

## 3. Branch results (each from a fresh ledger; two repeats per branch, hashes identical)

| branch | variant / capacity | decision stages | entry outcomes | buy attempts | sell attempts | exit intents | intents by status | end status |
|---|---|---|---|---|---|---|---|---|
| `assumed_capacity_none` | assumed / none | `halt_key`=152, `insufficient_history`=342, `new_listing_exclusion`=36, `no_signal`=16065, `not_listed`=1346, `price_row`=17402, `signal`=959, `signal_on_last_session_beyond_window`=1 | `buy`=935, `zero_size`=24 | `expired:capacity_unproven`=878, `expired:fill_price_exceeds_limit_price`=54, `expired:limit_up_no_buy_fill`=1, `expired:suspended`=1 | — | — | `expired`=934, `pending`=1 | status `valued`, cash `1000000.00`, equity `1000000.00`, return `0.000000`, realized `0.00`, benchmark `0.009966`, open positions 0, live intents beyond window 1, ledger reconcile ok True |
| `assumed_fixed_5000` | assumed / fixed_5000 | `halt_key`=152, `insufficient_history`=342, `new_listing_exclusion`=36, `no_signal`=16065, `not_listed`=1346, `price_row`=17402, `signal`=959, `signal_on_last_session_beyond_window`=1 | `buy`=470, `refused:cooldown_active`=104, `refused:symbol_held`=223, `refused:valuation_incomplete`=1, `zero_size`=161 | `expired`=152, `expired:fill_price_exceeds_limit_price`=29, `expired:limit_up_no_buy_fill`=1, `filled`=287 | `expired:fill_price_below_limit_price`=36, `filled`=429 | `held:hold`=3569, `held:unresolved`=1, `max_holding`=58, `profit_target`=134, `stop_loss`=275 | `expired`=218, `filled`=716, `pending`=3 | status `valued`, cash `650809.74`, equity `1050431.74`, return `0.050432`, realized `53973.69`, benchmark `0.009966`, open positions 10, live intents beyond window 3, ledger reconcile ok True |
| `assumed_full_fill` | assumed / full_fill | `halt_key`=152, `insufficient_history`=342, `new_listing_exclusion`=36, `no_signal`=16065, `not_listed`=1346, `price_row`=17402, `signal`=959, `signal_on_last_session_beyond_window`=1 | `buy`=424, `refused:cooldown_active`=89, `refused:symbol_held`=211, `refused:valuation_incomplete`=1, `zero_size`=234 | `expired:fill_price_exceeds_limit_price`=30, `expired:limit_up_no_buy_fill`=1, `filled`=392 | `expired:fill_price_below_limit_price`=27, `filled`=382 | `held:hold`=3243, `held:unresolved`=1, `max_holding`=53, `profit_target`=112, `stop_loss`=245 | `expired`=58, `filled`=774, `pending`=2 | status `valued`, cash `518773.97`, equity `954371.97`, return `-0.045628`, realized `-43144.69`, benchmark `0.009966`, open positions 10, live intents beyond window 2, ledger reconcile ok True |
| `raw` | raw / none | `halt_key`=152, `insufficient_history`=342, `new_listing_exclusion`=36, `no_signal`=16065, `not_listed`=1346, `price_row`=17402, `signal`=959, `signal_on_last_session_beyond_window`=1 | — | — | — | — | — | status `valued`, cash `1000000.00`, equity `1000000.00`, return `0.000000`, realized `0.00`, benchmark `None`, open positions 0, live intents beyond window 0, ledger reconcile ok True |

Refined attempt classification derived from the exported research records (side, engine intent status, kernel status, fill, kernel reasons) — the raw `attempt_outcomes` keys above group a partially filled order whose remainder expired under `buy:expired`:

| branch | side | intent status | kernel status | filled shares | kernel reasons | attempts |
|---|---|---|---|---|---|---|
| `assumed_capacity_none` | buy | expired | unfilled | no | capacity_unproven | 878 |
| `assumed_capacity_none` | buy | expired | unfilled | no | fill_price_exceeds_limit_price | 54 |
| `assumed_capacity_none` | buy | expired | unfilled | no | limit_up_no_buy_fill | 1 |
| `assumed_capacity_none` | buy | expired | unfilled | no | suspended | 1 |
| `assumed_fixed_5000` | buy | expired | partially_filled | yes | — | 152 |
| `assumed_fixed_5000` | buy | expired | unfilled | no | fill_price_exceeds_limit_price | 29 |
| `assumed_fixed_5000` | buy | expired | unfilled | no | limit_up_no_buy_fill | 1 |
| `assumed_fixed_5000` | buy | filled | filled | yes | — | 287 |
| `assumed_fixed_5000` | sell | expired | unfilled | no | fill_price_below_limit_price | 36 |
| `assumed_fixed_5000` | sell | filled | filled | yes | — | 429 |
| `assumed_full_fill` | buy | expired | unfilled | no | fill_price_exceeds_limit_price | 30 |
| `assumed_full_fill` | buy | expired | unfilled | no | limit_up_no_buy_fill | 1 |
| `assumed_full_fill` | buy | filled | filled | yes | — | 392 |
| `assumed_full_fill` | sell | expired | unfilled | no | fill_price_below_limit_price | 27 |
| `assumed_full_fill` | sell | filled | filled | yes | — | 382 |

Funnel semantics: `decision_stage` counts are mutually exclusive per (symbol, session) in the order not_listed → halt_key → missing_unconfirmed_row → price_row, and inside price_row: new_listing_exclusion (attempt session within the first five listing sessions, listing age = index(session) − index(listing_date)) → insufficient_history (fewer than 21 consecutive price-bar sessions ending at the decision session) → no_signal → signal; `entry_outcomes` are the engine's decisions for signals (buy intent / zero_size / refused with the engine's reason); attempt keys carry the kernel's reason codes; `swept_expired_at_decision` counts intents expired by the next decision's sweep; a signal on 2025-03-31 becomes a live intent for 2025-04-01 that is never attempted (censored).

## 4. Determinism, chronology and provenance

* `assumed_capacity_none`: repeat 1 `341f0bbd74dc6478…` = repeat 2 `341f0bbd74dc6478…` → identical **True**; engine chain `2b3201cd4ec305d2…`, ledger state `1a85c06cf4f4ddfd…`.
* `assumed_fixed_5000`: repeat 1 `5a955d0471a5c1c3…` = repeat 2 `5a955d0471a5c1c3…` → identical **True**; engine chain `3f985fd5062c8827…`, ledger state `50eb3ff0cc2d0f8e…`.
* `assumed_full_fill`: repeat 1 `89070db755b43a36…` = repeat 2 `89070db755b43a36…` → identical **True**; engine chain `18a8280e10c97ae0…`, ledger state `0f8c9826de10b5e2…`.
* `raw`: repeat 1 `e84b51f969ca0a7c…` = repeat 2 `e84b51f969ca0a7c…` → identical **True**; engine chain `f49f22d3dcb75aed…`, ledger state `d63ecd3579780579…`.
* Global event order: for every session, due open attempts (exits before entries, then symbol / intent id) run at 09:30 with their original bound decision contexts before the 16:00 decision; the engine's policy event clock is monotone across the whole run (proved on the synthetic two-symbol case; the historical records carry the same `state_summary.event_clock`).
* Buys at the open value OTHER held symbols at their last already-available close (model instant of that earlier session, actual dates and ages recorded under `raw_provenance[role=other_held_mark]`); a held symbol without an eligible prior close makes the re-check `valuation_incomplete` (refusal), never zero. Decisions use closes of the same session only (`max_mark_age_sessions=0`); a halted holding makes the valuation incomplete.
* Every exported research record keeps the unmodified engine record plus: `grade` (`assumed` / `raw`), `model_time`, `assumption_ids`, and `raw_provenance` with symbol / trade_date / `raw_sha256` / `point_index` / 2026 `captured_at` for every bar consumed. Model instants are never written into source fields; the engine's `source_ref` strings carry `captured=<raw instant>` verbatim.
* Future-suffix control (synthetic, inside this runner): changing high/low/close/volume of the attempt session and later bars leaves the earlier decision and the open attempt records byte-identical (`synthetic_test_receipt.json:scenarios.future_suffix_control`). Volume enters only the post-hoc `order_quantity_over_full_day_volume` diagnostic. Known ex-dates are post-hoc flags only.
* Endpoint censoring at 2025-03-31 16:00: open positions and live intents are reported with their engine states (§3 columns); no forced liquidation, no fabricated expiry, no 2025-04-01 price. Hypothetical last-close valuation status per branch: `assumed_capacity_none`=valued, `assumed_fixed_5000`=valued, `assumed_full_fill`=valued, `raw`=valued.

## 5. What stays assumed or missing (unchanged from M4-03A)

Historical availability of every bar (all captured 2026-09-09/10; model instants declared), historical ST status and true daily bands (assumed not_st / previous-close band by code-prefix board), phase-level capacity (exogenous full_fill / fixed_5000 / none), sourced fee tariffs (hypothetical fixture), corporate-action completeness (3 known ex-dates flagged post hoc; `adjustment_uncertainty=true` everywhere), delisting handling (survivor pool, untested on real data), security status (`listed` default of the declared pool), board/lot/tick (code-prefix / fixture), calendar publication time (assumed). The two stores mirror one Tonghuashun capture; vendor value accuracy was not re-proved. Nothing here upgrades an assumption to evidence.

## 6. Files

`runs/<run_id>/receipt.json` (this run's complete receipt incl. guard log, store states, SQL, determinism, safety flags), `sql_log.json`, `reconciliation.json`, `warmup_depths.json`, `funnel.json`, `branches/<branch>/{summary.json, research_records.jsonl.gz, ledger_records.jsonl.gz}`; `evidence/{prework,postwork}_verification.json`, `evidence/synthetic_test_receipt.json`; `artifact_manifest.json` written last.

Safety: `review_only=true`, `live_trading_enabled=false`, `training_eligible=false`, `strict_pit=false`, `M4_complete=false`, `M5_started=false`; production SQLite connections 0; network 0; holdout/validation price rows read 0; no self-acceptance.
