# M3 Label Policy `m3.labels` — version `0.2.0-draft` (R2 contract revision)

Task: M3-01-R2-CONTRACT-FIX-20260910. Author: Claude (existing fork). Status: **proposed / ready_for_review** — every rule is a provisional hypothesis awaiting Codex review; nothing is adopted, frozen, validated or accepted. This version supersedes `0.1.0-draft` (module `6a0590cf…`, tests `efa2e21c…`, manifest `428bb425…`, all preserved under `claude_01/` and Codex's `codex/review_01_input/`) and answers the eight findings R1–R8 of `M3_01_CODEX_REVIEW_20260910.md` as one contract.

Implementation: `backend/app/research/m3_labels.py` (pure stdlib; no SQLite, network, clock, subprocess or `app` import). Machine-readable copy: `LABEL_POLICY.json` (`policy_hash = sha256(canonical_json(policy))`, pinned with the producer hash in `artifact_manifest.json`). Tests: `backend/tests/test_m3_labels.py` (71 synthetic tests incl. one-for-one reproductions of the Codex methods; see `REGRESSION_MAP.md`).

## 0. Unchanged meaning

- Labels are **observable behavioural proxies** from daily OHLCVA up to an explicit decision cutoff on an injected exchange-session calendar; not evidence of a hidden controlling actor, not trade recommendations. `review_only=true`, `live_trading_enabled=false`, `semantics.hidden_actor_claim=false`, `semantics.trade_recommendation=false`, `semantics.realized_return_claim=false` on every record.
- Generator outputs are **pending-review hypotheses**; the generator never writes reviewer identity, `reviewed_at`, an approved status, or asserts that two names are two executions (`review_ledger.independence_asserted_by_generator=false`).
- `training_eligible=false` everywhere; retrospective (M2-derived) records are `strict_pit_eligible=false` without exception.
- Thresholds, windows, volume condition, liquidity thresholds and regime thresholds are the same cited hypotheses as in 0.1.0-draft (§4) and were not tuned; no M2 price was read in this task.

## 1. Label families (unchanged vocabulary, one addition)

| Family | Labels |
| --- | --- |
| Phase | `accumulation`, `markup`, `distribution`, `failed_markup`, `indeterminate` |
| Selection | `candidate`, `non_candidate`, `indeterminate`; `matched_non_candidate` only from matching |
| Entry | `signal_eligible`, `signal_not_eligible`, `indeterminate`; `tradability="unverified"`, `execution.legal_next_session="unknown"` |
| Position event | `no_trade`, `hold`, `invalidation_event`, `stop_event`, `exit_event`, **`review_required`**, **`unknown`** (new, R6) |
| Context | liquidity `L1_thin`/`L2_low`/`L3_mid`/`L4_deep`/`unknown`; regime `bull`/`bear`/`range`/`unknown`; limit assessment |
| Current state | **`observed` / `suspended` / `missing`** (new, R5) |

## 2. Input contract (R4, R5)

`Observation` fields, units and validity rules are unchanged (symbol pattern, ISO session date, tz-aware `available_at` not before the row's own close, `source_ref`, CNY unadjusted OHLC, share volume, CNY amount, vwap envelope with the single BJ920006/2023-12-04 exception, `adjustment_mode="none"`, `volume_unit="share"`). New mandatory or validated inputs:

| Input | Contract |
| --- | --- |
| `SessionCalendar(sessions, source_ref, available_at, synthetic)` | **mandatory**; strictly increasing ISO sessions; `fingerprint = sha256(canonical sessions)`; every observation date, decision date, position date must be a session (`observation_not_a_session`, `decision_date_not_a_session`, `position_state_not_a_session`); real requests need `synthetic=false` (`synthetic_calendar_for_real_request`). Calendars are never inferred from prices. For the M2 reader: the pinned AkShare calendar file with its sha256 as `source_ref`. |
| `FrozenUniverse(symbols, source_ref, sha256)` | mandatory for real requests (`universe_required`); membership recorded as `universe.in_frozen_universe`, never inferred. |
| `SecurityContext` | enums validated (`st_status ∈ {unknown, st, not_st}`, `corporate_action_status ∈ {unknown, partial_known, complete_known, none_verified}`), ISO dates, strictly increasing `known_ex_dates`, positive finite `float_shares` or None, bool `turnover_available`; **any non-unknown fact requires `evidence_refs` and `facts_available_at`** (`security_facts_without_evidence` / `…_without_availability`); `none_verified` cannot carry ex-dates and is never inferred; `unknown` cannot carry ex-dates. |
| `Coverage(ratio, evidence_ref, available_at)` or `None` | `None` = explicit unknown (regime `unknown`, reason `universe_coverage_unknown`); ratio must be a finite non-bool number in [0, 1] (`invalid_universe_coverage` for `True`, NaN, 1.5, −1, strings); a bare float is accepted only for synthetic requests and recorded as `synthetic_declared_without_availability`; real requests need the evidenced form (`coverage_without_evidence`). |
| `PositionState` | see §4.5. |
| instrument role | `SH000###`/`SZ399###` (real) and `SYN9#####` (synthetic) are benchmarks; a benchmark cannot be labelled as a stock and a stock cannot serve as benchmark (`instrument_role_mismatch`). |

Availability of non-price facts is compared with the cutoff: in `strict` mode a fact declared available after `as_of` is **not used** (context falls back to all-unknown, coverage to unknown, with reasons `security_facts_not_available_at_cutoff` / `universe_coverage_not_available_at_cutoff`); in `retrospective` mode it is used and the violation is recorded (`context_availability.status="consumed_with_availability_violation"`). Capture time is never retrofitted to historical availability.

**M2 facts correction (review §5).** The frozen `_m2_ths_v2_claude_review_20260910/r06_basis_unit_controls.json` records nine known cash events with retained documents: SH600011 ex-dates 2024-07-11 (0.20), 2025-07-10 (0.27), 2026-07-03 (0.40); BJ920000 ex-dates 2023-07-05 (0.068), 2024-06-05 (0.11), 2024-09-30 (0.06), 2025-05-15 (0.08), 2025-09-18 (0.07), 2026-05-25 (0.08). Listing dates exist in the frozen qualification/pilot metadata. These are a **partial** known set with capture provenance (`corporate_action_status="partial_known"`, `facts_available_at` = capture time), not a complete register and not `none_verified`; other symbols and unrecorded periods stay `unknown`. The later reader carries them read-only; nothing was re-fetched here.

## 3. Cutoff, availability and whole-output PIT (R4, R5)

- `Cutoff(decision_date, as_of, mode)`; the **convention** `close+<seconds>` (`as_of − 15:00+08:00 of the decision session`) is recorded on every record and a series keeps one convention (`label_series` derives each cutoff as `close_time(d) + the same offset`; it never resets to 15:00 and never advances `as_of` to admit late data — under a `close+0s` strict convention the decision bar is honestly `missing`).
- Stock/benchmark rows are usable iff their close ≤ `as_of` and `trade_date ≤ decision_date`; strict additionally requires `available_at ≤ as_of` and `as_of` within 72 h after the decision close (`strict_cutoff_too_late`).
- `input_availability` now also reports `captured_after_decision_window` (rows whose `available_at` is after `close + 72h`): for the M2 corpus this is every row (captured 2026-09-10), so `pit.facts.stock_bars=false` regardless of mode.
- **Whole-output PIT** (`pit.strict_pit_eligible`) is true only in strict mode when every consumed fact class — stock bars, benchmark bars, security facts, coverage, calendar — was available within the decision window; `pit.facts` lists each class (`null` = not consumed). Retrospective records are always `strict_pit_eligible=false`, `provenance_kind="retrospective_capture_not_point_in_time"`.

## 4. Rules, precedence, reasons (thresholds unchanged)

Windows (sessions): warmup 250; short 20; medium 60; long 120; position 250; failed-markup lookback 20; distribution-veto lookback 20; dependence window 20; max stale sessions 1; long no-price run 10; max suspensions in window 10; min episode 3. **Every gap is measured in calendar sessions** (never natural days).

### 4.1 Current-state and quality gates → `indeterminate` (precedence 0)

`decision_session_evidence_missing` (no price and no suspension record for the decision session → `current_state="missing"`), `suspension_on_decision_session` (`current_state="suspended"`), `insufficient_warmup:<n><250`, `stale_last_price:<k>_sessions` (> 1 session since the last price), `interior_missing_sessions:<n>` (sessions inside the position window with neither price nor suspension — the M2 corpus has none by construction), `long_no_price_run_in_window:<n>_sessions` (> 10 consecutive sessions without a price), `many_suspensions_in_window:<n>` (> 10), `known_corporate_action_in_window` (partial/complete-known ex-date inside the position window), `missing_feature:*`, `scope_exception_on_decision_bar`. A determinate **selection** additionally requires `current_state="observed"`.

### 4.2 Phase rules (unchanged from 0.1.0-draft)

1. `distribution`: `position_250 > 0.78 ∧ volume_ratio_20 > 1.45 ∧ (close_to_high < 0.97 ∨ return_20 < −0.03)` — `phase_replay._classify_row:306-315`.
2. `markup`: `(return_20 > 0.18 ∨ return_60 > 0.35) ∧ volume_ratio_20 > 1.05` — `:317-322`.
3. `failed_markup`: not markup now ∧ markup on one of the previous 20 bars ∧ `drawdown_from_lookback_high ≤ −0.10` — transition known at the cutoff, never back-labelled.
4. `accumulation`: `position_250 < 0.65 ∧ ma_spread_20_60 < 0.09 ∧ return_120 < 0.25` — `:334-342`.
5. otherwise `indeterminate` / `no_rule_matched`.

### 4.3 Selection, entry, limits (unchanged logic; current-state gate added)

`candidate` = observed ∧ accumulation ∧ no rule-level distribution/failed_markup in the previous 20 bars ∧ liquidity band known. Entry `signal_eligible` = candidate ∧ close > ma20 ∧ `volume_ratio_20 ≥ 1.5` ∧ no possible limit-up/limit-down ∧ non-zero volume; lowest-plausible limit threshold (4.8) when ST status is unknown **or not yet available at the cutoff**; tradability always `unverified`.

### 4.4 Liquidity and regime (thresholds unchanged)

Bands 3e7 / 1e8 / 5e8 CNY on `amount_20_mean_cny`. Regime from the benchmark's own bars at the same cutoff (ma60, return_60 ± 5 %); `unknown` when the benchmark is absent/short/missing on the decision session, when coverage is unknown or not available at the cutoff, or when coverage < 0.90.

### 4.5 Position events (R6)

`PositionState(symbol, policy_hash, entry_decision_date, reference_date, reference_price, reference_basis ∈ {next_session_open, session_close, declared}, evidence_ref, available_at)`. Rejections: binding mismatch; `position_reference_before_entry` (reference must not precede the entry decision; for `next_session_open` it must be a later session); `position_state_not_earlier`; non-session dates; non-finite/non-positive reference; missing evidence or availability; availability after the cutoff; `position_reference_price_mismatch` when the declared reference disagrees with the consumed bar's open/close for an observable basis.

Event precedence: `invalidation_event` (phase distribution/failed_markup — a phase proxy, carried with `basis_verified`) > `stop_event` (close ≤ ref·0.95) > `exit_event` (close ≥ ref·1.08 or ≥ 20 holding sessions) > `hold`. **Determinate stop/exit/hold require a verified basis**: `current_state="observed"`, reference bar consumed, corporate-action status `none_verified` or `complete_known` and no known ex-date in `(reference_date, decision_date]`. Otherwise the record carries the computed `price_condition` but the label is `review_required` (basis unverified: unknown/partial/late-available actions, ex-date in the holding window, reference bar not consumed) or `unknown` (decision session missing or suspended). Unadjusted prices therefore never *claim* a stop or profit event under uncertainty; they only report the condition. Thresholds unchanged (`offhour._signal_exit_plan:6478-6479`).

## 5. Identity, hashes and consumers (R3)

- `decision_fingerprint = sha256(canonical{stock rows consumed, benchmark symbol+rows consumed, security_context record, context_usable, coverage record, calendar fingerprint, universe sha256, cutoff record, prior_state, position_state, synthetic})`; `episode_id = sha256(canonical{namespace, policy_hash, symbol, decision_date, decision_fingerprint})[:32]`. Changing the benchmark, a declared security fact, coverage, calendar, cutoff convention or position state changes the id; appending irrelevant future rows (stock, benchmark or later-dated facts) does not.
- `record_hash = sha256(canonical core)` where the core excludes `review_ledger` and `request_diagnostics`; `verify_record` recomputes it and checks schema `m3.labels.output.v2` and the live policy hash. **Every consumer** — `case_summary`/`match_controls`, `attach_review`, `build_episodes`, `admit_cases`/`library_counts`, `annotate_outcome` — verifies before trusting; a bare `episode_id` never inherits an earlier review (`review_case_binding_mismatch`).
- Policy integrity: rules read a private copy `_RULES`; `POLICY` is the exported copy; `policy_document()` returns a fresh deep copy. `assert_policy_integrity()` re-hashes both live and exported copies on every entry point and raises `policy_hash_mismatch` if either drifted, so no label can be produced under a stale hash. Mutating an export never changes labels.

## 6. Reviews (R2)

`ReviewRecord(reviewer_id, reviewer_kind ∈ {agent, human}, reviewed_at (tz-aware), verdict ∈ {positive, negative, ambiguous, failed, reject_data}, evidence_refs (non-empty), execution_ref (non-empty external execution/evidence reference), case_episode_id, case_record_hash, case_policy_hash, synthetic, supersedes, supersede_reason, notes)`. `attach_review` verifies the case, checks the triple binding, requires matching synthetic flags, rejects malformed times/kinds/verdicts, missing evidence or execution refs, exact duplicates, conflicting duplicates by the same reviewer without an explicit `supersedes` (own earlier entry hash + reason), and a tampered ledger (`ledger_hash_mismatch`). The ledger is append-only with its own `ledger_hash`; the label `record_hash` is unchanged by reviews.

Status from *current* (non-superseded) verdicts: `pending_review` → `single_review_not_independent` → `independently_reviewed` (≥ 2 distinct reviewers agreeing) or `disputed` (disagreement preserved, `consensus_verdict=null`). `approved` stays `false`. The generator never asserts independence; two names are not two executions — the coordinator must record actual individual reviews with their execution refs. Synthetic demo reviews are flagged `synthetic=true` and can only attach to synthetic cases.

## 7. Case-library contract (R1, R7, R8)

- **Matching (reviewed correction of the withdrawn ±10-session draft):** controls must share the positive's **decision date**, mode and cutoff convention, policy hash and version, known liquidity band, known regime, universe membership/sha256 and synthetic flag; be a different stock (`role="stock"`), `non_candidate`, `current_state="observed"`; 3–5 distinct symbols, ranked by `(|ln amount_20 ratio|, symbol)`; `unmatched=true` below 3 — never relaxed to fill a pool. Identical duplicate records collapse (`identical_duplicates_collapsed`), conflicting duplicates (same symbol+date, different `record_hash`) raise. Full records are verified; compact summaries must carry every matching field including `record_hash` (`malformed_summary`) and no outcome field (`outcome_leakage`). The positive must be a verified candidate with known band and regime, in the frozen universe (real), and admissible for the declared purpose (`guard_final_holdout` on admission).
- **Episodes:** verified, chronological, unique dates, one symbol, one policy/mode/convention/calendar/universe; consecutive calendar sessions only — a series gap closes the episode (`closed_reason="series_gap"`), a phase change closes it (`phase_change`), the last one is `open_censored`. Each episode records the actual `selection_path`, `selection_at_start`/`selection_at_end`, `eligibility_changes`, `candidate_sessions`, `min_duration_established_at` (the third consecutive member's date — the start is never back-labelled), `kind` (`ambiguous` for indeterminate, `failed` for failed_markup), `episode_key`, `episode_content_hash`.
- **Dependence groups:** same-symbol episodes chain-connect when their session intervals overlap or the gap ≤ 20 sessions (transitively); each chain is one effective decision group; synthetic episodes are excluded (arithmetic-only mode reports the count but returns 0 effective groups).
- **Chronology (R8):** purpose allowlist `initial_library_admission, target_count, rule_selection, threshold_selection, parameter_search, validation_readonly_check, final_report`; unknown purposes raise `unknown_purpose`; development-only for library/selection/count purposes; validation only for `validation_readonly_check`; holdout only inside `final_report`. `match_controls`, `admit_cases` and `library_counts` call the guard themselves. Intervals unchanged: development 2023-09-04…2025-03-31; validation 2025-04-01…2025-12-31; final holdout 2026-01-01…2026-09-04.
- **Counting (`library_counts`)** distinguishes `records_total` / admitted / excluded by split role, synthetic vs real, review statuses, `positively_reviewed_episodes` (non-synthetic independent positive consensus), `qualified_positives` (additionally: in frozen universe, observed decision session, candidate, `training_eligible=false`, a match record for the same `(episode_id, record_hash)` with ≥ 3 distinct controls under `initial_library_admission`), `matched_controls_total`, `effective_dependence_groups`; `target_met` compares effective groups with 50 and is `false` for every synthetic input by construction.

## 8. Seed context and universe (unchanged)

SZ002115 / SZ002081 remain `legacy_unverified` context with zero case contribution; `assert_in_universe` rejects them; extension is a separate decision.

## 9. Material choices for Codex review (carried + new)

1–9 from 0.1.0-draft (position window 250, failed-markup −0.10/20, selection veto, band and regime thresholds, lowest-threshold limit rule, 72 h strict window, split intervals, corporate-action gate, gap gates) — unchanged numbers, now session-based.
10. Same-date matching (this revision) instead of any window.
11. Determinate price-based position events only under `none_verified`/`complete_known` — for the M2 corpus (50 symbols unknown, 2 partial) this yields `review_required`, not stop/exit events.
12. Strict cutoff `as_of` must lie within 72 h after the close for any fact class; retrospective mode is the only mode that can label the M2 corpus.
13. `interior_missing_sessions > 0` and `long_no_price_run > 10` as hard gates.

## 10. Limitations

No real case, no review, no count exists; `qualified_positives=0` and `effective_dependence_groups=0` are the only honest values today. The synthetic demo path shows the contract (accumulation → indeterminate → markup → indeterminate → failed_markup → accumulation with a non_candidate→candidate eligibility change), not market behaviour. No performance, precision, return or effectiveness claim is made or possible.
