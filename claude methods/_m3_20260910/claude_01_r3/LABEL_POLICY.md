# M3 Label Policy `m3.labels` — version `0.3.0-draft` (R3 consumer-integrity revision)

Task: M3-01-R3-CONSUMER-INTEGRITY-20260910, incorporating Codex's in-task supplements `R3_BENCHMARK_INTEGRATION_SUPPLEMENT.md` (`a66f1db5…`) and `R3_IN_PROGRESS_FEEDBACK.md` (`e0092b69…`). Author: Claude (existing fork). Status: **proposed / ready_for_review** — every rule is a provisional hypothesis awaiting Codex review; nothing is adopted, frozen, validated or accepted. Supersedes `0.2.0-draft` (module `fe604647…`, tests `6fd2aa98…`, manifest `34b28360…`) and `0.1.0-draft` (`6a0590cf…` / `efa2e21c…` / `428bb425…`); both remain byte-identical under `claude_01/`, `claude_01_r2/` and Codex's `review_01_input/` / `review_02_input/`.

Implementation: `backend/app/research/m3_labels.py` (pure stdlib; no SQLite, network, clock, subprocess or `app` import). Machine copy: `LABEL_POLICY.json`. Tests: `backend/tests/test_m3_labels.py` (105 tests; see `REGRESSION_MAP.md`).

## 0. Unchanged research semantics

Label families, phase/volume/liquidity/regime thresholds, session windows, same-date matching, limit handling, the single BJ920006/2023-12-04 scope exception, the corporate-action statuses, the strict/retrospective cutoff rules, the split proposal (development 2023-09-04…2025-03-31, validation 2025-04-01…2025-12-31, final holdout 2026-01-01…2026-09-04) and the purpose allowlist are exactly those of `0.2.0-draft` (`claude_01_r2/LABEL_POLICY.md §1–§8`). No threshold was tuned; no M2 price was read. `training_eligible=false`, `strict_pit_eligible=false` for every retrospective (M2-derived) record, `review_only=true`, `live_trading_enabled=false`.

M2 facts unchanged: 50 stocks + 2 benchmarks; SH600011 and BJ920000 carry a *partial* known set of nine cash events; the other 48 stocks have unknown action coverage; benchmarks are not stocks.

## 1. Consumer boundaries (R2-A … R2-F, feedback items 1–2, benchmark supplement)

### 1.1 One ledger validator (R2-A)

`validate_ledger(record)` is the only path that interprets a review ledger and is called by `review_status`, `attach_review` (before and after the tentative append), `RecordRegistry` (hence matching through summaries), `admit_cases` and `library_counts`. It checks, in order: ledger present with all fields; `bound_episode_id/record_hash/policy_hash` equal to the exact current core (`ledger_binding_mismatch` — a valid ledger transplanted onto another valid core fails); `ledger_hash`; every entry's fields, enums, tz-aware time, non-empty `evidence_refs`, non-empty `execution_ref`, canonical-hex case binding, `synthetic` flag equal to the record's, optional 64-hex `case_prefix_hash`; entry content hash (`review_entry_hash_mismatch`); case/policy binding of every entry; supersession chain — target must be an earlier entry of the same reviewer, not already superseded (no fork / stale branch), with a non-empty reason and a **strictly later** parsed instant; plain duplicates and conflicting current verdicts of one reviewer; and finally that the cached `status/reviewer_ids/current_verdicts/agreement/consensus_verdict/reviewed_at` equal the state reconstructed from validated entries (`ledger_status_mismatch`). Dissent stays in the append-only history; the label `record_hash` excludes the ledger and is unchanged by any review. Names never prove executions: `independence_asserted_by_generator=false`; the coordinator supplies actual individual reviews with execution references.

### 1.2 Summaries bound to verified cores (R2-B)

`validate_summary_format` checks schema/types/enums/finite amounts/canonical hex (`z…z` is not hex) and that `split_role` derives from `decision_date`. A compact summary is **never** evidence by itself: `case_summary(summary)` without a registry raises `unresolved_record_reference`; with a `RecordRegistry` (in-memory registry of verified cores with validated ledgers) it is resolved by `episode_id`, checked against the core's `record_hash` (`stale_record_reference`) and compared field by field with the core's own summary (`summary_conflicts_with_core`). `verify_record` now also checks derived fields against their inputs (`split_role`, cutoff convention, `role`, `current_state`, label enums, `episode_id` derivation, finite amount, `training_eligible/live_trading_enabled = false`) and — feedback item 2 — recomputes `decision_fingerprint = sha256(canonical(identity.decision_inputs))` and checks the declared duplicates (`cutoff`, `calendar`, `synthetic`, `universe`, `security_context`, `stock_rows`, `benchmark_rows`, `benchmark_symbol`, `context_usable`) against the record fields (`decision_fingerprint_mismatch` / `decision_inputs_mismatch`). These are internal consistency checks; the frozen reader's input manifest and actual review receipts supply external provenance.

### 1.3 Matching revalidated at counting (R2-C)

`match_controls` accepts verified full records or registry-resolved summaries; its output is `m3.labels.match.v3` with policy hash/version and `(episode_id, record_hash)` references. `revalidate_match(match, registry, purpose)` requires the fixed policy `k_min/k_max`, resolves the positive and **every** control to a core (all referenced records must be supplied in memory — `unresolved_record_reference` / `stale_record_reference` otherwise), recomputes the match under the fixed policy and compares the control set, counts, `unmatched`, date, split role and purpose (`match_record_mismatch`). Caller-owned `k_min`, `control_count`, `unmatched` or symbols can no longer admit anything. Identical input records collapse (`duplicates_collapsed`), conflicting cores or ledgers under one `episode_id` fail closed.

### 1.4 Episode-prefix qualification (R2-D, feedback item 1)

The unit of positive admission is an **episode** whose three-consecutive-session prefix is established, never a daily record. `qualified_episodes` builds episodes per symbol from the **complete supplied chronology** (`build_episodes`: verified members, consecutive calendar sessions, one policy/mode/convention/calendar/universe; a missing or rejected intermediate day breaks continuity). `episode_prefix_proof(episode)` is the immutable proof: symbol, phase, start, `established_at` (third member's date), the first three member ids and record hashes, representative = the member at `established_at`, policy/calendar/mode/convention, and `prefix_hash`; it never contains the eventual end, later eligibility or any outcome. `prefix_proof_for(records, calendar, representative)` returns the proof a reviewer must bind.

**Episode review binding (new API):** `ReviewRecord.case_prefix_hash` carries the `prefix_hash` the reviewer actually considered. Counting recomputes the proof from the supplied chronology and admits an episode only when every current consensus entry is bound to that hash (`review_not_bound_to_prefix` for daily-only reviews; `review_prefix_binding_mismatch` when earlier member evidence changed after the review). Daily reviews stay valid daily reviews; they never silently become episode reviews.

### 1.5 Counting contract (`library_counts`)

Reports separately: `raw_input_records`, `unique_records`, `duplicates_collapsed`, admission by split role for the declared purpose, synthetic/real, review states, `positively_reviewed_records`, `episodes_total`, `episodes_duration_established` / `_not_established`, **`qualified_reviewed_positive_episodes`** (alias `qualified_positives`; = established prefix ∧ representative admitted, non-synthetic, in frozen universe, observed, candidate ∧ independent positive review with non-synthetic, evidenced, prefix-bound current entries ∧ revalidated same-date match with 3–5 distinct controls), `disqualified_episodes` by reason, `unique_controls` / `control_uses` / `control_reuse_max`, and `effective_dependence_groups` (chain-connected qualified episodes) as a separately reported limitation. `target` states the original criterion (`THREE_YEAR_RESEARCH_EXECUTION_GOAL.md:187-208`: ≥ 50 independently reviewed positive episodes with 3–5 matched controls each); `target_met` compares `qualified_reviewed_positive_episodes` with 50 and is never derived from dependence groups or daily records. Control records keep their own evidence and review status inside each qualified episode entry.

### 1.6 Consumed-only identity (R2-E)

Only facts the decision actually consumed enter `identity.decision_inputs`: an offered security context or coverage that is not usable at the cutoff (strict mode, declared available later) is stored in `request_diagnostics.offered_context_not_consumed` / `offered_coverage_not_consumed`; the core keeps a deterministic `{"effective": "unknown", "status": "not_available_at_cutoff", "usable": false}` (or `{"status": ..., "usable": false}` for coverage). Two different unavailable declarations therefore yield one identity, while two different *available* declarations yield different identities. Benchmark identity uses the price fields only (§1.8). PIT checks are unchanged: an offered-but-unavailable fact still marks `pit.facts.security_context=false` and `security_facts_not_available_at_cutoff`.

### 1.7 Reference-price chronology by basis (R2-F)

`validate_position_state` verifies, per basis: `next_session_open` — the reference session must be the next calendar session after the entry decision (`position_reference_not_next_session`) and evidence `available_at ≥` that session's open (09:30+08:00); `session_close` — reference ≥ entry decision and `available_at ≥` that session's close (15:00+08:00); both raise `position_reference_available_before_observable` otherwise, and the declared price must equal the consumed open/close. `declared` is never verifiable: `basis_verified=false`, price events `review_required` (`reference_basis_declared_unverified`). Determinate stop/exit/hold remain only under a verified basis, `none_verified`/`complete_known` actions, no ex-date in the holding window and an observed decision session; missing/suspended sessions give `unknown`.

### 1.8 Role-aware benchmark contract (supplement)

Benchmark rows (`SH000###`/`SZ399###` real, `SYN9#####` synthetic) must carry the retained M2 units `volume_unit = amount_unit = "not_applicable"` (`benchmark_units_must_be_not_applicable` otherwise — an index claiming share/CNY units is not honest); OHLC are index levels (positive, finite, ordered, unadjusted); the stock vwap envelope does not apply; `volume`/`amount` are retained uninterpreted aggregates — finite non-negative numbers or `None` (`invalid_benchmark_aggregate` otherwise) — never consumed as liquidity, never vwap-checked and excluded from the decision identity (`benchmark_price_fingerprint`). The regime uses a price-only kernel (close, ma60, return_60; `regime.price_only=true`, `benchmark_volume_amount_consumed=false`). Stock rows keep `share`/`CNY` units (`unsupported_volume_unit` / `unsupported_amount_unit` for anything else), the vwap envelope and the scoped BJ920006 exception. A benchmark symbol cannot be labelled or matched (`instrument_role_mismatch`), a stock cannot serve as benchmark. Thresholds untouched.

## 2. Input contract deltas vs `0.2.0-draft`

| Item | Change |
| --- | --- |
| `Observation.amount_unit` | new field (default `CNY`); benchmarks require `not_applicable` |
| `ReviewRecord.case_prefix_hash` | new optional field for episode reviews |
| `match_controls(..., registry=None)` | summaries require a `RecordRegistry` |
| `revalidate_match`, `RecordRegistry`, `validate_ledger`, `validate_summary_format`, `episode_prefix_proof`, `qualified_episodes`, `prefix_proof_for`, `benchmark_price_fingerprint`, `open_time` | new public helpers |
| `review_status(record)` | takes the record (validates the ledger against the core), no longer a bare ledger |
| `library_counts` | requires every referenced control in `cases`; keys renamed as in §1.5 (`qualified_positives` kept as alias) |
| output schema | `m3.labels.output.v3`; `security_context`/`context_availability` carry consumed-only content; `provenance.context_evidence_refs` only when consumed |

## 3. Material choices for Codex review (carried + new)

1–13 from `0.2.0-draft` unchanged.
14. Benchmarks must declare `not_applicable` units (share/CNY on an index is rejected rather than tolerated).
15. Episode reviews must bind `case_prefix_hash`; daily reviews without it never qualify an episode.
16. `library_counts` fails closed when a referenced control record is absent from `cases` (declared in-memory requirement) rather than silently disqualifying.
17. `revalidate_match` recomputes from the referenced controls only (validity of the claimed set under policy), not from the original pool (optimality is not re-established).

## 4. Limitations

No real case, review or count exists; the admissible-positive fixture (fixture-only real-format codes with `syn:fixture-only` refs) proves the counting path admits a genuinely bound episode exactly once — it is not a case. The M2 corpus remains retrospective-only with unknown action coverage for 48 stocks; `qualified_reviewed_positive_episodes=0` is the only honest value today. No performance, precision, return or effectiveness claim is made or possible.
