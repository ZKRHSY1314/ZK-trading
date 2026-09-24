# M3-01-R3 regression map — Codex methods → results under policy `0.3.0-draft`

Codex sources (none edited): `codex/test_independent_r2.py` (`656cc5c1…`, 15 methods, recorded R2 run: 3 ok / 12 FAIL), `codex/test_feature_oracle.py` (`eb600ca2…`, 8 methods), `codex/test_independent_contract.py` (`69ffd819…`, R1, 18 methods), `codex/test_independent_r3.py` (`403145a9…`, 23 methods, recorded working run against module `80303e2c…`: 21 ok / 2 FAIL). All recorded Codex receipts (`review_02_independent_tests/`, `r3_working_consumer_tests_01/`) are untouched.

Revised suite: `backend/tests/test_m3_labels.py` — **105 tests, exit 0** (`test_output.txt`). Literal runs of the four Codex files against the final module are retained under `transcripts/codex_*_literal_against_r3_final.txt`; `transcripts/codex_r2_consumer_tests_literal_against_r3_run01.txt` is the run against the R3 module *before* the benchmark supplement (13 ok / 2 ERROR).

## 1. Codex R2 consumer file (15 methods) → `CodexR2ConsumerReproductions`

Columns: **R2 module** = Codex's recorded run against `fe604647…`; **R3 pre-supplement** = literal file against the R3 module before benchmark units became mandatory; **R3 final literal** = unchanged file against the delivered module; **repro** = same-named method in the revised suite.

| Codex method | Group | R2 module | R3 pre-supplement | R3 final literal | repro | Outcome proved on the revised API |
| --- | --- | --- | --- | --- | --- | --- |
| `test_fixture_is_candidate_and_every_case_is_synthetic` | — | ok | ok | ERROR ¹ | ok | flat fixture is a candidate, synthetic, `target_met=false` |
| `test_unmodified_review_append_preserves_core` | R2-A | ok | ERROR (`qualified_positives` key) | ERROR ¹ | ok | core hash unchanged by two reviews; `qualified_positives` alias = 0 |
| `test_transplanted_valid_ledger_cannot_accept_a_new_case_review` | R2-A | FAIL | ok | ERROR ¹ | ok | `ledger_binding_mismatch` |
| `test_library_count_rejects_tampered_ledger` | R2-A | FAIL | ok | ERROR ¹ | ok | tampered entry → `ledger_hash_mismatch` (or `review_entry_hash_mismatch` after a ledger re-hash) |
| `test_library_count_rejects_duplicate_case_records` | R2-C | FAIL | ok | ERROR ¹ | ok | identical duplicate collapses: raw 2 / unique 1 / independently_reviewed 1 |
| `test_compact_summary_cannot_relabel_candidate_controls` | R2-B | FAIL | ok | ERROR ¹ | ok | no registry → `unresolved_record_reference`; with registry → `summary_conflicts_with_core` |
| `test_compact_summary_cannot_invent_record_hash` | R2-B | FAIL | ok | ERROR ¹ | ok | `z`×64 → `malformed_summary` |
| `test_superseding_an_already_superseded_review_cannot_fork_current_verdict` | R2-A | FAIL | ok | ERROR ¹ | ok | `invalid_supersede` (stale branch) |
| `test_superseding_review_must_be_later_than_original` | R2-A | FAIL | ok | ERROR ¹ | ok | `invalid_supersede` (not strictly later) |
| `test_session_close_reference_cannot_be_available_before_reference_date` | R2-F | FAIL | ok | ok | ok | `position_reference_available_before_observable` |
| `test_non_consumed_context_does_not_change_decision_identity` | R2-E | FAIL | ok | ERROR ¹ | ok | same labels, same `episode_id` for two unavailable declarations |
| `test_future_stock_suffix_remains_invariant` | — | ok | ok | ERROR ¹ | ok | suffix invariance of core hash and id |
| `test_counting_cannot_trust_caller_lowered_control_minimum` | R2-C | FAIL | ok | ERROR ¹ | ok | `match_record_mismatch` (policy k_min/k_max fixed; controls revalidated) |
| `test_counting_cannot_trust_changed_control_identity` | R2-C | FAIL | ok | ERROR ¹ | ok | `stale_record_reference` for out-of-universe/altered control refs |
| `test_single_decision_cannot_establish_minimum_episode_duration` | R2-D | FAIL | ERROR (controls absent) | ERROR ¹ | ok | with controls supplied: 0 qualified / 0 groups / 1 independently reviewed; without them: `unresolved_record_reference` (declared in-memory requirement) |

¹ `benchmark_units_must_be_not_applicable`: Codex's R2 fixture gives its benchmark share/CNY units; under the benchmark supplement an index must carry the retained M2 units (`not_applicable`). This is the one API adaptation applied in the reproductions (`BENCH_UNITS`), exactly as Codex's own R3 file already does (`request_r3`). No assertion was weakened.

## 2. Codex R3 working file (23 methods) → revised suite

Recorded working run (module `80303e2c…`): 21 ok / 2 FAIL. Final literal run: 21 ok / 2 FAIL — the same two methods, now for the *opposite* reason: their positive-control fixture attaches reviews **without** `case_prefix_hash`, so under feedback item 1 those reviews are daily reviews and the episode is disqualified (`review_not_bound_to_prefix`). The revised suite reproduces both with the bound fixture Codex asked for.

| Codex R3 method | Feedback | final literal | reproduction | Outcome |
| --- | --- | --- | --- | --- |
| `test_complete_format_fixture_counts_one_episode` | positive control | FAIL (0 ≠ 1, reviews unbound) | `EpisodeAndCountingTests.test_admissible_positive_control_counts_exactly_once` | prefix-bound reviews + revalidated 3 controls → exactly 1 qualified episode, 3 unique controls, 1 group, `target_met=false` |
| `test_review_cannot_silently_move_to_another_episode_prefix` | item 1 | FAIL (baseline 0, reviews unbound) | `EpisodeAndCountingTests.test_review_must_bind_the_recomputed_episode_prefix` | baseline 1; earlier members from another source → proof hash changes → 0 qualified, `review_prefix_binding_mismatch`; daily-only reviews → `review_not_bound_to_prefix`; wrong hash orphaned; malformed hash rejected |
| `test_declared_decision_inputs_must_recompute_the_fingerprint` | item 2 | ok | `EpisodeAndCountingTests.test_declared_decision_inputs_must_recompute_the_fingerprint` | `decision_fingerprint_mismatch`; re-derived fingerprint/id still fails `decision_inputs_mismatch` on every declared duplicate |
| `test_single_decision_cannot_establish_minimum_episode_duration` (R3 variant) | R2-D | ok | `test_counting_rejections_through_the_same_path` | 0 qualified / 0 groups |
| `test_missing_middle_session_does_not_qualify` | R2-D | ok | same | continuity broken → `episodes_duration_not_established=2` |
| `test_unavailable_coverage_value_cannot_change_consumed_identity` | R2-E | ok | `CausalityTests.test_offered_only_unavailable_facts_do_not_change_identity` | late coverage evidence is diagnostics, not identity |
| `test_index_level_with_retained_m2_units_generates_price_only_regime` | supplement | ok | `BenchmarkIntegrationTests.test_preserved_m2_benchmark_units_produce_a_price_only_regime`, `test_unused_benchmark_aggregates_never_change_regime_or_identity` | index levels with `not_applicable` units → regime; aggregates never change regime or identity |
| `test_benchmark_role_does_not_bypass_ohlc_or_availability` | supplement | ok | `BenchmarkIntegrationTests.test_invalid_benchmark_rows_still_reject` | 14 benchmark rejections incl. OHLC, NaN, negative aggregates, availability, identity, session, adjustment, units |
| `test_stock_cannot_use_index_units_or_escape_stock_vwap` | supplement | ok | same | `unsupported_volume_unit` / `unsupported_amount_unit` / `vwap_outside_range` |
| 15 inherited R2 methods | — | ok | §1 | — |

## 3. Codex feature oracle (8 methods) → `CodexFeatureOracleReproductions`

All eight pass literally against the final module (`transcripts/codex_test_feature_oracle_literal_against_r3_final.txt`, exit 0) and are reproduced verbatim in the revised suite: terminal-bar arithmetic, 250-bar window boundary, 20-bar volume mean excluding today, 20-bar amount mean including today, k-interval return endpoints, future-suffix isolation, undefined denominators, minimum bar counts. The stock feature kernel is unchanged; the benchmark regime now uses a separate price-only kernel (`_benchmark_features`) that these oracles do not touch.

## 4. Codex R1 file (18 methods) → `CodexReviewReproductions`

Final literal run: 5 ok / 13 ERROR (10 `calendar_required`, 3 `malformed_summary`) — the same API adaptations documented in R2 (`claude_01_r2/REGRESSION_MAP.md §1`), unchanged this round. The R1 reproductions now use genuine flat records instead of bare summaries (`flat_record`), because a bare summary is no longer evidence (§1 of the policy); `test_matching_mixed_policy_not_selected` asserts `policy_hash_mismatch` on a record carrying another policy hash.

## 5. Additional R3 regressions (beyond Codex's methods)

| Group | Tests |
| --- | --- |
| R2-A ledger | `CaseLibraryTests.test_ledger_validation_is_authoritative` (transplant on load/append/count; ledger-hash, entry-hash, cached-status and missing-ledger detection; entry-level rejections; stale case version; exact/conflicting duplicates), `test_supersession_chain_rules` (fork, non-later, earlier, own-entry, reason, unknown/malformed target, forged order on load, single reviewer stays single) |
| R2-B summaries / records | `test_summaries_are_bound_to_verified_cores` (11 forged fields → `summary_conflicts_with_core`; stale/unresolved/malformed), `IdentityTests.test_record_verification_and_tamper_detection` (derived fields forged with recomputed hashes), `EpisodeAndCountingTests.test_declared_decision_inputs_must_recompute_the_fingerprint` |
| R2-C matching / counting | `test_revalidate_match_rejects_forged_serializations` (11 forgeries), `test_duplicates_conflicts_and_identity_do_not_inflate_controls`, `EpisodeAndCountingTests.test_counting_rejections_through_the_same_path` (single day, gap, wrong member, no match, absent controls, forged k_min, stale control refs, duplicate match, disputed/single reviews, unknown purpose, synthetic same-path), `test_admissible_positive_control_counts_exactly_once` (positive control, duplicate collapse, conflicting ledger) |
| R2-D episodes | `test_episodes_track_selection_changes_duration_and_continuity` (prefix proof content), `test_review_must_bind_the_recomputed_episode_prefix`, `test_dependence_groups_chain_connect`, `test_split_admission_in_counting` |
| R2-E identity | `CausalityTests.test_offered_only_unavailable_facts_do_not_change_identity` (context and coverage; consumed facts still bind) |
| R2-F chronology | `TradeStateTests.test_reference_chronology_by_basis` (next-session rule, open/close earliest instants, declared never verified), `test_unverified_basis_yields_review_required_not_price_events`, `test_position_events_with_verified_basis` (positive controls incl. session_close) |
| Supplement | `BenchmarkIntegrationTests` (3 methods, 20+ assertions) |

## 6. Prior scenarios retained

All 41 first-version scenarios and all 71 R2 scenarios remain in substance; adaptations are limited to the API changes listed in `LABEL_POLICY.md §2` (benchmark units in fixtures, registry for summaries, `review_status(record)`, `build_episodes(series, calendar)`, `library_counts` keys, prefix-bound reviews in the admissible fixture, `declared` basis → `review_required`). No expectation was weakened; the R2 tests that forged summary fields to exercise matcher rejection reasons were rewritten to use genuine records with those properties (convention, universe, suspension), since forged summaries now fail earlier by design.

## 7. Correction-work transcripts (retained)

- `transcripts/run_01_first_attempt.txt` — 103 tests, 5 F + 1 E (fixture units, ledger-hash expectation, revalidation comparison, holdout calendar range, convention forgery).
- `transcripts/run_02_after_fixes.txt` — 103 passed.
- `transcripts/run_03_after_feedback_fixes.txt` — 105 passed (prefix binding + decision-inputs recompute added).
- `transcripts/codex_r2_consumer_tests_literal_against_r3_run01.txt` — Codex R2 file vs R3 module before the supplement: 13 ok / 2 ERROR.
- `transcripts/codex_test_*_literal_against_r3_final.txt` — the four Codex files vs the delivered module (R3 21/23, R2 1/15 ¹, R1 5/18, oracle 8/8).
- `test_output.txt` — final run, 105 passed, pinned in the manifest.
