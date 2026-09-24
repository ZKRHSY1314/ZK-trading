# M4-03B proposal — one bounded read-only development replay (for Codex review; NOT authorization to execute)

Status: **proposed — revision 2 after Codex M4-03A review 01** (`394ab7f9…`; corrections in `CORRECTION_MATRIX.md`). Owner if dispatched: Claude (existing session). Reviewer: Codex. Nothing below has been run against historical data; this task (M4-03A) opened no connection. The evidence mapping in §4 is implemented as pure functions in `proposal_mapping.py` and was executed through the complete frozen risk → ledger → kernel → exit chain on synthetic bars by `validate_qualification.py` (10 full-chain cases, `evidence/validation_receipt.json:full_chain_cases`). The proposal names exactly what a single M4-03B task would read, compute and write, and what it can and cannot prove given `QUALIFICATION_MATRIX.md`.

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

## 4. Deterministic baseline, causal evidence mapping and eligibility funnel (no result-based selection)

Baseline **B0 — 20-bar SMA crossing**, fixed here and not tuned: at decision session `D` for symbol `s`, `signal = close(D) > SMA20(D) and close(D-1) <= SMA20(D-1)` where `SMA20(D)` is the mean of the 20 most recent *valid price bars* ending at `D` and the 20 preceding calendar sessions contain no halt key (otherwise `indeterminate`, counted, not traded). Benchmark `SH000300`. Engine parameters fixed: `RiskPolicy(max_position_weight 0.05, max_gross_exposure 0.60, min_cash_reserve 0, stop_loss 0.05, profit_target 0.10, max_holding 20, cooldown 5, max_mark_age 0, max_gap 0.02, intent_expiry 1, exit_priority (stop_loss, profit_target, max_holding), entry_phase open_auction, exit_phase open_auction)`, initial cash `1 000 000.00` (hypothetical), fee schedule `HYPOTHETICAL_FIXTURE_FEES_A` (0.0004 / 0.0004 / 6.00 / 0.00002 / 0.0008, `provenance=hypothetical_fixture`, effective 2022-08-24…2025-03-31, boards main/star/chinext/bse by code prefix), assumptions `HYPOTHETICAL_FIXTURE_ASSUMPTIONS_03B`: `slippage 0.002, max_participation_rate 1.0, tick 0.01, lot 100, T+1`, `unknown_state_assumptions = (('st_status','not_st'), ('listing_state','seasoned'))` (`proposal_mapping.execution_assumptions`).

### 4.1 Raw versus model time — field by field (`proposal_mapping.py`)

Every mapped object keeps two things apart: the **raw capture instant** (`row_evidence.observed_at`, 2026-09-09/10), which is written verbatim into `source_ref` as `captured=<instant>` and is never overwritten, and the **model instant** (`observed_at` / `available_at` of the object), which under `variant="assumed"` is a declared assumption named in `source_ref` as `assumptions=<ids>`, and under `variant="raw"` *is* the raw capture instant (nothing assumed). Every replay record is therefore either fully raw or fully labelled; there is no third state.

| Object | Frozen field(s) consumed | Model `observed_at` → `available_at` (assumed variant) | Assumption id | Raw variant |
|---|---|---|---|---|
| `Mark` (decision valuation), `BenchmarkObservation`, rule `Signal` | `close(D)` of stock / index; rule on closes ≤ `D` | `D 15:00:00+08:00` → `D 16:00:00+08:00` (close + 3600 s, the M3 convention); decisions at `D 16:00:00+08:00` | `ASSUMPTION:close_fields_observed_at_1500_available_at_close_plus_3600s` | capture instant (2026) |
| `SessionCalendar` | frozen sessions, `09:30`/`15:00` `+08:00`, `halted_sessions=()` (none known) | `available_at = 2022-08-24T00:00:00+08:00` | `ASSUMPTION:exchange_calendar_published_in_advance` | capture instant |
| `PriceObservation` (open attempt) | **`open(D+1)` only** (`OpenAttemptInputs.open_price`) | `D+1 09:30:00+08:00` → `D+1 09:30:00+08:00`, `kind=predeclared_assumption`, `field="open"` | `ASSUMPTION:daily_bar_open_equals_0930_auction_print` | capture instant, `kind=contemporaneous` (refused) |
| `TradabilityEvidence` (open attempt) | halt ledger key for `D+1`; `close(D)` (band); **`open(D+1)`** (limit state) — nothing else | `D+1 09:30:00+08:00` → `D+1 09:30:00+08:00`; `status = suspended` if halt key else `tradable`; `band_state=band`, `limit_up/down = round_half_up(close(D) × (1 ± ratio), 0.01)`; `limit_state = limit_up` if `open(D+1) ≥ hi`, `limit_down` if `open(D+1) ≤ lo`, else `none`; `st_status=unknown` (declared `not_st`), `listing_state = new_listing` for the first 5 sessions after listing else `unknown` (declared `seasoned`) | `…tradable_at_open`, `…band_from_previous_close…`, `…limit_state_from_open_print_versus_band_only`, `…st_status_not_st`, `…listing_state_seasoned_after_5_sessions` | capture instant; no declared states (kernel `unknown_state`) |
| `LiquidityCapacity` | **none** (never `volume`) | `D+1 09:30:00+08:00`; see 4.2 | `…full_fill…` / `…fixed_exogenous_capacity_5000…` | absent |
| halt session (`D+1` is a confirmed full-day halt key) | no print exists | `status=suspended`, `limit_state=none`, price = previous close **placeholder** with `field="previous_close_placeholder_no_print"` — the kernel returns `unfilled: suspended` before any fill logic; the placeholder can never fill (proved: `halt_session_placeholder_cannot_fill`) | `ASSUMPTION:full_day_halt_no_print_previous_close_placeholder_cannot_fill_status_suspended` | — |

Consequences of the mapping, all proved on the frozen engines by `validate_qualification.py:full_chain_cases`:
* `high/low/close/volume(D+1)` and every later bar **cannot reach the open attempt** — `OpenAttemptInputs` has no field for them. Changing the whole future suffix (03-19 close 10.30 → 11.00 = band top, volume ×5, later bars) leaves the decision record, the intent, the budget, the tradability state (`none`) and the fill (400 @ 10.08, cash 95 961.92) byte-identical (`future_suffix_invariance`: D1 and X1 record hashes and the kernel `result_hash` equal; the next decision then diverges, as it must, once the 03-19 close is available).
* `limit_state` comes from the open print alone: open at the band top → `limit_up` → buy `unfilled: limit_up_no_buy_fill`; open at the band bottom → `limit_down` → buy fills (`limit_state_from_open_only`).
* Close fields are consumed only after their own close; the open field only at its own session's declared 09:30 instant. The earlier blanket rule "no `available_at` earlier than the bar's own close" is withdrawn (it was impossible for the open print and is replaced by the table above).
* Strict-raw is a **separate path, not a switch on the assumed path**: with raw capture instants everywhere the frozen risk layer refuses the marks, the benchmark and the signal at the decision stage as `future_evidence`; no intent, no reservation, no ledger record exists (`strict_raw_decision_refusal`). Raw attempt evidence offered to an intent created under the assumed decision is refused at the attempt stage as `future_evidence` with the intent and its reservation untouched (`raw_attempt_after_assumed_decision`). Neither is described as "strict with capacity removed".
* Capacity removal is a **sensitivity of the assumed chain**: identical assumed decision and attempt evidence with `capacity=None` → kernel `unfilled: capacity_unproven`, ledger `no_effect`, intent `expired`, reservation released, cash untouched (`assumed_capacity_removed_sensitivity`). It measures how much of the assumed result rests on the capacity assumption; it is not historical execution evidence.
* Known ex-dates are a **post-hoc performance flag** (`ex_date_flags`): a position whose `[entry_session, last_session]` window contains a known ex-date is flagged and reported separately; nothing is removed, re-decided or altered in the ledger, because the original availability of the implementation notices is not established (`corporate_action_original_available_at=null`). Every position carries `adjustment_uncertainty=true` regardless.

### 4.2 Capacity model (fixed now; consistent with `allowance = floor(capacity × max_participation_rate)`)

`max_participation_rate = 1.0` in every variant (the capacity itself is already the assumption; a second haircut would be double counting). Two mutually exclusive, pre-fixed variants, both independent of full-day volume:

| Variant | `LiquidityCapacity` | Hand-calculated samples (kernel, proved in `capacity_model_consistency`) |
|---|---|---|
| `full_fill` (primary) | `quantity = order quantity`, `basis=hypothetical_full_fill_equals_order_quantity`, `kind=predeclared_assumption` | order 100 → allowance 100 → **filled 100**; order 400 → allowance 400 → **filled 400**; a second attempt under the same `capacity_id` with `consumed_quantity=400` → **`capacity_exhausted`** (cumulative accounting kept) |
| `fixed_5000` (sensitivity) | `quantity = 5 000` shares per open attempt, `basis=hypothetical_fixed_exogenous_shares` | order 400 → **filled 400** (allowance 5 000, consumed 400); order 9 900 → **partially filled 5 000**, remaining 4 900 (whole lots), the remainder expires with the one-session window |
| `none` | no capacity object | `unfilled: capacity_unproven` (assumed-chain sensitivity above) |

Neither variant is changed after seeing results; `order_quantity / volume(D+1)` is reported as a post-hoc bar diagnostic only.

### 4.3 Funnel

Counts only, reported at every stage, no stage reordered after seeing results:
`symbol-sessions 50×378 = 18 900 → listed 17 554 → price row 17 402 → not in first 5 listing sessions → 20 valid bars & no halt in lookback → signal true → not held / no live intent / not in cooldown → next session inside window → intent sized by the risk layer (zero_size counted) → attempt at D+1 open: ASSUMED full_fill filled / unfilled (limit_up, band, gap, halt) → exits (stop / target / max holding; halts leave positions open) → performance at 2025-03-31 close vs SH000300; plus the two sensitivities (fixed_5000, capacity none) and the strict-raw path (refusal reasons per stage, expected 0 intents)`.

Determinism: the whole run is executed twice in-process with identical inputs and must produce identical record hash chains; the run id is derived from input hashes + policy hashes, not from a clock. Full-chain smoke on synthetic bars (assumed variant, hand-calculated, `assumed_full_chain_smoke`): budget 5 000.00 → 400 shares (estimate 4 014.08, limit 10.20); open 10.05 → fill 10.08, cost 4 038.08, cash 95 961.92, `evidence_grade=assumed` with the four assumption ids (price, capacity, st_status, listing_state) in the kernel record and `captured=` in every `source_ref`; hold at 10.30 (equity 100 081.92, entry reference 10.0952); stop at close 9.50 → sell limit 9.31 → open 9.40 fills 9.38 → cash 99 704.84, realized −295.16, cooldown from 03-21; four `cooldown_active` refusals; re-entry sized 400 (budget 4 985.24); performance −0.002952 vs benchmark −0.010000; ledger reconciles.

## 5. Outputs and write scope

Only `claude methods/_m4_20260912/claude_03b/` (new): `run_m4_03b_replay.py`, `runs/<run_id>/{receipt.json, sql_log.json, reconciliation.json, funnel.json, engine_records.jsonl.gz, ledger_records.jsonl.gz, performance.json}`, `REPORT.md`, `artifact_manifest.json` (last). A run refuses to overwrite an existing run folder. No file outside the folder, no accepted module, no freeze, no Codex evidence, no PLAN/state is touched; nothing staged or committed.

## 6. What this read could prove — and what it cannot fix

Could prove (all pool-conditional, all under the assumption set above):
1. the accepted kernel → ledger → risk chain runs end-to-end on 17 402 real bar shapes with real halts (5 symbols, 152 keys) and known ex-dates, deterministically (identical hashes on re-run);
2. the **strict-raw** result: with raw capture instants the frozen engines refuse at the decision stage (`future_evidence`), so the strict count is **0 intents / 0 fills** with the actual refusal reasons recorded per stage — reported truthfully, never manufactured by injecting assumptions and then removing capacity;
3. the **assumed-grade** count: how many B0 signals, intents, fills, exits and what hypothetical PnL vs SH000300 arise under the declared assumptions — the first "expected non-zero trades" figure on real bars, or truthfully zero if B0 never crosses under the exclusions — plus the two sensitivities (fixed 5 000-share capacity, capacity removed);
4. the exact exclusion ledger (warmup depth, halts, new listings, zero-size, expiry beyond window) and the post-hoc ex-date flags.

Cannot fix (missing metadata, out of this read's power): historical availability of any bar (strict PIT stays false), historical ST status and true daily bands, phase-level capacity / queue depth, sourced fee tariffs with effective dates, corporate-action completeness (splits/bonus/rights), delisting events (survivor pool), vendor value accuracy, independent source corroboration. Therefore the M4 acceptance item "…on eligible historical data" remains **unmet** after M4-03B; the honest deliverable is "synthetic proof + assumed-grade development replay + strict count 0", not historical execution evidence.

## 7. Acceptance conditions Codex can check

* Receipt shows exactly two connections to the two URIs, `query_only` read back `1`, authorizer installed, zero denied events, input hashes/sizes/mtimes identical before and after, no sidecars, SQL log equal to the table in §2 with the expected row counts.
* Funnel counts sum consistently stage by stage; strict-raw intents = 0 with recorded refusal reasons; every ASSUMED fill record carries `evidence_grade='assumed'` and lists its assumption ids, and every `source_ref` carries the raw `captured=` instant; every position carries `adjustment_uncertainty=true`; no record dated after 2025-03-31; close fields never consumed before their own session's 16:00 model availability, the open field never before its own session's 09:30 model instant, and no attempt record depends on `high/low/close/volume` of its own session (the future-suffix invariance check of `validate_qualification.py` is re-run inside the M4-03B receipt on two synthetic suffixes).
* Two in-process runs produce identical chain hashes; the report separates synthetic proof / assumed replay / strict historical evidence and states the unmet requirement.
