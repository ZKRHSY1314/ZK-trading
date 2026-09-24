# M3-01-R2 regression map — Codex independent methods → revised-API reproductions

Codex source: `claude methods/_m3_20260910/codex/test_independent_contract.py` (sha256 `69ffd819da5cf404e058b39e933dbfb0140b7e4bd2e79142ce1fa52695334cd6`, **not edited**). Its recorded run against the 0.1.0-draft module (`codex/review_01_independent_tests/execution.json`, exit 1, 2 ok / 16 failing methods) is preserved and was not overwritten.

Revised suite: `backend/tests/test_m3_labels.py` (71 tests, class `CodexReviewReproductions` holds the 18 one-for-one reproductions). Final run: `test_output.txt` — exit 0, 71 passed.

## 1. Why the literal Codex file cannot run unchanged against 0.2.0-draft

The corrected contract makes three inputs mandatory that Codex's 0.1-era fixtures do not carry; the literal file was executed read-only against the revised module (`transcripts/codex_independent_tests_literal_against_r2.txt`, exit 1: **5 ok, 13 ERROR, 0 FAIL**) and every ERROR is one of these two API rejections, not a contract failure:

| Rejection | Cause in the Codex fixture | Count |
| --- | --- | --- |
| `calendar_required` | `request()` builds `LabelRequest` without a `SessionCalendar` (R5 makes the injected calendar mandatory) | 10 |
| `malformed_summary` | `summary()` builds a compact control without `record_hash`, `role`, `mode`, `convention`, `policy_version`, `universe_sha256`, `in_frozen_universe`, `split_role`, `current_state` (R1/R3 forbid summaries that bypass provenance) | 3 |

Other adaptations used in the reproductions: benchmark symbols must match the benchmark role pattern (`SYN9#####`, so `SYN900300` replaces Codex's `SYN000999`); non-unknown `SecurityContext` facts need `evidence_refs`/`facts_available_at`; `Coverage(ratio, evidence_ref, available_at)` replaces the bare float for evidenced coverage (a bare float is still accepted for synthetic requests, which is what the coverage-rejection reproduction relies on); `PositionState` needs `evidence_ref`/`available_at` and a `reference_basis`; `build_episodes(outputs, calendar)` takes the calendar; `match_controls(positive, pool[, purpose])` no longer takes a session index because matching is same-date.

## 2. Method-by-method map

Result columns: **0.1** = Codex's recorded run against the first module; **0.2 literal** = the unchanged Codex file against the revised module; **R2 repro** = the reproduction in `CodexReviewReproductions` (same method name) against the revised module.

| # | Codex method | Finding | 0.1 | 0.2 literal | R2 repro | What the reproduction proves on the new API |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `test_matching_duplicate_record_does_not_meet_three_control_minimum` | R1 | FAIL | ERROR `malformed_summary` | ok | five identical summaries collapse to `control_count=1`, `identical_duplicates_collapsed=4`, `unmatched=true` |
| 2 | `test_matching_same_control_symbol_on_five_dates_is_not_five_controls` | R1 | FAIL | ERROR `malformed_summary` | ok | one symbol on five dates → 4 rejected `different_decision_date`, ≤ 1 control, `unmatched=true` |
| 3 | `test_matching_mixed_policy_not_selected` | R1 | FAIL | ok (raises `malformed_summary`, which the Codex test accepts) | ok | a control with another policy hash is rejected as `policy_mismatch`, `control_count=0` |
| 4 | `test_matching_later_decision_not_available_to_positive_cutoff` | R1 / review §2 | FAIL | ERROR `malformed_summary` | ok | a control dated after the positive is rejected `different_decision_date` (same-date rule replaces the ±10-session draft) |
| 5 | `test_episode_identity_binds_benchmark_that_changes_regime` | R3 | FAIL | ERROR `calendar_required` | ok | a changed benchmark that changes the regime changes `episode_id` (decision fingerprint covers benchmark rows) |
| 6 | `test_episode_identity_binds_security_context_that_changes_phase` | R3 | FAIL | ERROR `calendar_required` | ok | a declared ex-date that changes the phase changes `episode_id` |
| 7 | `test_late_benchmark_stays_unknown_at_decision_cutoff` | R4 | ok | ERROR `calendar_required` | ok | a benchmark bar available only in 2026 leaves the regime `unknown` at a 2024 strict cutoff |
| 8 | `test_invalid_context_enum_cannot_remove_adjustment_gate` | R4 | FAIL | ok | ok | `corporate_action_status="KNOWN"` → `invalid_security_context` |
| 9 | `test_invalid_coverage_is_rejected_not_known_market_regime` (4 subtests) | R4 | FAIL ×4 | ok | ok | `True`, NaN, 1.5, −1 → `invalid_universe_coverage` (also `False`, inf, strings in `InputRejectionTests.test_coverage_validation`) |
| 10 | `test_missing_decision_bar_cannot_label_current_candidate` | R5 | FAIL | ERROR `calendar_required` | ok | without the decision-session bar: `current_state="missing"`, selection `indeterminate` |
| 11 | `test_duplicate_cutoffs_do_not_create_three_session_episode` | R7 | ok | ERROR `calendar_required` | ok | three copies of one cutoff → `duplicate_decision_dates` (no episode at all) |
| 12 | `test_episode_end_selection_is_current_end_not_first_member` | R7 | FAIL | ERROR `calendar_required` | ok | a genuine later record whose selection changed gives `selection_at_end="non_candidate"`, `eligibility_changes=1`, `min_duration_established_at` = third session |
| 13 | `test_review_without_any_evidence_cannot_be_independently_reviewed` | R2 | FAIL | ERROR `calendar_required` | ok | a review with empty evidence is rejected `review_without_evidence`; the case stays `pending_review` |
| 14 | `test_review_is_bound_to_specific_case_and_evidence_version` | R2 | FAIL | ERROR `calendar_required` | ok | a review bound to case A (episode id + record hash + policy) cannot attach to case B: `review_case_binding_mismatch` |
| 15 | `test_holdout_unknown_purpose_cannot_claim_protected` | R8 | FAIL | ok | ok | `target_counts` (typo) → `unknown_purpose`; allowlisted purposes enforced on admission in matching/counting |
| 16 | `test_mutable_policy_export_cannot_change_labels_under_same_hash` | R3 | FAIL | ERROR `calendar_required` | ok | mutating `policy_document()` leaves labels and hash unchanged; mutating `POLICY`/`_RULES` raises `policy_hash_mismatch` (`PolicyIdentityTests`) |
| 17 | `test_known_action_does_not_emit_unadjusted_price_stop` | R6 | FAIL | ERROR `calendar_required` | ok | a known ex-date inside the holding window → phase `indeterminate`, event `review_required` with the price condition reported, never `stop_event`/`exit_event` |
| 18 | `test_position_reference_before_entry_is_rejected` | R6 | FAIL | ok | ok | `reference_date < entry_decision_date` → `position_reference_before_entry` |

Note on Codex's 0.1 tally: 19 unittest failure records = 16 failing methods (method 9 contributed four subtest records). This map treats them as 16 methods in 8 groups, as the review does.

## 3. Additional R2 regressions beyond the Codex methods

| Group | Tests (class.method) |
| --- | --- |
| R1 matching identity | `CaseLibraryTests.test_duplicates_conflicts_and_identity_do_not_inflate_controls` (conflicting duplicate raises; tampered record raises `record_hash_mismatch`; policy version, universe, convention, benchmark-role, suspended-control rejections; malformed summary; non-bool synthetic flag), `test_same_date_matching_is_deterministic_and_outcome_free`, `test_matching_split_admission_and_unknown_context` |
| R2 review provenance | `CaseLibraryTests.test_review_provenance_binding` (evidence, execution ref, reviewer kind, malformed time, synthetic-flag mismatch, wrong case, stale version of the same symbol/date, tampered ledger, exact and conflicting duplicates), `test_review_disagreement_supersession_and_independence` (disputed preserved; explicit supersession; own-entry rule; one reviewer never independent), `test_library_counts_are_fail_closed` |
| R3 identity | `IdentityTests.test_identity_binds_benchmark_context_coverage_calendar_and_state`, `test_record_hash_boundaries_and_tamper_detection`, `PolicyIdentityTests.test_exported_policy_mutation_cannot_change_labels_under_the_same_hash`, `CausalityTests.test_suffix_invariance_benchmark_context_and_state` |
| R4 non-price inputs / PIT | `InputRejectionTests.test_security_context_validation`, `test_coverage_validation`, `test_real_requests_need_real_calendar_universe_and_evidenced_coverage`, `CausalityTests.test_strict_whole_output_pit_covers_every_consumed_fact`, `test_retrospective_capture_never_strict_pit` (`captured_after_decision_window=301`), `TradeStateTests.test_limit_unknown_is_conservative` (late ST declaration not usable) |
| R5 calendar / current data | `DataQualityTests.test_missing_decision_session_cannot_label_current_candidate`, `test_suspension_on_decision_session_is_distinct_from_missing`, `test_interior_gaps_suspension_runs_and_staleness_in_sessions`, `CausalityTests.test_series_keeps_the_declared_convention_and_consumes_decision_bars`, `InputRejectionTests.test_availability_units_kinds_and_calendar` |
| R6 position events | `TradeStateTests.test_position_events_with_verified_basis` (positive controls: hold/exit/stop/invalidation/max-holding under `none_verified`), `test_unverified_basis_yields_review_required_not_price_events` (unknown, partial, ex-date in window, missing, suspended), `test_position_state_rejections` (12 rejection codes incl. price mismatch, evidence, availability, basis, sessions) |
| R7 episodes / dependence | `CaseLibraryTests.test_episodes_track_selection_changes_duration_and_continuity` (selection path, `min_duration_established_at`, series gap, duplicate/unsorted/tampered/mixed-convention/calendar-mismatch rejections), `test_dependence_groups_chain_connect` (chain, overlap, synthetic exclusion, missing indices) |
| R8 chronology | `ProtectionTests.test_split_roles_and_purpose_allowlist` (allowlist, unknown/empty/None purposes, validation vs holdout per purpose), matching/counting admission in `CaseLibraryTests` |

## 4. Prior 0.1.0-draft scenarios: retained and adapted (none removed)

All 41 first-version scenarios are retained in substance. Honest API adaptations:

- every request now passes a declared synthetic `SessionCalendar` (`CAL`, weekday sessions from 2023-01-02, `synthetic=true`); real-symbol scenarios (BJ920006 scope exception, SH600011/SZ002115 universe checks) pass a non-synthetic test-pinned calendar and a `FrozenUniverse`;
- `build_episodes(series, CAL)`; `effective_decision_dates` is replaced by `dependence_groups` (chain-connected, session-indexed);
- `match_controls(positive, pool)` (same-date rule): the pool fixtures now place every control's distribution spike on the positive's decision date; a far-dated control and a same-symbol control are kept as decoys and are asserted to be rejected;
- `ReviewRecord` gains the binding/execution fields; `PositionState` gains basis/evidence/availability; unknown corporate-action status turns the old determinate `stop_event`/`exit_event` expectations into `review_required` (the determinate expectations are kept under `verified_context()`);
- `input_availability` field names changed (`captured_after_decision_window` added; `strict_pit_eligible` moved to `pit`); `request_diagnostics` unchanged;
- `test_missing_decision_bar` semantics changed by design: the first version labelled yesterday's bar as today's candidate; the revised expectation is `current_state="missing"`.
- Observed effect of the R5 series-convention fix: the synthetic episode boundaries in `synthetic_examples.json` shift one session earlier than in `claude_01/` because the decision bar is now consumed under the declared `close+14400s` convention instead of being silently dropped by a 15:00 cutoff.

## 5. Correction-work transcripts (retained, not overwritten)

- `transcripts/run_01_first_attempt.txt` — first run of the revised suite: 71 tests, 2 failures + 1 error (retrospective availability wording, corporate-action wording for the all-unknown context, duplicate-review expectation).
- `transcripts/run_02_after_fixes.txt` — after the three fixes: 71 passed.
- `transcripts/run_03_after_session_view_fix.txt` — after excluding the decision session from interior-gap counts: 71 passed.
- `transcripts/codex_independent_tests_literal_against_r2.txt` — the unchanged Codex file against the revised module (5 ok, 13 ERROR as tabulated above).
- `test_output.txt` — final verbose run pinned in the manifest.
