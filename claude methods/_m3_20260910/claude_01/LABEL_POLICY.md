# M3 Label Policy `m3.labels` — version `0.1.0-draft`

Task: M3-01-LABEL-SPEC-20260910. Author: Claude (existing fork). Status: **proposed / ready_for_review** — every rule below is a provisional hypothesis awaiting Codex review; nothing here is adopted, validated or accepted.

Implementation: `backend/app/research/m3_labels.py` (pure stdlib, no SQLite, no network, no wall clock, no `app` imports). Machine-readable copy: `LABEL_POLICY.json` (the module's `POLICY` dict; `policy_hash = sha256(canonical_json(POLICY))`). Tests: `backend/tests/test_m3_labels.py` (41 synthetic adversarial tests).

Policy hash and producer hash are pinned in `artifact_manifest.json`, not repeated here, so that this document stays valid if the module is re-hashed after a Codex-requested edit.

## 0. What these labels are and are not

- Every phase / selection / trade-state label is an **observable behavioural proxy** computed from daily OHLCVA up to an explicit decision cutoff. It is not evidence of a hidden controlling actor ("主力") and not a trade recommendation. Each output carries `semantics.hidden_actor_claim=false`, `semantics.trade_recommendation=false`, `review_only=true`, `live_trading_enabled=false`.
- The generator produces **pending-review hypotheses**: `review.status="pending_review"`, `reviews=[]`, `reviewer_ids=[]`, `reviewed_at=null`, `approved=false`. It never writes a reviewer identity or an approved status.
- `training_eligible` is `false` in every output of this version: no independently reviewed case library exists yet, and the M2 corpus is `strict_pit=false`.
- Namespace `m3.labels` / policy id `m3_label_policy` are distinct from the legacy producers `observable_structure_v1` (`structure_scoring.py`), the `main_force_phase_replays.phase` vocabulary (`phase_replay.py`), `agent_learning_outcomes.outcome_label` (`outcome_labeling.py`) and the 70/30 signal split in `offhour.py`. Legacy material is cited only as hypothesis input (§4); no legacy label is imported.

## 1. Label families (task item 1)

| Family | Labels | Function |
| --- | --- | --- |
| Phase | `accumulation`, `markup`, `distribution`, `failed_markup`, `indeterminate` | `label_phase` / `rule_phase` |
| Selection | `candidate`, `non_candidate`, `indeterminate`; role `matched_non_candidate` is assigned only by matching | `label_selection`, `match_controls` |
| Trade state | entry: `signal_eligible`, `signal_not_eligible`, `indeterminate`; position event: `no_trade`, `hold`, `invalidation_event`, `stop_event`, `exit_event` | `label_entry`, `label_position_event` |
| Context | liquidity band `L1_thin`/`L2_low`/`L3_mid`/`L4_deep`/`unknown`; regime `bull`/`bear`/`range`/`unknown`; limit assessment | `label_liquidity`, `label_regime`, `limit_assessment` |

`indeterminate`, `unknown` and `no_trade` are first-class results, never coerced to a binary label.

## 2. Input contract, units, timestamps (task item 2)

`Observation` (one per symbol-session):

| Field | Type / unit | Notes |
| --- | --- | --- |
| `symbol` | `^(SH\|SZ\|BJ)\d{6}$` real; `^SYN\d{6}$` synthetic | wrong identity → `wrong_security_identity` |
| `trade_date` | `YYYY-MM-DD` exchange session date | historical close time = `trade_date 15:00:00+08:00` |
| `kind` | `price` \| `full_day_suspension` | suspension rows carry no OHLCVA (`suspension_with_prices` rejected) |
| `available_at` | ISO-8601 with UTC offset | when the research system could read the row; naive datetime rejected; must not precede the row's own close time (`availability_before_close`) |
| `source_ref` | non-empty string | provenance pointer (M2: `row_evidence.raw_sha256`/receipt id; synthetic: `syn:…`) |
| `open/high/low/close` | CNY, unadjusted | `0 < low ≤ min(open,close) ≤ max(open,close) ≤ high` |
| `volume` | share | `≥ 0`; `volume = 0` requires `amount = 0` |
| `amount` | CNY | `≥ 0`; `amount/volume ∈ [0.98·low, 1.02·high]` unless a listed scope exception |
| `adjustment_mode` | must be `none` | matches the M2 store (`daily_bar_cache.adjustment_mode='none'`) |
| `volume_unit` | must be `share` | matches `contract_v2.py:252` |

Numeric rules: finite `int`/`float` only; `bool`, `NaN`, `±inf`, `None` rejected (`nonfinite_or_missing_numeric`). Ordering: strictly increasing `trade_date` per symbol; duplicates → `duplicate_key`; disorder → `unsorted_input`. All rejections are fail-closed `LabelInputError` with a stable `code`.

Mapping to the frozen M2 candidate store (read from the frozen DDL in `_m2_ths_v2_claude_review_20260910/r02_db_schema.json`, no SQLite opened): `daily_bar_cache(symbol, trade_date, open, high, low, close, volume, amount, adjustment_mode, volume_unit)` → price observation; `coverage_inventory.classification='full_day_suspension'` + `suspension_records.evidence_sha256` → suspension observation; `row_evidence.observed_at` → `available_at` (capture time 2026-09-10, **not** the historical close); `row_evidence.raw_sha256` → `source_ref`. This mapping is documentation for the later reader task, not executed here.

`SecurityContext` (facts not derivable from OHLCVA; unknown stays unknown): `listing_date`, `name`, `st_status ∈ {unknown, st, not_st}`, `corporate_action_status ∈ {unknown, none_verified, known}`, `known_ex_dates`, `float_shares`, `turnover_available`. The M2 corpus supplies none of these except the listing date → every M2-derived output will carry `turnover_unavailable`, `float_shares_unavailable`, `adjustment_uncertainty`.

Every output carries: `policy_id`, `policy_version`, `policy_hash`, `producer_sha256` (module bytes), `cutoff{decision_date, as_of, mode}`, `input_availability{rows_consumed, availability_violations_consumed, max_trade_date_consumed, max_available_at_consumed, strict_pit_eligible, retrospective, training_eligible, provenance_kind}`, `provenance{input_fingerprint, source_refs}`, `data_quality[]` reasons, `episode_id`, `record_hash`, `review{…pending…}`. `request_diagnostics` (rows offered/excluded) is kept outside the hashed record because it depends on what was offered, not on what was consumed.

## 3. Causality and cutoff (task item 3)

- `Cutoff(decision_date, as_of, mode)`; `as_of` is explicit and tz-aware; the module never reads the clock (test `test_module_is_pure_stdlib_and_clock_free` asserts the source contains no `date.today`/`datetime.now`/`time.time`).
- A full-day bar is usable only if its close time (`trade_date 15:00+08:00`) ≤ `as_of` **and** `trade_date ≤ decision_date`.
- `strict` mode additionally requires `available_at ≤ as_of`, and `as_of` must lie within 72 h after the decision session close (`strict_cutoff_too_late`) — otherwise "available_at ≤ as_of" would let a 2026 capture masquerade as 2024 knowledge. Consumed rows are therefore point-in-time by construction → `strict_pit_eligible=true`.
- `retrospective` mode ignores availability for usability, counts `availability_violations_consumed`, and sets `strict_pit_eligible=false`, `provenance_kind="retrospective_capture_not_point_in_time"`. Applied to the M2 corpus (all rows captured 2026-09-10) a strict cutoff in 2024 consumes **zero** rows (test `test_retrospective_capture_never_strict_pit`); only retrospective mode labels it, and that mode can never claim strict PIT or training eligibility. A truncated calculation does not manufacture historical availability.
- Observation/capture time (`available_at`) and historical close time are stored and compared separately.
- Suffix invariance: the stable record (everything except `request_diagnostics`) and `record_hash`/`episode_id` are identical whether or not later rows are present, mutated or removed (test `test_suffix_mutation_and_truncation_invariance`).

## 4. Rules, precedence, reasons and their hypothesis sources (task items 1, 5, 8)

Windows (sessions): warmup 250, short 20, medium 60, long 120, position 250, failed-markup lookback 20, distribution-veto lookback 20, dependence window 20, period-match tolerance 10, staleness 1, long-gap 10, min episode 3.

Features at the decision bar (all from bars ≤ cutoff): `return_20/60/120`, `volume_ratio_20` (decision-bar volume ÷ mean of the previous 20 usable volumes; needs all 20 prior bars present and ≥ 10 usable), `ma20`, `ma60`, `ma_spread_20_60`, `position_250` = (close − min low₂₅₀)/(max high₂₅₀ − min low₂₅₀), `close_to_high`, `drawdown_from_lookback_high` (20-bar high), `amount_20_mean_cny`, `pct_change`.

### 4.1 Quality gates → `indeterminate` (precedence 0)

`insufficient_warmup:<n><250`, `no_price_bars_before_cutoff`, `suspension_on_last_observation`, `stale_last_bar:*` (>1 suspension session after the last price, or decision date > 7 calendar days after the last price), `long_gap_in_window` (> 20 calendar days between consecutive bars inside the 250-bar window), `many_suspensions_in_window` (> 10), `known_corporate_action_in_window`, `missing_feature:*`, `scope_exception_on_decision_bar`. Unknown is never zero: a missing feature blocks the label instead of defaulting.

### 4.2 Rule precedence (after the gates)

1. `distribution`: `position_250 > 0.78` ∧ `volume_ratio_20 > 1.45` ∧ (`close_to_high < 0.97` ∨ `return_20 < −0.03`). Source: `phase_replay._classify_row` distribution branch (`:306-315`), with the 120-bar position replaced by the 250-bar position to align with the warmup requirement. Reason `high_position_volume_rejection`.
2. `markup`: (`return_20 > 0.18` ∨ `return_60 > 0.35`) ∧ `volume_ratio_20 > 1.05`. Source: `phase_replay._classify_row:317-322`. Reason `return_expansion_with_volume`.
3. `failed_markup`: not markup now ∧ markup rule held on at least one of the previous 20 bars (computed from earlier data only) ∧ `drawdown_from_lookback_high ≤ −0.10`. It is a **transition known at the current cutoff after a prior observable markup**, never a label written back onto the earlier markup. Threshold provenance: `phase_replay` post-distribution watch at −0.08 (`:303-304`) and twice the `offhour._signal_exit_plan` default stop 0.05 (`:6478`). Reason `prior_markup_then_drawdown_at_cutoff`.
4. `accumulation`: `position_250 < 0.65` ∧ `ma_spread_20_60 < 0.09` ∧ `return_120 < 0.25`. Source: `phase_replay._classify_row:334-342`. Reason `range_bound_converged_averages`.
5. otherwise `indeterminate` / `no_rule_matched` (ambiguity is preserved; test `test_ambiguous_stays_indeterminate`).

`structure_scoring.py` ranges (base position 12–58 pct `:73`, controlled volume 0.65–1.45 `:84`, upper shadow ≥ 0.55 `:95`) were read and are consistent in direction, but its sigmoid scoring is not reproduced: scores are not labels.

### 4.3 Selection

`candidate` = phase `accumulation` ∧ liquidity band known ∧ no rule-level `distribution` or `failed_markup` among the previous 20 bars (`_veto_within_lookback`). `non_candidate` = phase ∈ {markup, distribution, failed_markup} or accumulation with a recent veto. `indeterminate` = phase indeterminate or liquidity unknown. The matched-control role is assigned only by `match_controls`, never by the selector.

### 4.4 Entry eligibility, tradability, execution (task item 5, last sentence)

`signal_eligible` = selection `candidate` ∧ `close > ma20` ∧ `volume_ratio_20 ≥ 1.5` ∧ limit-like not possible ∧ limit-down not possible ∧ not a zero-volume session. Volume threshold source: `dengzhan.has_forced_divergence` default `min_volume_ratio=1.5` (`:153`); the three-state pass/fail/unknown design of `dengzhan.SignalResult` is the template for `unknown ≠ fail`.

Signal eligibility is explicitly separated from tradability: every output has `entry.tradability="unverified"` and `entry.execution.legal_next_session="unknown"`, because the next session's open, limit state and suspension state are not observable at the cutoff. Daily OHLCVA never yields execution eligibility.

Limit handling: board thresholds re-declared from `app/data/price_limits.py:31-37` (`main 9.8, st 4.8, chinext 19.5, star 19.5, bse 29.0`; the module does not import it). When ST status is unknown (true for the whole M2 corpus — `row_evidence.source_name` is NULL), main-board codes use the **lowest plausible** threshold (4.8) and the assessment is `limit_like_possible`, not confirmed; a possible limit-like day blocks entry (`limit_like_possible`), a missing `pct_change` blocks it (`limit_state_unknown`).

### 4.5 Position events (review-only hypothetical position)

Bound to a `PositionState(symbol, policy_hash, entry_decision_date, reference_date, reference_price)`; binding mismatch, non-earlier dates or a non-finite reference are rejected. Precedence: `invalidation_event` (phase distribution/failed_markup at cutoff) > `stop_event` (close ≤ ref·0.95) > `exit_event` (close ≥ ref·1.08 or ≥ 20 holding sessions) > `hold`; without a position → `no_trade`. Evaluation basis is the cutoff close; no intraday fill is claimed. Thresholds: `offhour._signal_exit_plan` defaults `stop_loss_pct=0.05`, `take_profit_pct=0.08` (`:6478-6479`; the same defaults at `:2735-2736`); holding cap = dependence window.

### 4.6 Context

Liquidity band from `amount_20_mean_cny` (absolute CNY thresholds 3e7 / 1e8 / 5e8; missing → `unknown`). Regime from the benchmark's own bars at the same cutoff: `bull` (close > ma60 ∧ return_60 > +5%), `bear` (close < ma60 ∧ return_60 < −5%), else `range`; `unknown` when the benchmark has < 60 bars, lacks a bar on the decision bar's date, or `universe_coverage_on_decision_date < 0.90` (market-wide missingness). The two frozen benchmarks (`SH000300`, `SH000001`) are the intended inputs.

### 4.7 Conservative handling (task item 5)

- Unadjusted M2 prices are treated as unadjusted: all return/position features carry `semantics.adjustment_uncertainty=true` unless `corporate_action_status="none_verified"`; a **known** ex-date inside the position window forces `indeterminate`; an unknown status never becomes "no action" and a smooth chart is never used to infer absence of an action.
- Suspensions are separate observations; they never produce OHLC, are never forward-filled and never count as zero.
- Long gaps, many suspensions, insufficient warmup, stale last bar → `indeterminate` with the reason.
- Missing limit/IPO/float/turnover data → recorded as `data_quality` reasons; entry treats unknown limit state as blocking.
- BJ block-scope exception: exactly one pinned key `BJ920006 / 2023-12-04` (per `M2_FINAL_ACCEPTANCE_20260910.md §5.3`) is accepted by the vwap validity check; its volume and amount are excluded from every ratio mean, and when it is the decision bar `volume_ratio_20=None` → `indeterminate` (`scope_exception_on_decision_bar`). Any other key with the same anomaly is rejected (`vwap_outside_range`).
- No realized-return claim anywhere (`semantics.realized_return_claim=false`).

## 5. Outcome separation (task item 4)

`annotate_outcome(case, later_observations, later_cutoff)` computes what became known after the case cutoff (next-session open reference, unadjusted close/max/min returns over ≤ 20 sessions). It returns a separate record with `annotation_kind="later_known_outcome"`, `not_a_label=true`, `realized_return_claim=false`; it is never merged into `labels` and `match_controls` rejects any record carrying `outcome_*/future_*/forward_*/realized_*/max_return*/min_return*/close_return*` fields (`outcome_leakage`). No past accumulation/entry label reads its future maximum or eventual profit; `failed_markup` uses only bars ≤ cutoff.

Prior state: `PriorState(symbol, decision_date, as_of, policy_hash, phase)` is accepted only if bound to this symbol and policy hash, earlier than the current cutoff, and **re-derivable** from the offered data at that earlier cutoff (`prior_state_inconsistent` otherwise). Repeated runs and truncations are deterministic (tests `test_state_isolation_and_repeatability`, invariance tests).

## 6. Reviewable case-library contract (task item 6)

- `episode_id = sha256(canonical{namespace, policy_hash, symbol, decision_date, input_fingerprint})[:32]`, `input_fingerprint = sha256(canonical list of consumed observations)`; a one-tick change in any consumed bar changes the id.
- Episodes (`build_episodes`): consecutive cutoffs of one symbol with the same phase; `start`, `end`, `sessions`, `open_at_last_cutoff`, `meets_min_sessions (≥3)`, `member_episode_ids`. Episodes of one symbol are disjoint by construction; positives of one symbol whose starts lie within the 20-session dependence window form one effective decision group (`effective_decision_dates`, calendar-approximate unless a session index is supplied).
- Matching (`match_controls`): controls must be `non_candidate`, a different symbol, the same liquidity band and the same broad regime (both must be known), and within ±10 sessions of the positive's cutoff using cutoff dates only; ranking is deterministic by (session distance, |ln amount ratio|, symbol, date); 3–5 controls; `unmatched=true` below 3; `rejected_pool_counts` enumerates why pool items were excluded; `control_reuse_counts` reports reuse and unmatched positives. Synthetic and real records never match each other.
- Counting: `effective_decision_dates` excludes synthetic episodes; `reviewed_positives=0` until reviews exist; target `min_reviewed_positives=50` with 3–5 controls each is the bar before a supervised result is more than exploratory — not a reason to tune thresholds or duplicate dates.
- Review: `ReviewRecord(reviewer_id, reviewer_kind ∈ {agent, human}, reviewed_at, verdict ∈ {positive, negative, ambiguous, failed, reject_data}, evidence_refs, notes)`. `attach_review` never mutates the input case; one reviewer → `single_review_not_independent`; two distinct reviewers agreeing → `independently_reviewed`; disagreeing → `disputed` with both verdicts preserved and `consensus_verdict=null`; `approved` stays `false` (user-level act). Rule agreement is not review: a `rule_engine` reviewer kind is rejected. Ambiguous, failed and invalidated episodes stay visible as their own phases/verdicts. Synthetic cases never count.

Two actual agents reviewing one case: each writes its own `ReviewRecord` with its own evidence refs; Codex and Claude records are appended in either order; disagreement is stored, not resolved by the generator.

## 7. Seed context and universe (task item 7)

`SZ002115 三维通信` and `SZ002081 金螳螂` come from `phase_replay.CORE_REPLAY_TARGETS`; both are **absent from the frozen 52-security pilot manifest** (`pilot_symbols.csv`, sha256 `97e251ae…`). They are retained as `legacy_unverified` seed context with `case_count_contribution=0`, `case_data_fabricated=false`, `reviewed=false`; no current case data is fabricated and no legacy "successful" label (`phase_replay.py:281-283` hard-codes a user-confirmed post-distribution label for SZ002081) is imported. New cases come only from the reviewed M2 corpus; `assert_in_universe` rejects any symbol outside the frozen set, and outputs mark `universe.in_frozen_universe`. Adding either seed symbol (or any other) to the research universe is a separate user/Codex decision.

## 8. Chronological protection (task item 8) — proposal, not adopted

| Role | Interval | Use |
| --- | --- | --- |
| development | 2023-09-04 … 2025-03-31 | rule/threshold work, case review |
| validation | 2025-04-01 … 2025-12-31 | out-of-sample check of adopted rules |
| final_holdout | 2026-01-01 … 2026-09-04 | never consumed for rule/threshold selection or target counting |

`split_role` classifies decision dates; `guard_final_holdout(records, purpose)` raises `final_holdout_consumed` for purposes `rule_selection`, `threshold_selection`, `target_count`, `parameter_search`. This is distinct from `offhour._chronological_signal_split` (70/30 by signal count, no holdout, `:5370-5378`, split at `:5376-5377`) and from walk-forward folds there. Real case extraction must not start before this split (or a Codex-revised one) is adopted.

## 9. Material choices requiring Codex review before adoption

1. Position window 250 instead of the legacy 120 for distribution/accumulation (aligns with warmup; changes the semantics of "high/low position").
2. `failed_markup` drawdown threshold −0.10 and the 20-session lookback.
3. Selection veto: `failed_markup` within the lookback disqualifies a candidate (not in any legacy rule).
4. Liquidity band thresholds 3e7/1e8/5e8 CNY (absolute, not quantile) and regime ±5% / ma60.
5. Lowest-plausible-threshold limit handling when ST status is unknown (blocks many main-board days ≥ 4.8%).
6. Strict-mode 72 h window after the close; retrospective mode as the only mode that can label the M2 corpus.
7. The proposed split intervals in §8.
8. `known_corporate_action_in_window` → indeterminate (no attempt at cash-forward adjustment inside labels).
9. Whether `many_suspensions_in_window > 10` and `long_gap > 20 calendar days` are the right gates for the 14 warmup-shortfall symbols and `SZ002731`'s ongoing suspension.

None of these numbers was compared against M2 prices; no raw price body or candidate table was read in this task.

## 10. Known limitations of this version

- Volume-ratio semantics inherited from the legacy rule (ratio to a trailing mean) make `markup` short-lived once the mean absorbs the high-volume days; a transition window of `indeterminate` between markup and failed_markup is expected and visible in the synthetic sequence.
- Calendar gaps are measured in calendar days (no trading calendar is injected); `effective_decision_dates` is exact only when a session index is supplied.
- Regime uses one benchmark; sector context is out of scope.
- `producer_sha256` changes with any edit to the module; `record_hash` therefore changes too — this is intended provenance, not instability.
- No performance, precision or return claim is made or possible in M3-01.
