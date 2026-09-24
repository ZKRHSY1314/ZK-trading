# Three-Year A-Share Research and Backtest Execution Goal

Status: `in_progress`  
Owner: Claude (implementation and evidence collection)  
Independent reviewer: Codex  
Product owner and permission authority: User  
Workspace: `D:\codex-A股交易`  
Created: 2026-09-04  

> Operational scratchpad only. Do not stage or commit this file.

## 1. Mission

Build a reproducible, leakage-resistant research system that uses approximately three years of A-share market history to:

1. identify candidate stocks exhibiting verifiable control-stock-like behavior, using 三维通信 only as an initial case study rather than as the definition;
2. distinguish evidence-backed phases such as accumulation, markup, distribution, and failure/abandonment;
3. evaluate entry, position management, stop-loss, exit, and risk-control rules;
4. learn chart, volume, liquidity, trend, and market-regime patterns without hindsight leakage;
5. preserve reviewed successes and failures in an auditable experience-memory loop; and
6. deliver a first credible three-year walk-forward backtest, followed by a maintainable paper-research workflow.

This is a research and review system. It does not promise profitability and must never enable live trading.

## 2. Meaning of “Done”

The first credible three-year research milestone is complete only when all of the following are true:

- The declared research interval is at least `2023-09-04` through `2026-09-04`, or an explicitly documented equivalent three-year interval.
- The selected research universe has measured coverage, with at least 95% of eligible symbol-sessions present or every material gap explicitly classified.
- Prices, adjustment mode, volume, amount, listing/delisting, suspensions, limit-up/limit-down sessions, and invalid dates pass documented quality checks.
- No duplicate decision snapshot can inflate sample or fold counts.
- Every training label has a written point-in-time definition and can be generated without using future information unavailable at the decision cutoff.
- Positive cases, matched negative controls, ambiguous cases, and failed cases are all represented.
- The backtest produces non-zero eligible signals and reports non-zero trades when the strategy is supposed to trade. Zero trades is a failed validation, not a successful backtest.
- Training, validation, and final test periods are separated chronologically. The final test period is not used for rule or parameter selection.
- Results include benchmark-relative return, precision/recall or ranking quality, turnover, costs, slippage assumptions, maximum drawdown, exposure, capacity/liquidity constraints, and failure cases.
- All reported sample sizes use effective independent decision days or folds, not duplicated rows.
- A clean checkout can reproduce the result from versioned code and an explicit data manifest.
- Only reviewed, provenance-carrying cases enter the experience-memory layer.
- Live trading remains disabled, and no broker login, account access, credentials, real orders, or real cancellations are introduced.

Passing software tests alone does not satisfy this definition.

## 3. Current Evidence Baseline

Record all later changes relative to this baseline instead of relying on chat summaries.

- Branch: `codex/control-plane-refactor`
- HEAD at audit: `73f266d`
- Batch A1 focused validation: `93 passed, 0 failed`
- Full backend validation in the current dirty workspace: `740 passed, 0 failed`
- The full-suite result is not yet an isolated A1 proof because the excluded A0 change in `backend/tests/conftest.py` was active.
- Production database migration has not been run.
- API and frontend listeners were not running at the Batch A1 checkpoint.
- Raw daily-bar table: 2,891,617 rows, including one known invalid `trade_date='ERROR'` row.
- Valid dated daily bars: 2,891,616 rows across 5,566 symbols.
- Observed valid date range: `2024-04-09` through `2026-09-04`; most symbols begin around `2024-06`, so the corpus is not yet three years.
- Forecast decisions: 20,082 rows.
- Forecast outcomes: 18,682 rows.
- Forecast evaluations: 746 legacy rows whose sample/fold counts require quarantine or explicit legacy treatment.
- Historical backtest runs exist, but observed trade and closed-trade counts are zero; they do not prove strategy performance.
- Strategy documents exist, but the observed experience-event and experience-review tables contain no operational learning history.

Re-query these values before using them. A baseline is evidence from one point in time, not a permanent truth.

## 4. Role and Handoff Contract

### Claude — implementation owner

- Continue safe, in-scope work without asking the user for minor implementation choices.
- Inspect current code and data evidence before changing anything.
- Make the smallest milestone-aligned change and run focused validation before broader validation.
- Maintain a progress ledger in Section 10 after each material checkpoint.
- Stop only at the mandatory gates in Section 6 or when a milestone is ready for independent review.
- Never declare independent review on Codex’s behalf.

### Codex — independent milestone reviewer

- Review the actual diff, current schema, reproducible commands, and data evidence.
- Treat Claude’s report as a claim to verify, not as proof.
- Classify findings as blocking, non-blocking, or future-scope.
- Mark a milestone `validated` only after its acceptance checks pass in the intended isolated state.

### User — product owner and permission authority

- Authorizes production data/database mutations, commits/pushes, scope changes, and any decision whose alternatives materially change the research result.
- Accepts validated milestones.

## 5. Continuous Execution Protocol

At the start of every Claude work session:

1. Read `AGENTS.md`, `CODEX_CLAUDE_COLLABORATION.md`, and this file in full.
2. Record branch, HEAD, `git status --short`, active processes/listeners relevant to the task, and pre-existing diffs in the files to be touched.
3. State the current milestone, write scope, read-only scope, data impact, and acceptance checks.
4. Resume from the first unchecked acceptance item. Do not restart completed work merely because the chat changed.

During a milestone:

- Continue diagnosing, editing allowed code/tests, and validating until the milestone is either ready for review or genuinely blocked.
- Resolve ordinary test failures, formatting issues, and small design details autonomously when they do not expand scope or mutate protected data.
- Prefer local fixtures, temporary databases, copied databases, and synthetic cases.
- Do not send a progress message for every command. Report only when a checkpoint materially changes status, evidence, risk, or the required user decision.
- If context is becoming long, update Section 10 before continuing so another session can resume from disk.
- Never convert an estimate, a passing test count, or a row count into a claim of strategy effectiveness.

At a milestone checkpoint, report exactly:

1. milestone and state (`in_progress`, `ready_for_review`, `validated`, or `blocked`);
2. files changed, with unrelated dirty files explicitly excluded;
3. commands, exit codes, pass/fail counts, and whether excluded workspace changes were active;
4. data read/write impact and before/after counts;
5. safety status (`review_only`, `simulation_only`, `live_trading_disabled`);
6. acceptance checks passed and failed;
7. remaining risks and rollback method; and
8. one concrete next action.

## 6. Mandatory Stop Gates

Stop and request the appropriate authorization or independent review before any of these actions:

- writing, deleting, deduplicating, migrating, or backfilling the production SQLite databases, datasets, or knowledge stores;
- replacing or reclassifying historical labels or cases;
- committing, pushing, opening a pull request, or changing the allowlist;
- staging or committing datasets, strategy sets, methodology materials, this Claude scratchpad, `AGENTS.md`, `CLAUDE.md`, `CODEX_CLAUDE_COLLABORATION.md`, or any Codex-/Claude-related test or helper file;
- changing the declared research universe, label meaning, target variable, chronological split, benchmark, cost model, or primary acceptance metric;
- enabling any real-account, credential, fund, broker-login, order-placement, or cancellation capability;
- modifying a file another agent appears to be changing without a handoff;
- relying on a network source whose provenance, adjustment mode, units, or time availability cannot be verified; or
- discovering evidence that materially invalidates the current milestone premise.

At a stop gate, continue all safe read-only or isolated-fixture work that does not depend on the pending decision. Do not stop merely because the task is difficult or lengthy.

## 7. Milestone Plan

### M0 — Batch A0/A1 evidence integrity closure

Goal: establish one trustworthy decision snapshot per scope and data vintage, with ownership fencing and explicit provenance.

Required work:

- Finish Batch A1 review of manual-by-default behavior, the only explicit scheduled worker, ownership loss, canonical snapshot selection, provenance persistence, policy-versioned evaluations, and atomic migration.
- Validate A0 network isolation separately.
- Prove A1 in a clean A1-only state, or commit/validate A0 first and then prove A1 on top of it.
- Keep production databases untouched until migration rehearsal and authorization.

Acceptance:

- Focused tests pass.
- Full backend tests pass in the exact state intended for commit.
- `git diff --check` passes.
- The strict allowlist contains no Batch B/C/D or excluded artifacts.
- A copied production database survives migration, preserves counts and constraints, and supports idempotent re-entry.
- The operational consequence of migrating the historical claim to `legacy_unknown` is documented: official confirmed evidence temporarily becomes empty until a new scheduled snapshot is finalized.

### M1 — Three-year data contract and read-only readiness audit

Goal: define exactly what data is needed before any backfill.

Deliverables:

- Universe definition with listing/delisting policy and survivorship-bias treatment.
- Target interval and expected trading-session calendar.
- Field contract for OHLC, volume, amount, adjustment mode, source, source timestamp, and availability timestamp.
- Symbol-level coverage matrix and gap taxonomy.
- Duplicate, invalid-date, impossible-price, non-monotonic-adjustment, unit, and stale-source checks.
- Source precedence and reconciliation rules, including Tonghuashun rate limits and failure behavior.
- Estimated backfill size, duration, retry policy, staging location, backup, rollback, and validation plan.

This milestone is read-only against production data.

### M2 — Authorized historical-data backfill and validation

Goal: create a validated three-year corpus without silently rewriting evidence.

Prerequisite: explicit user authorization after M1 review.

Acceptance:

- Backfill runs to a staging or copied database first.
- Before/after manifests, counts, hashes where practical, coverage, rejected rows, and source lineage are recorded.
- No `ERROR` pseudo-dates or duplicate `(symbol, trade_date, adjustment)` observations enter the research view.
- Corporate-action adjustment is consistent through the entire interval.
- Production promotion, if authorized, is atomic or recoverable and independently checked.

### M3 — Label specification and reviewed case library

Goal: translate the investment idea into labels that can be generated without hindsight.

Required label families:

- stock-selection candidate vs matched non-candidate;
- accumulation, markup, distribution, failed markup, and indeterminate phase;
- entry eligibility, invalidation/stop-loss event, exit event, and no-trade state;
- market-regime and liquidity context.

Rules:

- 三维通信 is a seed case, not the sole positive template.
- Every positive episode needs matched negative controls from the same period, liquidity band, and broad regime.
- Ambiguous cases remain ambiguous; do not force binary labels to improve metrics.
- Label rules, reviewer identity, cutoff, supporting evidence, and policy version are stored together.
- Begin with at least 50 independently reviewed positive episodes and three to five matched controls per positive before treating a supervised result as more than exploratory. If the evidence cannot support that target, report the limitation instead of fabricating balance.

### M4 — Backtest engine validity

Goal: prove that the simulator can express the intended strategy without future leakage or unrealistic fills.

Acceptance:

- Signals use only information available at the decision timestamp.
- Orders cannot fill before the next legally available execution point.
- Suspensions, price limits, commissions, transfer fees, stamp duty, slippage, lot size, liquidity, and rejected orders are represented.
- Position sizing, maximum exposure, stop-loss, exit, and cooldown behavior are deterministic and tested.
- Benchmarks and delisted securities do not create survivorship leakage.
- At least one deliberately simple baseline generates expected non-zero trades on a controlled fixture and on eligible historical data.

### M5 — Baseline research models

Goal: establish interpretable baselines before complex optimization.

Build and compare separately:

- a rule/ranking baseline for stock selection;
- a phase-classification baseline for accumulation/markup/distribution;
- entry/exit/stop-loss policies evaluated on fixed signals;
- chart/trend features evaluated with ablations;
- a trivial benchmark and a market/liquidity-matched benchmark.

Use chronological train/validation/test splits. Do not tune on the final test interval.

### M6 — Walk-forward validation and robustness

Goal: determine whether performance survives time, regime, costs, and reasonable perturbations.

Required evidence:

- walk-forward folds based on independent decision dates;
- performance by bull, bear, sideways, high-volatility, and low-liquidity regimes where sample size permits;
- effective sample count, confidence intervals or bootstrap uncertainty, and false-positive analysis;
- sensitivity to thresholds, costs, execution delay, and universe definition;
- comparison of successes and failures, not only aggregate return;
- explicit rejection criteria for a strategy that does not generalize.

### M7 — Auditable experience-memory loop

Goal: turn reviewed outcomes into reusable knowledge without poisoning future evaluation.

Acceptance:

- Only validated cases with provenance and policy versions enter official memory.
- Exploratory/legacy cases are visibly separated.
- Positive, negative, ambiguous, and invalidated lessons are all retained.
- A memory update cannot change historical backtest results silently.
- Re-running the same evidence is idempotent.

### M8 — Paper research operation

Goal: run the research loop safely over new market days.

Acceptance:

- Monitoring is read-only or simulation-only.
- One official scheduled snapshot is produced per eligible vintage.
- Failure states are explicit and never reported as successful empty runs.
- Drift, missing data, source failure, and confidence degradation trigger review-only behavior.
- No real trading capability is enabled.

## 8. Measurement Framework

Do not optimize a single return number. At minimum report:

- selection precision at K and recall against reviewed cases;
- rank IC with independent date-level folds;
- phase classification precision, recall, confusion matrix, and transition consistency;
- total and benchmark-relative return;
- annualized volatility, maximum drawdown, downside deviation, and exposure;
- trade count, win rate, payoff ratio, turnover, holding period, and cost drag;
- false-positive concentration by sector, regime, liquidity, and listing age;
- data coverage and evidence-quality split (`confirmed` vs `inferred`/`exploratory`);
- stability across chronological folds and parameter perturbations.

All metrics must state sample count, independent fold count, interval, universe, cost assumptions, and policy/model/data versions.

## 9. Git and Data Hygiene

- Never use `git add .` or broad staging.
- Build an explicit allowlist for each commit and show it before staging.
- Never stage databases, raw/generated datasets, caches, logs, `.venv`, `node_modules`, `frontend/dist`, `.codegraph`, strategy sets, methodology documents, Claude/Codex collaboration files, or Claude-/Codex-related tests and helpers.
- Preserve all unrelated dirty changes.
- Use a temporary database or verified copy for migration and backfill rehearsals.
- Do not start services or long-running write loops as part of a review checkpoint.
- Keep live trading disabled and prove it in tests whenever the affected path could influence execution.

## 10. Progress Ledger

Append one concise entry at every milestone checkpoint. Do not rewrite earlier entries except to correct a factual error, and mark corrections explicitly.

### 2026-09-04 — Batch A1 closure candidate

- State: `ready_for_clean_isolation_validation`
- Reported by Claude: 93 focused tests and 740 full backend tests passed.
- Independently reproduced by Codex in the current dirty workspace: 93 focused tests and 740 full backend tests passed.
- Verified closure changes: `_run_decision_snapshot()` defaults to `manual`; the scheduled worker passes `run_kind="scheduled"`; an end-to-end `label_due()` test writes and reloads confirmed/inferred provenance; stale comments were corrected.
- Remaining gate: prove the full suite in the exact A0/A1 commit state, because the excluded `backend/tests/conftest.py` A0 change was active during the dirty-workspace full run.
- Production impact: none; no migration, service start, commit, or push performed.
- Next action: isolate and validate A0, then validate the exact A1 allowlist on top of the accepted A0 baseline. Stop for Codex review before staging or any production migration.

### 2026-09-04 — M0 clean-isolation validation and migration rehearsal

- Milestone: M0. State: `ready_for_review`.
- Baseline at start: branch `codex/control-plane-refactor`, HEAD `73f266d`, 36 dirty files, no API/frontend/worker listeners (only the Tonghuashun client on 17180). The dirty workspace was not disturbed at any point.
- Isolation method: `git worktree add --detach` at `73f266d`, then patches applied in order. A0 = `backend/tests/conftest.py` alone (network-isolation fixture only; it contains nothing else).
- Isolated results, all in the worktree using the project venv:
  - HEAD, no patches: `639 passed, 0 failed` (113s).
  - A0 only: `639 passed, 0 failed` (104s). A0 adds no tests; it removes real network calls, which is where the ~9s and the historical flakiness came from.
  - A0 + A1 focused: `93 passed, 0 failed`.
  - A0 + A1 full: `691 passed, 0 failed`. `git diff --check` clean.
- Test-count reconciliation, 740 (dirty) vs 691 (isolated). The 49-test gap is entirely excluded files, confirmed by diffing collected test ids, not by inference: `test_codex_decision_review.py` 28, `test_tonghuasun_preflight.py` 12, `test_codex_market_pulse.py` 8, `test_tonghuasun_startup_script.py` 1, `test_market_history_refresh_loop.py` 1. 691 + 49 = 740.
- The isolated set is a strict subset of the dirty set apart from one parametrized case id in `test_tonghuasun_startup_script.py` (a Batch D file): the HEAD form of that case runs and passes under A0+A1, so A1 does not break it.
- No A1 file imports an excluded artifact. The only textual match, `service.py:528`, is the string literal `"codex_market_pulse.v1"` used as a default `prompt_version`.
- Migration rehearsal on a consistent copy (sqlite3 backup API; production opened read-only only): 1,284 MB copy. All five table counts preserved exactly (decisions 20,082; outcomes 18,682; evaluations 746; claims 1; daily bars 2,891,617). `run_kind` added; the historical claim became `legacy_unknown`, not `scheduled`. No stranded `__migrated` table. CHECK enforced on an upgraded database, and `run_kind` cannot be omitted. Second `init()` left counts, claims and schema unchanged. `forecast_evaluations.canonical_policy_version` added, all 746 legacy rows NULL.
- Canonical-evidence consequence, measured rather than predicted: after migration the copy yields `{"inferred": 29}` and zero `confirmed`; stock canonical snapshots fall 6 to 5. Official confirmed evidence is empty until a new scheduled snapshot is finalized, exactly as documented in M0 acceptance.
- Production impact: none. Counts unchanged, `run_kind` absent from production, HEAD unchanged, nothing staged, committed, pushed, started, or migrated.
- Next action: Codex validates M0 against the isolated worktree evidence. On validation, proceed to M1 read-only three-year readiness audit.

### 2026-09-04 — Codex independent M0 review

- State: `changes_requested`.
- Evidence accepted: Codex independently reproduced `93 passed` for the focused A1 suite and `691 passed` for the exact isolated A0+A1 full suite. The 16 isolated files match the current candidate. The migration rehearsal database passes SQLite quick/integrity checks, preserves all five required table counts, migrates the historical claim to `legacy_unknown`, leaves all 746 old evaluation policy versions NULL, and yields 29 inferred / 0 confirmed canonical snapshots with 5 stock vintages. Production remains unmigrated and unchanged; nothing is staged, committed, pushed, or running.
- Blocking issue 1 — calibration provenance fails open: `ForecastCalibrationService.persist()` currently treats a missing `evidence_quality` as `official`, and `_record_snapshot()` stamps `CANONICAL_POLICY_VERSION` even when the supplied metrics contain no policy provenance. Missing, unknown, or mismatched provenance must never create a proposal and must never be relabelled as evidence produced by the current policy. Require exact `evidence_quality == "official"` and an explicit policy version matching `CANONICAL_POLICY_VERSION` for proposal eligibility. Persist the verified supplied version; preserve missing provenance as NULL/unknown or reject it explicitly. Add regression tests for missing and mismatched versions.
- Blocking issue 2 — the advertised ownership-loss status is not exercised: `test_a_writer_that_loses_ownership_mid_run_reports_ownership_lost` inserts an already-finalized successor before the attempted run, so it returns `already_recorded` and never reaches either `ownership_lost` branch. Add a genuine race/fault-injection test in which writer A claims and begins writing, writer B takes ownership before A's periodic recheck or finalize, and A returns `ownership_lost` with the correct `orphaned_row_count` while B's claim remains unchanged.
- Blocking issue 3 — idempotent scheduled repeats report false degradation: `_normalize_status("already_recorded")` currently returns `partial`, contradicting the service contract that an already-recorded vintage is a successful no-op. Normalize `already_recorded` to `completed` and test the outer decision step and overall rollup, not only the inner ledger payload.
- Non-blocking hardening: the HTTP endpoint accepts a caller-supplied `run_kind="scheduled"`; therefore the worker is only the sole scheduled writer by repository convention, not by an enforced trust boundary. Document the local trusted-caller assumption now and place authentication or a separate internal scheduler path before any non-local exposure. In A0, prefer `raising=True` for the two real Akshare methods so an interface rename cannot silently reopen network access.
- Reporting correction: the net 49-test difference is 50 dirty-only collected IDs minus one isolated-only parametrized ID, not five excluded groups whose raw counts directly sum to 49.
- Required next action: address the three blocking issues in the isolated A0+A1 scope, update tests, rerun focused and exact isolated full validation, and stop again at `ready_for_review`. Do not stage, commit, push, start services, migrate production, or begin M1 until Codex marks M0 `validated`.

### 2026-09-04 — M0 closure pass 2 (Claude): three blocking issues resolved

- State: `ready_for_review`. Nothing staged, committed, pushed, started, or migrated. Production database untouched.
- Blocking 1 — calibration provenance now fails closed. `persist()` requires exactly `evidence_quality == "official"` **and** `canonical_policy_version == CANONICAL_POLICY_VERSION` before a proposal is eligible. `_record_snapshot()` persists the *supplied* version and stores NULL when none was supplied, so a pre-policy result stays identifiable instead of being relabelled as current-policy evidence. 5 regression tests added (missing version, mismatched version, exploratory-with-matching-version, no-provenance relabelling, fully-attributed positive control). `tests/test_forecast_calibration.py`: 3 → 8 tests.
- Blocking 2 — the ownership-loss status is now genuinely exercised. The old test was renamed to `test_a_vintage_already_finalized_by_a_successor_reports_already_recorded`, which is what it actually proved. Two real fault-injection tests replace it: writer B takes the vintage by UPDATE of the claim row partway through A's writing, injected via a `ForecastLedger` subclass counting `record_forecast` calls. One covers the **periodic recheck** branch (15 candidates, takeover after 50 rows, A stops at the candidate-11 recheck with `orphaned_row_count == 50`); one covers the **finalize** branch (1 candidate, takeover on the last row, `orphaned_row_count == 5`). Both assert B's claim is unchanged and A published nothing. A 1-candidate fixture can never reach the recheck, since `OWNERSHIP_RECHECK_EVERY = 10` — which is why the branch had gone untested.
- Blocking 3 — the root cause was larger than the status mapping. `_run_decision_step` derived its status from `result["status"]`, which is the **selection's** status and is `"completed"` whenever a list was produced. The ledger status never reached the step or the rollup at all, so `already_recorded` and `preview_not_recorded` were unreachable in `_normalize_status`, **and `ownership_lost` reported `completed` end to end** — a run that published nothing looked identical to one that published. Fixed by making the step the worse of the selection status and the ledger status, reusing the existing `_rollup_status` severity order rather than adding a second ordering. `already_recorded` / `preview_not_recorded` → `completed`; `ownership_lost` / `empty` → `partial`. 3 tests added at the outer step and rollup level.
- Non-blocking hardening applied: A0 conftest now uses `raising=True` for both real Akshare methods, so an interface rename fails loudly instead of silently restoring live network access. The caller-supplied `run_kind="scheduled"` trust boundary is documented at `router.py` — the only thing preventing an arbitrary caller from consuming the official claim is that `run_stack.ps1` binds uvicorn to `127.0.0.1`; that is a deployment property, not an API guarantee, and needs real authorization before any non-local exposure.
- Validation. Focused suite (9 files): **119 passed**, 45s. Exact isolated A0+A1 full suite in the clean worktree: **701 passed**, 132s (was 691; +10 = 5 calibration + 5 control-plane). Dirty workspace full suite: **750 passed**, 137s. `git diff --check -- backend/`: clean.
- Correction to my own earlier isolation run: my worktree sync list was too broad. `backend/tests/test_market_history_refresh_loop.py` is Batch C (+86 lines asserting `effective_sources`, which does not exist at HEAD), not A0/A1. Copying it in produced one failure that was an artifact of my sync, not of the A1 code. The file was restored to HEAD and the isolated worktree now contains exactly the A0/A1 allowlist: 13 modified + 3 new files.
- Codex's reporting correction is confirmed against the corrected worktree. The delta is 50 dirty-only collected IDs minus 1 isolated-only ID = 49. Dirty-only by file: `test_codex_decision_review.py` 28, `test_tonghuasun_preflight.py` 12, `test_codex_market_pulse.py` 8, `test_market_history_refresh_loop.py` 1, `test_tonghuasun_startup_script.py` 1. The isolated-only ID is that same startup-script test under its HEAD parameter name (`akshare_first` vs Batch C's `tonghuasun_first`), which is why it nets to 49 rather than 50. Every excluded ID is Batch C/D or Codex-review scaffolding; none is A0/A1.
- Rollback: all changes are unstaged working-tree edits to the files listed above. `git checkout -- <path>` per file reverts any one of them; the three new files (`app/forecasting/canonical.py`, `tests/test_canonical_snapshot.py`, `tests/test_decision_day_migration.py`) are untracked and can simply be deleted. No migration has run against production, so there is nothing to roll back in the database.
- Awaiting Codex. Not starting M1, not staging, not committing, not migrating production.


### 2026-09-05 — Codex M0 technical validation

- State: `validated` for the current A0+A1 candidate; product acceptance and deployment are separate. All three previous blocking findings are closed. No new blocking finding was identified in this review.
- Calibration now requires explicit official quality and a matching supplied policy version before proposing changes. Persisted versions come from the input; missing versions remain NULL. The tests cover rejected unknown/mismatched provenance and a legitimate positive control.
- Both ownership-loss paths now run under actual database claim changes during forecast insertion: periodic recheck after 50 rows and failed finalize after 5 rows. Each test verifies the orphan count and the surviving owner's claim.
- Status now incorporates both selection and ledger results. Ownership loss propagates as partial; successful idempotent repeats and manual previews complete normally. Correction to Codex's earlier diagnosis: normalization alone was insufficient because the old step never consumed the ledger status. Claude correctly repaired that propagation too.
- Independent commands executed from the isolated worktree's backend directory using the project venv: the seven A1 test files previously reviewed passed with **103 passed, 1 warning in 34.62s**, exit 0; the default full suite passed with **701 passed, 1 warning in 125.78s**, exit 0. Claude's reported 119 focused tests used nine files; these are different command scopes, not a discrepancy in the seven-file result. The 750 dirty-workspace run was not repeated in this review. The warning is the existing Starlette/httpx deprecation.
- Isolation: exactly 16 changed/new paths (A0: one; A1: fifteen), all matching current workspace contents after newline normalization. The Batch C history-loop test is absent from the patch. `git diff --check` passed. Existing default pytest collection exclusions remain in effect; 701 is the default suite, not every legacy opt-in test.
- Read-only database checks: production counts remain 20,082 decisions / 18,682 outcomes / 746 evaluations / 1 claim / 2,891,617 daily-bar rows. Production has neither new column. The existing migration rehearsal copy passes `quick_check`, preserves these counts, retains 746 NULL evaluation-policy versions, and yields 29 inferred / 0 confirmed snapshots. No schema migration code changed in this closure pass; the prior migration rehearsal and rollback/idempotence tests remain applicable.
- HEAD remains `73f266d`; staging is empty; API/frontend ports 8000/3000 are not listening. Review made no production data changes, commits, pushes, or service starts.
- Operational limits remain: scheduled is a trusted local caller convention, not authenticated scheduler identity; manual preview protects official forecast recording and is not a promise that the entire full-profile endpoint is read-only. A2 must still filter legacy/unknown/exploratory evaluations before an official scoreboard or automatic calibration consumer relies on persisted history. Zero confirmed evidence after migration must display as insufficient evidence, not a successful performance result.
- Correction to the preceding Claude rollback paragraph: do not use file-wide `git checkout --` or delete untracked files as a generic rollback in this shared dirty workspace. Preserve the candidate and unrelated user edits; reverse only a reviewed task-specific patch, or later revert its dedicated commit after checking overlapping work. The earlier rollback recipe is superseded by this correction.
- Next action: Claude proceeds to M1 below. M0 technical validation does not authorize production migration, bulk backfill, commits, pushes, or service startup.

### 2026-09-05 — M1 read-only three-year data readiness audit (Claude)

- State: `ready_for_review`. Read-only throughout: every connection opened `file:...?mode=ro`; no `SQLiteStore.init()`, no service constructor, no migration, no provider call, no download, no service start, nothing staged/committed/pushed. Production databases unchanged. A0/A1 candidate and its isolated worktree preserved (16 files, worktree HEAD `73f266d`).
- Deliverable: `claude methods/M1_THREE_YEAR_DATA_READINESS.md` (88 KB, 11 sections + appendices), backed by 361 evidence artifacts under `claude methods/_m1_evidence/`, plus my own independent cross-check at `_m1_evidence/claude_independent_crosscheck.md`.
- Method: 9 independent read-only audit dimensions, each of whose material findings was handed to adversarial verifiers required to re-derive the number with their own query rather than re-run the original SQL. Where a verifier adjusted or refuted a claim, the report uses the corrected value and says so.

**Headline: the three-year window is BLOCKED, and the cause is "never collected", not "collected then lost".**

- Both bar stores begin at `2024-04-09`. `2023-09-04..2024-04-08` holds **0 rows** in both; the pre-window warm-up region holds **0 rows**. Independently reconfirmed on the main line.
- `2024-04-09` is a single-stock floor — the first session carrying >=4,000 stocks is **`2024-06-24`**. The honest research window is **`2024-06-24..2026-09-03`, 536 sessions, ~2.2 years**, of which 396 days remain labelable after a 120-day feature warm-up and the unmaturable 20-day tail.
- Coverage denominator corrected twice. The earlier 91.3% used the data's own 587-session footprint as denominator — circular. The audit then estimated a ~733-session window; the completeness critique found the denominator never needed estimating (see below). **Measured against the real 728-session window: best symbol 538/728 = 73.90%, median 536/728 = 73.63%, and zero symbols reach 80%.**
- **Survivorship is UNRESOLVED and no full-market completeness percentage is reported.** `instruments.delist_date` is non-null for **0** of 5,561 rows; `universe_snapshots` covers only 7 dates, all on/after 2026-07-14; not one of 5,566 securities has a price series terminating before 2026. Delisting evidence does not exist, rather than being sparse.
- **The two stores are one source, not two.** All 100 `market_history.ingest_runs` carry provider `trading_local.daily_bar_cache`, and `daily_bars` is 100% `qfq`. Cross-store agreement is therefore not cross-validation — a point that matters because they substantially disagree (below).

Additional blocking findings, all adversarially verified:

- Cross-store `close` disagrees on **38.01%** of common keys with both sides marked `qfq`, and the ratio drifts with date, so no single re-basing factor explains it. (Reproduced independently: 1,059,744 / 2,787,736. A minor denominator nuance versus the report's 2,787,696 is documented in my cross-check file so a re-derivation of 7.43% instead of 7.46% is not read as a contradiction.)
- Source splicing: **2,096 of 5,865** measurable source-change boundaries (35.7%) show a >0.5% price-level shift. The decisive control is cross-store return agreement — 43.9% divergence at boundaries versus 0.8% on same-day controls.
- `available_at` is an ingest clock, not an availability time: `available_at <> fetched_at` returns **0 rows** across only 4 collection days, and strict PIT filtering at `as_of=2026-06-30` returns **0 rows**. Current-vintage qfq is therefore not point-in-time history.

**One accusation was withdrawn under adversarial review, and is recorded as such.** The claim that 74.7% of recorded decisions referenced bars not yet existing at their cutoff was **REFUTED**: the control group scores 74.71% and a true look-ahead probe returned 0 of 3,900. The real, narrower problem that survives is that `daily_bar_cache` carries no point-in-time column, so historical decisions cannot be replayed.

**The existing research record is void, which reinforces rather than reopens M0.**

- 39 of 39 `historical_backtest_runs` produced zero trades with `final_cash == initial_cash`, and every run was created 2026-06-12..2026-06-29 — **before** the earliest surviving bar's `created_at` of 2026-06-30 04:55:30. They cannot be reproduced from today's data. Confirmed independently.
- The 746 legacy evaluations report 3,630 samples / 121 folds where the canonical truth is 150 / 5 — **24.2x inflation** — and confirmed-canonical evidence is **0**. A2 remains an explicit prerequisite before any official scoreboard or automatic calibration consumer reads persisted history, and zero confirmed evidence must display as insufficient evidence, never as a successful result. No legacy row was read-modified, relabelled or deleted.
- Acceptance baselines for M2 were measured and independently reconfirmed: V1 OHLC violations = 3, V2 illegal `trade_date` = 1 (the known `ERROR` pseudo-date), V3 illegal symbols = 482 rows across 4 spellings, and an untouched 2025 control slice of 1,307,976 rows / close_sum 30336732.878.
- Recommended M2: a single-source, single-vintage full-window rebuild into a **staging** database (never in-place), because re-pulling the whole window costs the same wall clock as filling only the head gap (one request per symbol) while also resolving the splice and adjustment-vintage problems. Estimated 5,561 requests / ~4.08M rows / 2.0-3.4 h / ~2.9 GiB against 600 GiB free. Rate assumptions are graded: Sina 0.45-0.79 symbols/s is our own measured log, vendor quota unverified; Tonghuashun 1.0 s/request is our own client-side throttle, vendor limit unverified; the Eastmoney path is measured unavailable (1 success in 32 runs). BJ legacy-code history and delisting registers cannot be estimated from local data and need separate authorization.
**The completeness critique found five blocking gaps in the audit's own work. All five were reconfirmed by me with independent read-only queries, and the report and acceptance suite were corrected before this entry.**

- **C-1 The trading calendar never needed estimating.** `backend/.venv/Lib/site-packages/akshare/file_fold/calendar.json` ships 8,797 sessions (1990-12-19..2026-12-31), and `backend/app/data/trading_calendar.py:61` already consumes the same source. Measured: window = **728** sessions (audit estimated ~733), head gap = **141** (est. ~146), full-market gap = **191** (est. ~196). Segments B/C and calendar-2025 match the audit exactly (50 / 536 / 243), which is what confirms the calendar is the right one. Consequences: coverage becomes 73.90% / 73.63%; G-A backfill becomes 5,167 x 141 = **728,547 rows**, not 754,382 (3.5% overstated); open question U1 is closed, not deferred.
- **C-2 Unit contamination is in the pricing store too, and the audit's test structurally could not see it.** A18 was scoped to frozen `market_history` tencent rows; its test required `cache.amount` to exist, but **100% of tencent cache rows have `amount IS NULL`**, so the contaminated population was excluded by construction. Measured inside `daily_bar_cache`: of 6,243 source-change boundaries, **555 show a 20-500x volume drop and 293 are near 100x**, against only **19** near-100x steps in 2,878,584 non-boundary pairs; 291 of 293 move close by <=11% (mean ratio 1.0061), so it is a 股/手 unit switch, not a corporate action. Suspect population: **306,543 rows / 4,946 symbols, all `amount IS NULL`** - exactly the rows that reach `execution.py`'s `volume x SHARES_PER_HAND x price` liquidity proxy. **The bias is optimistic**: the backtest fills orders reality could not. A18 is reclassified to "both stores, pricing store included", and G-D' (163,174-row UPDATE) is not the whole fix.
- **C-3 The acceptance gate was unreachable.** G1/G2 targeted "~146 sessions/symbol" and "~733"; a perfect backfill can only reach 141/728, so a correct result would have been rejected. Literals corrected to the measured values with a note that they are measured, not estimated.
- **C-4 The V-series acceptance items existed only in report prose.** `backfill_acceptance.sql` held only G1-G5 and N1-N10, and the frozen BEFORE snapshot only A1-A9. The A18 gate, OHLC gate, ERROR-row gate, bare-symbol gate and vintage-preservation gate had no executable query and no baseline, so nothing could be proven after promotion. Added V1, V2, V3, V5, **V5b (the new pricing-store unit gate from C-2)**, V5c and V7.
- **C-5 The A2 filter is not executable on the schema that exists.** Production `forecast_evaluations` has none of `canonical_policy_version`, `run_kind`, `evidence_quality`, and all 746 `metrics_json` blobs carry only {horizon_days, metrics, scope}. So the report's "all 746 policy versions are NULL" described a column that does not exist; the accurate statement is "the column is absent because production is deliberately unmigrated", consistent with M0. **A2 must therefore explicitly include a schema migration**, and since the 746 rows carry no key to `forecast_decisions`, evaluation-level lineage checks are impossible on the current schema - the audit's orphan check covered `forecast_outcomes` only.

- **C-6 The audit understated its own best remediation evidence.** Diffing `universe_members` between consecutive snapshot dates recovers **5** removal events (2026-07-15->16: SH605081, SZ000004, SZ002808; 16->17: SZ002898; 07-19->09-03: BJ920305), not the 2 the report claimed. All five `status='inactive'` instruments are recoverable this way. Survivorship stays UNRESOLVED - 7 snapshot dates cover only the last 53 days of the window - but snapshot diffing is a validated, already-working delisting-register path and should be stated as such.
- **C-7 The contract's headline deliverable encoded the circular denominator the report criticises.** `coverage_manifest.csv` carried `eligible_sessions = 587` (the data's own footprint) while labelling it `eligibility_basis='listing_interval'`, and Section 11.1 tells Codex to read that file first - so a reviewer would have been handed the 0.913 artefact while the prose argued 0.736. **Regenerated** against the measured calendar, BOM removed, with the footprint ratio kept as a separately labelled column and a nominal-window column added. Result: 5,543 of 5,567 securities have a computable denominator, median **0.7363**, mean 0.7485. Critical caveat now stated in the file: the 247 symbols at >=0.99 are **all** listed after 2024-06-20 with a median eligible window of just 248 sessions - an IPO artefact, not historical depth. **For the 5,167 listed on or before the window start: max 0.7390, and not one reaches 0.95.**

- Audit cost and honesty note: 47 agents, 3.98M subagent tokens. The completeness critic died on a session usage limit in the first run and was re-run on resume. Its findings materially corrected the audit, which is the reason the pass exists; the corrected numbers above are the ones I stand behind, and each was re-derived on the main line rather than accepted from the agent. The audit's own numbers were spot-checked by me on the main line rather than taken on trust.
- Not started: M2, any backfill, any production migration, any commit/push, any service start.


### 2026-09-06 — Codex independent M1 review

- State: `ready_for_review` candidate returned for a bounded closure pass; **M1 is not yet `validated`**. M0 remains validated. M2 remains unauthorized.
- Independent read-only verification supports the core diagnosis: local-calendar window 728 sessions, missing head 141 sessions, zero pre-window warm-up, coverage median 73.6264%, and no pre-window-listed security at 95%. Both stores begin 2024-04-09; 39 old runs have no trade rows. Production main/WAL size and mtime are unchanged through this review.
- Four closure requirements: R1 version-aware temporal availability (do not backdate revised qfq content); R2 reconcile the calendar coverage manifest with the still-spine-based gap table (5,286 denominator disagreements); R3 implement complete, fail-closed acceptance gates and frozen baselines; R4 consolidate the staged pilot/rebuild/promotion proposal, including benchmark, warm-up and preservation boundaries.
- Concrete gate probes: the delivered date/symbol queries report zero violations for an impossible date and unsupported exchange; the source-boundary unit gate reports zero on a single-source wrong-unit fixture. The frozen BEFORE JSON still contains only A1-A9.
- Evidence and full English instructions: `claude methods/M1_CODEX_REVIEW.md`, with `claude methods/_m1_codex_review/review_m1.py` and `observed_results.jsonl`. Corrected independent query pass and in-memory gate probes exited 0. No runtime code changed and no backend regression suite rerun.
- Next action: Claude completes R1-R4 using the existing evidence, then stops for review. Do not restart the broad audit, begin M2, migrate data, start services, commit, or push. Section 12 is the current handoff.

### 2026-09-06 — M1 bounded closure (Claude), responding to the Codex M1 review

- State: `ready_for_review`. Read-only throughout. No runtime code, dataset, methodology, knowledge store, production database, or M0 candidate was touched; no network/plugin call, download, migration, service start, commit or push. New files live only under `claude methods/_m1_closure/` plus `claude methods/M1_CLOSURE.md`.
- Deliverable: `claude methods/M1_CLOSURE.md`, backed by five runnable artifacts in `_m1_closure/`. **The superseded execution path was removed, not annotated**: `backfill_acceptance.sql`, `backfill_acceptance_BEFORE.json`, `coverage_05_manifest.py`, `coverage_manifest.csv` and `coverage_gap_shape.csv` are renamed `*.SUPERSEDED.*`, and `M1_THREE_YEAR_DATA_READINESS.md` now opens with a banner marking it historical. Codex was right that a corrections preamble does not make conflicting execution instructions safe.

| Req | Artifact | Result |
|---|---|---|
| R1 temporal contract | `_m1_closure/temporal_contract.py` | 6/6 proofs, exit 0 |
| R2 coverage reconciliation | `_m1_closure/coverage_gap_generator.py` | identity holds for all computable securities, exit 0 |
| R3 acceptance gates | `_m1_closure/acceptance_runner.py` + `test_acceptance_gates.py` | 22/22 synthetic cases, exit 0 |
| R4 M2 proposal | `M1_CLOSURE.md` section 5 + `_m1_closure/pilot_selection.py` | 50 stocks + 2 benchmarks, deterministic, exit 0 |

- **R1.** Five times are now separate (event, assumed publication, observed availability, ingestion, factor vintage) and `assumed_publication` is never consulted by strict admission — that was the T1/T2 hole. Proof P3 is the sharp one: forging the availability stamp back to 2024, exactly what T1 produced, still fails on `factor_vintage_after_cutoff`. Unknown stays unknown and fails closed; exploratory admission is allowed but returns a label saying it is reproducibility, not point-in-time validity. Measured consequence: **0 production rows can satisfy strict PIT** (`available_at <> fetched_at` is 0 rows across 4 collection days; no `factor_vintage` column exists). That is a property of the evidence, not a defect, and it cannot be repaired by backfill — only future collection can carry it.
- **R2.** One pinned calendar (sha256 `f1f1ce33...`) and one listing-interval definition now feed a single generator that emits manifest and gap shape as projections of the same record, asserting `observed + leading + interior + trailing == eligible` before writing. The 5,286 disagreements are gone; BJ920000 reconciles at 728 = 501 + 227 + 0 + 0, where the old gap table showed 587 and silently dropped the 141-session head gap. Totals: 5,567 securities, 5,542 computable, 24 unknown list_date, 1 eligible-but-unobserved, 0 off-calendar rows; eligible 3,900,763 = observed 2,888,185 + leading 1,004,942 + interior 4,611 + trailing 3,025. Headline coverage on the only meaningful population (5,167 listed on/before window start): max 0.7390, median 0.7363, **none reaches 0.95**. Gap causes stay `unknown` — no suspension or delist calendar exists, so naming a cause would be fabrication.
- **R3.** Gates are now three-valued and UNKNOWN never counts as PASS, which was the old suite's failure mode: checks structurally incapable of finding a problem reported "0 violations", indistinguishable from clean. Each gate Codex broke now rejects the input that fooled it — `2025-02-30` (real-date + session validation, not shape), `XX123456` (namespace + instruments reference), a same-source deliberately-wrong unit **with no provider boundary present**, an edited archive value with unchanged row count (content fingerprint, not row count), and a non-null dangling `ingest_run_id`. Six clean controls prove the gates are not merely always-FAIL. Production baseline: D1 FAIL 1, D2 FAIL 6, D3 FAIL 4, D4 UNKNOWN (whole population quarantined), D5 PASS, D6 UNKNOWN (baseline recorded).
- **R4.** Contract and harness precede ingestion; all writes stay staging-only after authorization. Pilot: 50 stocks + `SH000300`/`SH000001`, stratified so it can fail (20 ordinary control, 10 suspected unit switch, 8 in-window IPO, 7 BJ code-history, 5 largest interior gap). Research interval unchanged at 2023-09-04..2026-09-04; maximum feature lookback stated **separately** as a planning option — 250 preceding sessions anchors at **2022-08-24**, matching Codex. Rate and one-request-per-symbol remain **assumptions the pilot exists to measure**, not commitments. Original vintages are preserved read-only with a D6 fingerprint and are **not repaired in place first**; staged rebuilds are labelled intentional with a declared rewrite list. Gates B/C/D (pilot, full rebuild, production promotion) are separately authorized, and promotion is designed as a recoverable two-phase operation because two renames across two files are not one atomic transaction.

**Corrections to my own earlier claims, all accepted from the Codex review:**

- **I retract the claim that the runtime already consumes `calendar.json`.** `ak.tool_trade_date_hist_sina()` performs `requests.get("https://finance.sina.com.cn/realstock/company/klc_td_sh.txt")`; offline, `trading_calendar.py` falls back to `weekday_fallback`. The file is an offline audit reference only, and which calendar any historical runtime used remains UNKNOWN. Recorded in the generator and in `_meta.json` as `calendar_is_runtime_source: false`.
- **I narrowed the unit-contamination scope, which I had overstated.** Measured: all **293** near-100x events are `SH688xxx` (STAR board), every one a tencent to sina transition, **218 of them on 2024-08-13**. I had presented the 306,543-row / 4,946-symbol tencent population as the contaminated scope; that is an upper bound of what is *unverifiable*, not what is *wrong*. D4 quarantines it and rescales nothing. A STAR-board lot convention is a hypothesis for the pilot, not a finding.
- **My 7.43%/7.46% explanation was wrong.** There are no NULL cache closes among the common keys; the 40-key difference is the quality/adjustment filter. The denominator must be named explicitly rather than explained away.
- Snapshot removals evidence observed membership changes, not certified delist dates. The old leakage probe is `unsupported by this probe`, not a clean bill of health. Zero-trade runs are not performance evidence, but timestamp order alone does not prove their numbers are irreproducible; those records stay untouched.

- Reproduction (in `claude methods/_m1_closure/`, project venv): `coverage_gap_generator.py`, `temporal_contract.py`, `acceptance_runner.py`, `test_acceptance_gates.py`, `pilot_selection.py` — all exit 0.
- Remaining limitations: strict-PIT admissible rows are 0 and unfixable retroactively; historical universe / ST / suspension / delist / BJ code mapping all UNKNOWN so survivorship stays unquantifiable; the 38.01% cross-store close disagreement has no arbiter because both stores share one source; the STAR-board unit hypothesis is unverified; no backend regression suite was rerun because no runtime code changed.
- Not done and not authorized: M2 pilot download, full rebuild, production promotion, A2, commits, pushes, service start.


### 2026-09-06 — Codex independent review of the M1 closure

- Verdict: **do not start M2 downloads yet**. M1 is not yet technically validated as a complete execution handoff. M0 remains validated.
- Passed independently: six supplied temporal proofs; all 22 supplied synthetic cases; exact reproduction of every reconciled coverage CSV cell and total; exact reproduction of the 50 unique pilot-stock records and 20/10/8/7/5 quotas, plus two declared benchmarks. R2's original denominator disagreement is closed for the pinned inputs and must not be re-audited.
- Remaining targeted blockers: F1 strict admission accepts blank provenance and a later instant expressed in another timezone; F2 NULL units and empty/duplicate populations can pass individual quality checks; F3 the archive fingerprint omits open/high/low/provenance and the documented entry point cannot validate supplied staging paths against an immutable baseline; F4 benchmark/stock validation and raw/adjusted evidence need explicit routing.
- Reproduced examples: empty provenance returns strict-PIT admitted; availability at 03:00 UTC passes a cutoff at 02:00 UTC; NULL volume_unit reports D4 PASS; changing archive open and provider leaves D6 PASS. See `claude methods/M1_CLOSURE_CODEX_REVIEW.md` for exact fixes and finite acceptance criteria.
- Independent diagnostic output: `claude methods/_m1_codex_review/closure_results.jsonl`; reproducer: `closure_review.py`; inspectable notebook: `M1_closure_review.ipynb` in the same directory. Original production metadata and the inspected Claude artifact hashes remained unchanged. The production diagnostic matches the frozen baseline exactly.
- Next action: fix F1-F4 locally and demonstrate one clean and several corrupted temporary-staging runs through the actual validation entry point. No new broad audit, no downloads, no production mutation, no runtime changes, no services, no commits/pushes. Pilot execution still requires independent gate review and user authorization.

### 2026-09-06 — F1-F4 targeted execution-gate closure (Claude)

- State: `ready_for_review`. Read-only against production throughout. No runtime code, dataset, strategy set, methodology material, knowledge store, production database or M0 candidate touched; no network/plugin call, download, migration, service start, commit or push. Writes confined to `claude methods/_m1_closure/` and this ledger.
- Scope honoured: the coverage census, the deterministic 50-stock selection, the six temporal proofs and the 22 gate cases were **not** redone — Codex reproduced them and they stand. This pass fixed only the four false-pass paths.

| Finding | Fix | Test result |
|---|---|---|
| F1 temporal admission | validate inputs, normalize to absolute instants before comparing, declare date-only semantics | `temporal_contract.py` **13/13**, exit 0 |
| F2 fail-closed data checks | NULL/blank/unsupported unit, empty-population UNKNOWN, D0 population, D7 duplicates, D8 declared-transformation reconciliation | `test_acceptance_gates.py` **46/46**, exit 0 |
| F3 archive protection + real gate | whole-database fingerprint; `snapshot`/`validate` CLI with explicit paths; validate never writes; FAIL/UNKNOWN → exit 1 | `test_staging_gate_e2e.py` **19/19**, exit 0 |
| F4 pilot routing | stock/benchmark separation, raw-vs-adjusted evidence declared, warm-up measured separately | F4a-F4e in the 46 |

- **F1.** Both fixtures Codex demonstrated now reject. Blank strings were passing because the checks tested only `None`; and a `2024-06-28T03:00:00Z` availability was passing a `2024-06-28T10:00:00+08:00` (02:00 UTC) cutoff because `"0" < "1"` lexicographically — the version was an hour too late. Every value now goes through `to_instant()`, which rejects missing/blank/malformed/impossible/naive input and returns a tz-aware instant. **Date-only semantics are declared and widen fail-closed in both directions**: event/availability/ingestion/vintage dates widen to end-of-day `+08:00`, a date-only cutoff to start-of-day, so a same-day vintage does not pass a same-day cutoff. Timezone is a fixed `+08:00` constant (no DST in China since 1991) rather than a tz-database lookup, so the contract cannot shift under a tzdata update. Naive timestamps are rejected rather than assumed local — silently mixing date strings, local times and UTC is exactly what produced the second hole.
- **F2.** `volume_unit = NULL` was returning D4 **PASS** with `verifiable=1, contradicted=0, quarantined=0`: SQL three-valued logic made both `volume_unit='hand'` and `NOT IN ('hand','share')` evaluate to NULL, so the row counted as verified and could never be contradicted. Verification now requires a non-null, non-blank, supported declared unit; anything else is quarantined as missing evidence. Empty tables returned PASS from D1/D2/D3/D5 and now return UNKNOWN, backed by a new **D0** gate that requires an explicitly declared expected population. **D7** duplicate-key checking is restored (it had been dropped in the registry rewrite). **D8** cross-store reconciliation is new and *refuses* to compare a raw series against an adjusted one unless a transformation is declared — demanding raw price equality would manufacture a failure, comparing silently would manufacture a pass.
- **F3.** The old D6 hashed six columns, so editing an archive's open price or provider left it PASS; `F3a` now asserts the narrow digest is blind while the whole-database fingerprint (schema + every table, column and row) catches it. The documented command always ran `production_run()`, took no paths, had no frozen baseline, **overwrote `acceptance_baseline.json` on every run**, and exited 0 after reporting FAIL/UNKNOWN. It is now split: `snapshot` is the only writing mode and refuses to clobber an existing baseline without `--force`; `validate` takes staging paths, archive paths, the pilot manifest, the pinned calendar and a read-only frozen baseline, writes nothing at all, and exits 1 when any required gate is FAIL **or UNKNOWN** — a diagnostic may say "we do not know", a gate authorizing a download may not. `acceptance_runner.py` remains a diagnostic that says so and no longer writes a baseline; the old `acceptance_baseline.json` is retired as `.SUPERSEDED.`.
- **F4.** D2 required every symbol to be in the stock catalog and D4 required trade-capacity evidence from every row, so a legitimate index benchmark could not pass either. Stocks and benchmarks are now routed from one manifest (`pilot_symbols.csv` carries the two benchmarks with `stratum=benchmark`): benchmarks are identity-checked only and excluded from D4, with the exclusion count printed. `F4d` proves the exclusion cannot absorb an unknown among the stocks. Stock unit verification explicitly demands **raw (unadjusted) price + positive amount + positive volume + a declared supported unit**; any adjusted research series must coexist with the raw one under a declared transformation. Coverage is three separate gates — V1 stocks, V2 benchmarks, V3 warm-up — with warm-up advisory by default and blocking under `--warmup-required`, never folded into V1. The 50,856-row figure is restated as a **gross upper bound** for capacity planning, not an expected row count, since IPOs, suspensions and BJ code history necessarily reduce it.
- End-to-end demonstration on temporary databases (19/19): clean staging validates (exit 0); impossible date, NULL unit, duplicate key, empty staging and short population each fail (exit 1); a tampered **archive** fails even when staging is clean, and validates again once restored; a missing path is exit 2, not a pass; the frozen baseline is byte-identical after every validation; and both production databases are unchanged in size and mtime across the whole run.
- One production-diagnostic change for Codex to note: **D2 moves from FAIL 6 to FAIL 4** because `SH000001`/`SH000300` are now routed as benchmarks instead of counted as missing from the stock catalog. The four bare 6-digit spellings are unchanged. New rows: D0 UNKNOWN (production declares no expected population), D7 PASS, D8 UNKNOWN (no declared transformation). D1 FAIL 1, D3 FAIL 4, D4 UNKNOWN, D5 PASS, D6 UNKNOWN all match the reproduced baseline.
- Wording accepted from the review: the local corpus cannot prove historical PIT availability, but that is **not** proof that no external archived version or dated source evidence could ever supply it, and **not** proof that three-year exploratory research is impossible. The correct posture is to freeze the chosen vintage, declare limitations, block revised-value leakage, and keep any research claim proportional to its evidence. `strict_pit_admissible_basis` was reworded accordingly.
- Reproduction (in `claude methods/_m1_closure/`, project venv, `-B -X utf8`): `coverage_gap_generator.py`, `temporal_contract.py`, `acceptance_runner.py`, `test_acceptance_gates.py`, `test_staging_gate_e2e.py`, `pilot_selection.py` — all exit 0. The authorization gate itself is `staging_gate.py`, which has no default invocation because every path must be supplied.
- Not done and not authorized: M2 pilot download, full rebuild, production promotion, A2, commits, pushes, service start. No broad multi-agent audit was launched.


### 2026-09-06 — Codex execution-gate wiring review

- Verdict: M1 is not yet `validated` as an executable M2 handoff. M0 remains validated; M2 downloads remain unauthorized. Do not repeat the accepted coverage census or deterministic pilot selection.
- Independently rerun: temporal contract **13/13**, acceptance checks **46/46**, and supplied real-command tests **19/19**, all exit 0. The earlier blank-provenance/timezone defects are closed. The remaining problems concern integration and output-path safety, not a new broad audit.
- **G1:** the actual staging command validates pricing rows but applies only a provenance-reference check to the research history; D8 reconciliation is not called. A disposable history fixture with an impossible date, invalid prices and a duplicate still returns exit 0. Validate both consumed views and wire required declared-transformation reconciliation into the real command.
- **G2:** the command drops listing metadata and demands the entire research window from every stock. A stock listed 2025-06-10 with all 305 eligible sessions is rejected for absent pre-listing data. Reuse the accepted listing-aware denominator and keep warm-up strictly before the research start.
- **G3:** `snapshot --force` can overwrite an input archive when `--baseline-out` aliases its path. This was reproduced only on a disposable database. Reject protected input/output aliases before any write, regardless of force.
- Full English handoff: `claude methods/M1_GATE_WIRING_CODEX_REVIEW.md`. Independent reproducer and captured results: `_m1_codex_review/gate_wiring_review.py` and `gate_wiring_results.jsonl`; companion notebook: `M1_gate_wiring_review.ipynb`.
- Production main/WAL size and mtime remained unchanged during the successful probe run. The frozen fixture baseline remained byte-identical through validation. HEAD remains `73f266d`; the index is empty. No download, runtime change, migration, service start, commit or push occurred.
- Next action: Claude fixes G1-G3 only in local closure artifacts, demonstrates clean and independently corrupted fixtures through the actual command, then stops at `ready_for_review`. Section 12 is the current handoff; a validated gate is a prerequisite to requesting separate authorization for the bounded staging pilot.

### 2026-09-06 — G1-G3 gate-wiring closure (Claude)

- State: `ready_for_review`. Production read-only throughout. No runtime code, dataset, strategy set, methodology material, knowledge store, production database or M0 candidate touched; no network/plugin call, download, migration, service start, staging, commit or push. Writes confined to `claude methods/_m1_closure/`, `claude methods/M1_CLOSURE.md` and this ledger. No broad multi-agent audit was launched.
- Scope honoured: the temporal fixes (13/13), primitive gate improvements (46/46), coverage census and deterministic pilot selection were **not** redone — Codex verified them and they stand. Only G1-G3 were addressed.

| ID | Defect | Fix | File:line | Result |
|---|---|---|---|---|
| G1 | history view almost unvalidated; D8 never invoked by `validate` | both views attached and validated; declared reconciliation wired as a required gate | `staging_gate.py:315-321`, `:363-381`, `:384-409` | 12 CLI cases |
| G2 | listing metadata discarded; full session set applied to every stock | per-symbol eligibility restored from the manifest; warm-up strictly separate | `staging_gate.py:135-148`, `:205-262`, `:411-441` | 7 CLI cases |
| G3 | `--baseline-out` could overwrite an input database under `--force` | all roles resolved and validated before any write; aliases rejected regardless of force | `staging_gate.py:74-112`, `:159-195`, `:295-300` | 15 CLI cases |

- **G1.** The command had been running date/price/unit/duplicate checks only against the pricing store, the foreign-key check against history, and **never calling D8 at all** — which is why Codex's history fixture carrying `trade_date='ERROR'`, `close=-999`, `high<low`, a wrong provider and a duplicate row still returned exit 0 / SUCCEEDED. Both consumed views are now attached into one connection and history is validated for population, dates, OHLC, duplicates and provenance (H0-H4). The declared cross-view transformation is a **required** gate: absent or unsupported transformations block rather than being skipped, and declaring `identity` across differing bases fails outright, so raw and adjusted prices are never compared as if identical. The old "clean" fixture was itself part of the defect — 728 pricing sessions against **three** history rows; the control is now a genuine two-view fixture with identical symbols and all 728 sessions on a common declared basis.
- **G2.** `load_manifest()` had reduced the manifest to bare symbols and coverage applied all 728 research sessions to every stock, so a stock listed 2025-06-10 holding **all 305** of its eligible sessions failed for lacking pre-listing bars. Eligibility is now computed per symbol from retained `list_date`/`delist_date`, reusing the accepted listing-aware denominator. Pre-IPO sessions are outside eligibility, not missing bars. Unknown listing stays UNRESOLVED and blocking rather than counting as complete. Warm-up sessions are selected strictly `< RESEARCH_START` with an explicit non-overlap assertion, a declarable `--warmup-sessions` depth, and its own gate separate from V1.
- **G3.** This was the dangerous one: `--baseline-out` pointed at an archive with `--force` returned exit 0 and replaced that database's SQLite header with JSON. All paths are now resolved and every role validated in `guard_paths()` **before any file is opened for writing**. An output that equals, normalizes to, or is a filesystem alias of an archive or the calendar is rejected regardless of `--force`; aliasing covers exact equality, Windows case-insensitivity and `os.path.samefile` (hardlinks/symlinks/junctions). Role collisions are rejected too (archive==archive, staging==archive, staging==staging). `--force` may replace only a document whose `kind` is `frozen_archive_baseline`, so it cannot be aimed at an arbitrary file. Every rejection is asserted to leave the target's SHA-256 unchanged.
- End-to-end through the real CLI: **36 checks, 0 unexpected, exit 0**. Clean two-view control succeeds (exit 0); five separately corrupted history fixtures, missing coverage, missing transformation, unsupported transformation, mismatched bases and same-basis divergence each fail (exit 1); full eligible IPO coverage succeeds while deleting one required post-listing session fails; unknown eligibility blocks; every path-alias probe returns exit 2 with inputs byte-identical. Frozen baseline byte-identical throughout; both production databases unchanged in size and mtime.
- Full suite: `coverage_gap_generator.py` exit 0 (identity 3,900,763 holds), `temporal_contract.py` 13/13 exit 0, `acceptance_runner.py` exit 0 (diagnostic only), `test_acceptance_gates.py` 46/46 exit 0, `test_staging_gate_e2e.py` 36/36 exit 0, `pilot_selection.py` exit 0 (50 + 2).
- One design decision flagged for Codex: a manifest that **declares** zero benchmarks yields `NOT_APPLICABLE` for V2 (scoped out), whereas an empty stock population yields blocking `UNKNOWN`. Without this no benchmark-free sub-batch could ever pass. The declared total is still cross-checked by the P0 population gate, so an accidental omission is caught there. If benchmarks should be unconditionally mandatory, that is a one-line change.
- Pilot clarifications (universe and strategy unchanged): coverage is judged per eligible listing interval, so the 8 in-window IPOs legitimately have fewer eligible sessions and must not be padded with fabricated pre-listing bars; the pilot must either fetch both consumed views or explicitly declare that it populates only the pricing store, because absence must not pass by default; and warm-up depth is honestly unavailable for new listings, with advisory-vs-blocking left to the authorization step.
- Remaining limitations: strict-PIT admissible rows remain 0 and cannot be created retroactively; historical universe / ST / suspension / delist / BJ code mapping remain UNKNOWN; `identity` is the only supported transformation because no local factor series exists; expected history population must be declared per batch or the gate blocks; no backend regression suite was rerun because runtime code was untouched.
- Not done and not authorized: M2 pilot download, full-market rebuild, production promotion, A2, commits, pushes, service start. M1 is not self-approved — it stops here for Codex acceptance.


### 2026-09-06 — Codex review of the G1-G3 closure

- Verdict: **G3's reproduced overwrite defect is closed; G1 and G2 remain partially open.** M1 is not yet validated as an executable M2 handoff. M0 and the accepted census/stock selection stand.
- Independently rerun: temporal proofs 13/13, primitive checks 46/46, supplied end-to-end checks 36/36; all commands exit 0. The history error checks, 305-session IPO control and Windows path-alias protections now pass their supplied regressions.
- G1a remains: history population checks count distinct symbols and global dates, while reconciliation sees only intersecting keys. Removing one required history key (3,640 to 3,639 common records), or replacing a whole stock series with XX123456 (2,912 common records), still returns exit 0. Validate expected identities and eligible keys in both consumed views, not just marginal counts.
- G1b remains: actual history adjustment_mode=qfq passes when the CLI claims both bases are none; changing history high from 11 to 12 while preserving close also passes identity reconciliation. Verify actual representation metadata and the declared identity fields, including OHLC.
- G2a remains: the actual pilot manifest has blank listing dates for both indices. Disposable complete two-view data built from that manifest (34,737 eligible stock records plus 1,456 benchmark records) passes V1 and reconciliation but fails V2 UNKNOWN. Use an explicit benchmark eligibility contract and test the actual 50+2 manifest; do not invent IPO dates or remove the indices.
- G2b remains: --warmup-required --warmup-sessions 250 without --warmup-start silently makes V3 advisory/NOT_APPLICABLE and returns exit 0. Reject or resolve incomplete required configuration; distinguish full eligible coverage from per-security feature readiness.
- Full English review and finite closure criteria: `claude methods/M1_G_CLOSURE_CODEX_REVIEW.md`. Reproducer/results/notebook: `_m1_codex_review/gclosure_review.py`, `gclosure_results.jsonl`, and `M1_gclosure_review.ipynb`. Supplied-suite outputs are saved in `gclosure_suite_results.json`.
- Production main/WAL sizes and mtimes remained unchanged; fixture archives, baseline and calendar remained hash-identical; reviewed Claude artifacts were unchanged during the probes. Reviewer writes were limited to local review artifacts and this ledger. No runtime modification, download, migration, service startup, staging, commit or push.
- Next: close G1a/G1b/G2a/G2b only, preserve G3, and stop for independent review. Do not restart a broad audit or begin M2.

### 2026-09-06 — G1a / G1b / G2a / G2b closure (Claude)

- State: `ready_for_review`. Production read-only throughout. No runtime code, dataset, strategy set, methodology/knowledge material, production database or M0 candidate touched; no network/plugin call, download, migration, service start, staging, commit or push. Writes confined to `claude methods/_m1_closure/`, `claude methods/M1_CLOSURE.md` and this ledger. No broad audit was restarted.
- Preserved and unchanged: G3 path protections, 13 temporal checks, 46 primitive checks, M0, the accepted coverage census, and the 50 selected pilot securities plus the two named benchmarks.

| ID | Defect | Fix | File:line | Real-CLI tests |
|---|---|---|---|---|
| G1a | marginal counts + inner join hid a deleted record and a substituted series | manifest-derived expected keys; per-security membership in both views; union-based identity | `staging_gate.py:182`, `:205`, `:280`, `:484` | 4 |
| G1b | X1 trusted the CLI arguments; X2 compared close alone | stored `adjustment_mode` verified per view, mixed bases rejected; identity over `open,high,low,close` at an explicit tolerance | `staging_gate.py:259`, `:280`, `:478`, `:504`, `:528` | 5 |
| G2a | delivered manifest's blank benchmark `list_date` made complete data UNRESOLVED | benchmarks get a `benchmark_research_window` contract; clean control driven by the actual manifest | `staging_gate.py:131`, `:157` | 2 |
| G2b | `--warmup-required --warmup-sessions 250` without `--warmup-start` exited 0 as advisory | interval derived from the pinned calendar, or input error; feature readiness separated from price coverage | `staging_gate.py:361`, `:548` | 5 |

- **G1a.** Expected keys now come from the manifest and never from observed data, so success can no longer rest on a non-empty intersection. `membership_gate` compares actual per-security key sets in **both** views and reports missing and unexpected symbols in both directions; `identity_gate` works over the full key union instead of an inner join. Both of Codex's probes now fail: deleting one history record fails and names the security, and substituting a whole 728-row series with `XX123456` fails with the substitution reported as an unexpected symbol alongside the absent one — while distinct symbol and session counts stay unchanged.
- **G1b.** `basis_gate` reads the **stored** `adjustment_mode` from each view, rejecting both disagreement with the declared basis and unintended mixed bases; history stored as `qfq` while `none` is declared now fails. Identity reconciliation compares `open,high,low,close` at an explicit `--identity-tolerance` (default 0.005), so the changed-high-with-unchanged-close probe fails, as do the equivalent open and low mutations. No adjustment factor is invented and no raw/adjusted equivalence is assumed; an unsupported transformation still blocks.
- **G2a.** The delivered manifest's blank `list_date` for `SH000300`/`SH000001` was being run through the stock listing rule, so complete benchmark data returned UNRESOLVED. Benchmarks now carry an explicit `benchmark_research_window` contract — the research window, honouring a `list_date` only if present. **The clean control is the actual `pilot_symbols.csv`**: 50 stocks + 2 benchmarks, 36,193 records per view, exit 0; deleting one required benchmark session fails. No index IPO date was fabricated and neither index was removed.
- **G2b.** `resolve_warmup` derives the interval from the pinned calendar when a depth is supplied and raises an input error (exit 2) when the required configuration is incomplete, so a required warm-up can never fall back to advisory NOT_APPLICABLE. V3b reports **per-security feature readiness** separately from M1's eligible price coverage, and states in its own detail that a new listing can satisfy M1 while being short here.
- **A defect this pass introduced and fixed before delivery**: the first implementation ran `membership_gate` per sub-population against a shared table, so checking the stocks flagged the two benchmarks as unexpected and the real manifest failed on complete data. The unexpected-symbol test belongs to the view, so it now takes an explicit `view_declared` set.
- **Correction to my previous report**: I claimed `P0` would catch an accidentally omitted benchmark. That was wrong — its expected total derived from the same manifest and was never an independent 52-member contract. `P0` has been removed; membership is judged per security against the manifest in each view.
- Results: `coverage_gap_generator.py` exit 0 (identity 3,900,763 holds), `temporal_contract.py` 13/13 exit 0, `acceptance_runner.py` exit 0 (diagnostic only), `test_acceptance_gates.py` 46/46 exit 0, `test_staging_gate_e2e.py` **36/36 exit 0**, `pilot_selection.py` exit 0 (50 + 2). Frozen baseline byte-identical and both archive hashes unchanged after every validation; both production databases unchanged in size and mtime.
- Remaining limitations: strict-PIT admissible rows remain 0 and cannot be created retroactively; historical universe / ST / suspension / delist / BJ code mapping remain UNKNOWN; `identity` is the only supported transformation because no local factor series exists; volume and amount are deliberately **not** reconciled across views since the stores legitimately differ on unit and amount availability, with unit correctness handled by P4 and still quarantined; the history scope must be declared rather than inferred; feature readiness is currently short for every stock on this corpus and is reported rather than waived; no backend regression suite was rerun because runtime code was untouched.
- Pilot proposal unchanged at 50 stocks + `SH000300`/`SH000001`, with three clarifications: benchmark coverage is contractually distinct from stock coverage; coverage is judged per eligible listing interval so in-window IPOs legitimately have fewer eligible sessions; and warm-up is a separate honest statement whose advisory-vs-blocking status is an authorization decision, with an advisory pilot barred from claiming feature readiness.
- Not done and not authorized: M2 pilot download, full-market rebuild, production promotion, A2, commits, pushes, service start. M1 is not self-approved; it stops here for Codex acceptance.


### 2026-09-06 — Codex key-domain and warm-up review

- Progress: the specific previous G1a/G1b/G2a/G2b counterexamples are now repaired. Missing/substituted history keys fail M3/X2; actual basis mismatch fails H5; changed high with unchanged close fails X2; required 250-session warm-up derives an interval and blocks when short; incomplete required configuration returns exit 2. G3 remains accepted.
- Independently rerun: 13 temporal proofs, 46 primitive checks, 36 current end-to-end checks, all exit 0. An independently constructed fixture plan from the actual CSV/calendar (not the gate's eligibility helper) contains 36,193 records per view for the unchanged 50+2 population and passes the actual command.
- M1 is still not fully validated as an executable M2 handoff. **K1:** membership checks missing eligible keys but not extra dates for known symbols. Adding BJ920002/2024-05-29 to both views, before its manifest listing date 2024-05-30, still returns exit 0. Compare observed/expected keys in both directions under the declared contract; genuine predecessor history would need explicit evidence and mapping, not automatic admission.
- **K2:** required feature readiness currently counts pricing warm-up only, and identity is restricted to the research window. In a temporary diagnostic subset, 250-session two-view warm-up passes; deleting all history warm-up or changing a history warm-up high still passes. Pin the actual feature-source view(s), enforce warm-up checks for required consumers, and explicitly exclude unconsumed views from readiness claims. This is not authorization to change the pilot universe or waive feature requirements.
- Test preservation: the latest 36 CLI checks replace several earlier cases; an unchanged count is not proof that all prior wiring regressions remain. Retain/restore the already-requested history date/price/duplicate/FK, transformation and eligibility scenarios.
- Full English handoff: `claude methods/M1_KEY_CONTRACT_CODEX_REVIEW.md`. Evidence under `_m1_codex_review/`: `key_contract_review.py`, `key_contract_results.jsonl`, `key_contract_suite_results.json`, `M1_key_contract_review.ipynb`.
- Production main/WAL sizes and mtimes, protected fixture hashes and reviewed artifact hashes remained unchanged during the independent probes. All fault writes were confined to disposable synthetic fixtures. No runtime modification, network/plugin call, download, migration, service start, staging, commit or push occurred.
- Next: close K1 and explicitly resolve K2 only, preserving all verified work. Stop for review; M2 and any production promotion still need separate authorization.

### 2026-09-06 — K1 / K2 closure (Claude)

- State: `ready_for_review`. Production read-only throughout. No runtime code, dataset, strategy set, methodology/knowledge material, production database or M0 candidate touched; no network/plugin call, download, migration, service start, staging, commit or push. Writes confined to `claude methods/_m1_closure/`, `claude methods/M1_CLOSURE.md` and this ledger. No broad audit was restarted.
- Preserved unchanged: G3 protections, the verified G1a/G1b/G2a/G2b behaviours, M0, the accepted coverage census, and the selected 50 stocks plus `SH000300`/`SH000001`.

| ID | Defect | Fix | File:line | Real-CLI tests |
|---|---|---|---|---|
| K1 | `membership_gate` computed `want - seen` but never `seen - want`; a pre-listing record added to BOTH views passed at 36,194 records each | keys compared in both directions inside each gate's own interval; `ineligible_records` reported separately from missing keys and unexpected symbols | `staging_gate.py:205`, `:239` | 3 |
| K2 | readiness counted pricing only and identity covered the research window only, so deleting all pre-window history still reported "ready" | `--warmup-consumers` must be declared; every consumed view validated over the warm-up interval; `both` also reconciles warm-up identity; a non-consumed view is reported NOT CONSUMED; readiness counts eligible observations and states its scope | `staging_gate.py:379`, `:563`, `:581`, `:592`, `:615` | 9 |

- **K1.** The gate only ever asked what was missing, never what was extra, and identity only compared the two views to each other — so `BJ920002 / 2024-05-29`, one day before its declared listing date, passed in both views. Keys are now compared in both directions **within each gate's own interval**, so a record inside the interval that is not an eligible session is an `ineligible_records` violation naming the security and session. Because each gate judges only its own interval, a legitimate declared warm-up record is never mistaken for an unexpected research record — proven by a dedicated case. A synthetic declared post-delisting record also fails. No predecessor-history mapping is invented: this rejects records under the **declared** contract and makes no claim that such observations are intrinsically fake.
- **K2.** The warm-up consumer boundary is now explicit and mandatory: requesting a warm-up without `--warmup-consumers` is an input error (exit 2). Each declared consumer view is validated for warm-up eligibility and completeness; `both` additionally reconciles warm-up identity over `open,high,low,close`, so a changed warm-up high now blocks. A view that is not consumed is reported `NOT CONSUMED` and explicitly **not certified**, and the readiness line carries its own `scope=` so a pricing-only count can never be read as history or both-view readiness. Readiness counts **eligible** observations only, and a security is ready only if the weakest declared consumer view supplies enough. The separation Codex asked for is proven end to end: `BJ920002` satisfies M1 coverage in full and still fails V3b readiness, with the failure text saying exactly that.
- **Test preservation.** The review was right that an unchanged count of 36 proved nothing. The suite is now **55 checks**, labelled by originating round, and the dropped scenarios are restored and marked `[restored]`: malformed history date, nonpositive history price, duplicate history key, dangling `ingest_run_id`, missing transformation, unsupported transformation, mismatched bases, and unknown eligibility. Blocks: G3 15, G2a 3, K1 3, G1a 4, G1b 5, G1r 8, K2 9, G2b 3, invariants 5.
- One correction of my own: the failing K2 assertion in development was my test lowercasing the haystack but not the needle, not a gate defect; fixed before delivery.
- Results: `coverage_gap_generator.py` exit 0 (identity 3,900,763 holds), `temporal_contract.py` 13/13 exit 0, `acceptance_runner.py` exit 0 (diagnostic only), `test_acceptance_gates.py` 46/46 exit 0, `test_staging_gate_e2e.py` **55/55 exit 0**, `pilot_selection.py` exit 0 (50 + 2). Frozen baseline byte-identical and both archive hashes unchanged after every validation; production databases unchanged in size and mtime; pinned calendar hash still `f1f1ce33c5cceb5c`.
- The K2 warm-up scenarios use a disposable diagnostic subset of two pre-window-listed stocks plus the two benchmarks, purely to isolate warm-up behaviour. It is never proposed as the pilot; the approved population stays 50 + 2 and the research control still runs on the actual delivered manifest.
- Remaining limitations: strict-PIT admissible rows remain 0 and cannot be created retroactively; historical universe / ST / suspension / delist / BJ code mapping remain UNKNOWN and K1 makes no claim that pre-listing observations are intrinsically fake; `identity` is the only supported transformation; volume and amount are deliberately not reconciled across views since the stores legitimately differ on unit and amount availability; history scope and warm-up consumers must be declared rather than inferred; every stock on this corpus is short of a 250-session warm-up, which is reported rather than waived, so no feature- or training-readiness claim is made; no backend regression suite was rerun because runtime code was untouched.
- Not done and not authorized: M2 pilot download, full-market rebuild, production promotion, A2, commits, pushes, service start. M1 is not self-approved; it stops here for Codex acceptance.


### 2026-09-06 — K1 empty-eligible-domain closure (Claude)

- State: `ready_for_review`. Production read-only throughout. No runtime code, dataset, strategy set, methodology/knowledge material, production database or M0 candidate touched; no network/plugin call, download, migration, service start, staging, commit or push. Writes confined to `claude methods/_m1_closure/`, `claude methods/M1_CLOSURE.md` and this ledger. No broad audit was restarted.
- Preserved unchanged: the K1 key-direction fix, the K2 warm-up consumer contract, G3, M0, the accepted census and the selected 50 + 2 population. All 55 prior end-to-end checks still run and pass; the suite is now **67**.
- Defect: `expected_key_map()` dropped known securities with zero eligible sessions from `expected`, while `membership_gate()` still demanded every declared security appear. The outcome was inverted — a correctly empty series failed as "absent data", and injecting one ineligible record into both views made the same batch **pass**.
- Fix: a known-empty eligible set is kept in `expected` as an empty set (`staging_gate.py:182`, `:200`), so observed keys are still compared against it; only a security that owes eligible records can be "absent" (`:248`); and an `empty_domain` policy is applied per interval (`:271`, `:609`) — `reject` on the research interval, where a member contributing no eligible research record is a **manifest** error rejected independently of the data, and `allow` on warm-up, where a security listed later legitimately supplies none. Under both policies an observed record inside an empty domain fails and names the security and session, so inserting invalid data can never turn a rejection into a success.
- Known-empty (`known_empty` / `correctly_empty`) is reported separately from UNKNOWN (`unresolved`); the two are never conflated, and a dedicated check asserts it.
- Research and warm-up stay distinct: an IPO listed after the warm-up interval reports `correctly_empty=1 empty_domain=allow` and passes coverage, while still failing required feature depth at `V3b` — both asserted on the same run.
- Results: `coverage_gap_generator.py` exit 0 (identity 3,900,763 holds), `temporal_contract.py` 13/13 exit 0, `acceptance_runner.py` exit 0 (diagnostic only), `test_acceptance_gates.py` 46/46 exit 0, `test_staging_gate_e2e.py` **67/67 exit 0**, `pilot_selection.py` exit 0 (50 + 2). Frozen baseline byte-identical and both archive hashes unchanged after every validation; production databases unchanged in size and mtime; pinned calendar hash still `f1f1ce33c5cceb5c`.
- The synthetic empty-domain contracts reuse selected identifiers with disposable listing metadata in temporary manifests. The approved manifest is never modified and no claim is made about any security's real listing history.
- Accepted note recorded: `V3b` reports observation depth and can PASS while `W2` identity fails; overall validation still fails because both are required. The V3b count is not a standalone readiness verdict.
- Remaining limitations: strict-PIT admissible rows remain 0 and cannot be created retroactively; historical universe / ST / suspension / delist / BJ code mapping remain UNKNOWN, and rejecting an out-of-interval record is a statement about the declared contract rather than a claim the observation is fake; `identity` is the only supported transformation; volume and amount are deliberately not reconciled across views; history scope and warm-up consumers must be declared; every stock on this corpus is short of a 250-session warm-up, reported rather than waived, so no feature- or training-readiness claim is made; no backend regression suite was rerun because runtime code was untouched.
- Not done and not authorized: M2 pilot download, full-market rebuild, production promotion, A2, commits, pushes, service start. M1 is not self-approved; it stops here for Codex acceptance.


### 2026-09-06 — M1 VALIDATED by Codex (data-contract and staging-acceptance scope)

- State: **`validated`** — technically, for the M1 data-contract and staging-acceptance scope only. Recorded from `claude methods/M1_ACCEPTANCE_CODEX.md`. This is **not** user acceptance, **not** dataset certification, **not** strict point-in-time research, **not** training readiness, and **not** authorization to begin M2.
- Independently reproduced by Codex: staging end-to-end suite **67 checks, 0 unexpected, exit 0**; primitive quality checks **46/46, exit 0**; temporal proofs **13/13** called directly, exit 0; 11/11 prior subprocess probes; the unchanged 50 stocks + 2 benchmarks with independently constructed expected keys at **36,193 records/view**, clean control exit 0.
- Accepted rejection behaviour: the original `BJ920002 / 2024-05-29` pre-listing addition fails in both membership gates; known-empty research eligibility is rejected on the explicit manifest policy with `absent_symbols=0` and `correctly_empty=1`; injecting a record into an empty domain cannot turn failure into success; an IPO with zero eligible warm-up passes coverage while only the depth gate `V3b` fails; an ineligible IPO warm-up observation fails `W1_pricing` and `W1_history`; missing or divergent required history warm-up fails overall; and a pricing-only declaration scopes the result with history explicitly NOT CONSUMED.
- Accepted design, recorded so it is not re-litigated: `expected_key_map()` retains known-empty sets and observed keys are compared against them; missing-series reporting applies only to securities that owe eligible records; research uses `empty_domain=reject` and warm-up `empty_domain=allow`, with an observed ineligible key failing under either; genuinely unknown eligibility stays UNKNOWN. **`V3b` is not a standalone readiness verdict** — all required membership, representation, reconciliation and depth gates must pass together.
- Preserved and not reopened: the K1/K2 closure, G3 protections, the G1/G2 fixes, M0, the accepted coverage census, and the selected 50 + 2 population. Codex explicitly asked that these audits not be restarted to inflate a test count.
- Safety at acceptance: production main/WAL sizes and nanosecond mtimes matched the prior baseline and were unchanged (`trading_local.sqlite3` 1,346,048,000 bytes / mtime_ns 1788517646307317700; `market_history.sqlite3` 1,234,956,288 bytes / mtime_ns 1788493486739967200; `-wal` 0 bytes). These are metadata checks, not fresh full-content hashes. HEAD remains `73f266d`; staging empty.
- What M1 does **not** establish, carried forward verbatim: M1 proves the contract and its tested rejection behaviour, **not that the existing corpus passes those gates**. Roughly three years of validated data, reviewed labels/cases, execution-model validation and chronological out-of-sample research remain ahead. Incomplete local history and warm-up, unresolved unit evidence, unknown historical universe / ST / suspension / delisting / BJ mapping, no locally established strict-PIT evidence and identity-only cross-view reconciliation all remain open. Identical fixture values are not independent real-source corroboration. The 746 legacy evaluations and A2 remain a separate prerequisite.

### 2026-09-06 — M2 pilot authorization request prepared (Claude), awaiting the user

- State: `proposed`, **awaiting explicit user authorization**. Nothing fetched, written or started. Document: `claude methods/M2_PILOT_AUTHORIZATION_REQUEST.md`.
- Pinned: population unchanged at 50 stocks + `SH000300`/`SH000001` (manifest sha256 `97e251ae84fc9274…`); research interval **2023-09-04..2026-09-04, 728 sessions**; optional warm-up **2022-08-24..2023-09-01, 250 sessions** ending strictly before the research start; calendar sha256 `f1f1ce33c5cceb5c…`; consumed views **both** with `--history-scope all` and `--warmup-consumers both`; price representation **raw (`none`) in both views with amount**, declared `--transformation identity`; staging destination `D:\codex-A股交易\staging\pilot_20260906\`; production opened read-only for baseline fingerprinting only.
- Volume: **36,193** eligible research records and **9,742** eligible warm-up records per view, **45,935** total; **52** requests, one per symbol per interval, ceiling 200 including retries.
- Sources graded: Sina primary at 0.45–0.79 symbols/s **measured from our own logs with the vendor quota UNVERIFIED**; Tonghuashun fallback at a 1.0 s **self-imposed client throttle, vendor limit UNVERIFIED**; Tencent unusable (no `amount`); Eastmoney **measured unavailable** (1 success in 32 runs). Runtime is a 1–3 hour range, not a commitment; measuring the real quotas is part of the pilot's purpose.
- Acceptance is two runs with different standing. **Run A is the blocking gate** (research interval only): every required gate must pass, and **`D4`/`P4` must move from UNKNOWN to PASS** — if the fetched data still cannot verify units, the pilot has not achieved its purpose and that is reported as failure, not waived. **Run B is advisory** (adds warm-up): it validates warm-up membership and cross-view warm-up identity and reports depth, and will not be presented as feature readiness.
- Warm-up is advisory for a stated, measured reason, not to make the pilot pass. Of the 50 approved stocks: **36 can reach 250 eligible warm-up sessions, 2 are partial, and 12 have zero** because they listed after 2022-08-24. Making the depth blocking would fail 14 of 50 for a reason no download can fix. Shrinking the population or lowering the depth to hide that was explicitly refused; the shortfall is published per security and **no feature-readiness claim is made for any stock**.
- Rollback: the pilot writes only inside the staging directory, so rollback is deleting it. `snapshot` refuses a `--baseline-out` aliasing an archive or the calendar with or without `--force`; `validate` writes nothing and re-verifies both production archives against the frozen baseline every run. No promotion step is included.
- Explicitly out of scope and not implied: qfq reconciliation (no local factor series), full-market rebuild, production promotion, model training, service startup, A2, commits and pushes.
- Until the user authorizes explicitly: no network or plugin call, no download, no database write, no service start, no staging directory, no commit, no push.


### 2026-09-06 — M2 authorization request revised (rev. 2), after Codex review

- State: `proposed`, **not executable as written**; two prerequisites block execution. Nothing fetched, written or started. No network/plugin call, download, dataset or production write, runtime edit, service, staging, commit or push.
- Scope of this round: revised `M2_PILOT_AUTHORIZATION_REQUEST.md` and the handoff/progress documents only. Local code inspection, no live source probes. M0, M1, K1/K2/G3, the census and the 50 + 2 selection were not reopened.

| Item | Correction | Evidence |
|---|---|---|
| 1. warm-up integrity vs depth | **Retracted my earlier claim.** `W1_pricing`, `W1_history`, `W2` and `V3b` are all registered `required=warm_required`, so omitting the flag makes warm-up *integrity* advisory too. Separation is now enforced by an acceptance rule over per-gate statuses: Run B uses `--warmup-required`, and exit 1 is accepted **only** if W1/W1/W2 are PASS and `V3b` is the sole failure with a shortfall exactly equal to a pre-published list of 14 securities | `staging_gate.py` warm-up block |
| 2. request budget | Symbol jobs 52, provider calls 52, **HTTP attempts 102** with no retries (raw `stock_zh_a_daily` issues **2** GETs — history + amount — and `stock_zh_index_daily` **1**); ceiling **306** with 3 attempts/job. Neither Sina URL takes a date parameter and slicing is client-side, so research + warm-up is **one combined fetch** and warm-up adds **zero** extra attempts. Pagination unavailable on both paths; fallback budget 0 | `stock_zh_a_sina.py:177,196,220`; `cons.py:54-59`; `index_stock_zh.py:299-316` |
| 3. source capability | Tonghuashun **cannot** serve the window — `limit = min(days, 500)`, `startTimeUtc/endTimeUtc = None`, `tail(limit)` — so it is removed from the plan and left UNRESOLVED, not described as a proven fallback. The Sina wrapper labels a raw call `unknown`, so the pilot may not stamp `none`; that is prerequisite **P1**. `stock_zh_index_daily` returns no `amount`, so benchmarks supply no liquidity evidence (already excluded from P4 by F4). Raw-path `drop_duplicates` on OHLCVA can silently drop identical sessions — recorded as a hazard to measure, not to work around | `tonghuasun_provider.py:214-247`; `akshare_provider.py:114`; `stock_zh_a_sina.py:222` |

- Pinned warm-up shortfall, published in advance so it cannot be padded after the fact: **12** securities with zero eligible warm-up (`BJ920002 BJ920003 BJ920005 BJ920007 BJ920519 BJ920627 SH603075 SH688549 SH688702 SZ301251 SZ301507 SZ301529`) and **2** partial (`BJ920001` 167, `BJ920006` 75). **36 of 50** can reach 250 sessions. Population, depth and thresholds were not adjusted to obtain a pass.
- Vendor quota is **not** inferred from observed throughput. Pacing is set slower than anything previously observed (≥1.5 s between Sina calls, concurrency 1, finite 10 s/30 s timeouts, retry only on timeout/5xx/reset, abort on 20 consecutive failures or any 403/429 or the 306 ceiling). akshare's own docstring warns that bulk fetching this endpoint readily gets an IP banned.
- Honest expected outcome recorded in advance: until P1/P2 are closed, Run A should FAIL at `P6`/`H5` (stored basis `unknown` != declared `none`) or leave `P4` UNKNOWN. That is correct fail-closed behaviour, stated now rather than discovered mid-run.
- Section 12 superseded: the stale kickoff still requested the completed K1/K2 repairs. It is retained as a historical record with a superseded banner, and the current handoff is the new Section 13.
- Not authorized and not done: pilot execution, P1/P2 remediation, full-market rebuild, production promotion, training, A2, services, commits, pushes.


### 2026-09-06 — M2a offline pilot runner implemented (Claude)

- State: `ready_for_review`. **Offline-only.** No network or plugin call, download, production write, real staging collection, service, Git staging/commit/push, training or promotion. New artifacts live only in `claude methods/_m2_pilot/`; the accepted M1 gates in `_m1_closure/` are **imported and unmodified**, as are production runtime code, datasets, strategies and methodology/knowledge materials.
- Deliverable: `claude methods/M2A_OFFLINE_PILOT_RUNNER.md`, backed by `transport.py`, `provenance.py`, `acceptance.py`, `pilot_runner.py` and `test_m2a.py`.

| Req | Implementation | Cases |
|---|---|---|
| 1 raw-basis provenance | `provenance.py` — basis is `none` only when the observed URL set is exactly the validated raw path; unit is measured from `amount / (volume x k)` against the price band, not stamped; `require_basis()` refuses to serve an unestablished basis; stock/benchmark routed separately | 11 |
| 2 transport controls | `transport.py` — pacing, counting and bounding on **every** attempt (both internal GETs of a raw stock call); finite 10 s/30 s timeouts; redirects disabled and surfaced as failures; bounded explicit retries; global ceiling; 403/429 abort the run without retry and stick; hidden library retries rejected | 14 |
| 3 machine-checkable acceptance | `acceptance.py` — parses every gate line, cross-checks against the gate's own verdict and the exit code, fails closed on disagreement; recomputes the **complete** per-security warm-up shortfall from the unchanged manifest and pinned calendar and compares it to the pinned 14 including eligible counts | 12 |
| 4 staging safety | `pilot_runner.py` — `plan()` is the default and writes nothing; `collect()` refuses unless armed and given a paced transport and a fetcher; destinations must be inside the declared root and may not alias a protected input; the root may not contain one; `.partial` files promoted only on success | 11 |

- Results: `test_m2a.py` **48 cases, 0 unexpected, exit 0**. The accepted M1 suites, imported but untouched, still pass: `temporal_contract.py` 13/13, `test_acceptance_gates.py` 46/46, `test_staging_gate_e2e.py` 67/67 — all exit 0. Production databases unchanged; no `staging/` directory exists; HEAD `73f266d`; index empty.
- Notable proofs: a series fetched from an unexpected URL is **rejected** and writes **zero** rows rather than being relabelled `none`; both GETs of a stock call are paced and counted, so 52 symbols is 102 attempts not 52; a 403/429 aborts on the first response and the abort is sticky; `exit 1` alone cannot satisfy warm-up acceptance — an integrity FAIL, an advisory integrity gate, any other required failure, an unexpected shortfall symbol, or a wrong eligible count each reject; an aborted run leaves the staging directory empty.
- One defect found and fixed during implementation: the destination guard checked containment before aliasing, so a destination aimed at a production database was rejected with the weaker "outside the staging root" message. Aliasing is now checked first, because "this destination IS production" is the more urgent diagnosis and understating it would misreport what was nearly done.
- **P2 reclassified, and my rev.2 wording retracted.** An unavailable fallback is a declared limitation, not a requirement to develop another source, and it was wrong to say *no* source can supply the window: the primary path returns the entire series in one call and slices it client-side. What is missing is a *second* source able to do the same. A failed primary job is a **reported failure**; the runner invents no substitute and reaches for no other provider, with a test asserting it.
- Unresolved live-data questions, deliberately left open: whether the live raw response carries `amount` for every pilot symbol; the real vendor limits (observed throughput is not a quota); whether the raw path's `drop_duplicates` on OHLCVA drops legitimate identical sessions; whether the observed URL set is stable; and whether index responses match the assumed column shape.
- Proposed later smoke test, bounded and not requested now: **3 symbols** (one ordinary stock, one BJ stock, one benchmark), **5 HTTP attempts** (ceiling 15), pacing >= 1.5 s, concurrency 1, into a discarded temporary directory, purely to confirm `amount` presence, the URL set and the index column shape. The 52-symbol pilot remains a separate authorization.
- Limitations carried forward unwaived: no strict-PIT evidence and none creatable retroactively; historical universe / ST / suspension / delist / BJ mapping UNKNOWN; corpus unit evidence UNKNOWN with the 293 STAR-board events still a hypothesis and nothing rescaled on suspicion; `identity` the only supported transformation; A2 and the 746 legacy evaluations a separate prerequisite; **warm-up collection acceptance is data integrity, never feature readiness** — 14 of 50 stocks cannot reach 250 sessions and no download changes that.
- Not authorized and not done: M2 execution, the live smoke test, full-market rebuild, production promotion, training, A2, commits, pushes.


### 2026-09-06 — M2a R1-R4 closure (Claude)

- State: `ready_for_review`. Offline-only. No network or plugin call, download, live smoke test, real staging collection, production write, service, Git operation, training or promotion. Work confined to `claude methods/_m2_pilot/` and the English M2a documents; the accepted M1 code in `_m1_closure/` is imported and **unmodified**, as are production runtime, datasets, strategies and methodology materials.

| ID | Reproduced defect | Fix | Regressions |
|---|---|---|---|
| R1 | rows came from an independent `fetcher` callback while the response body was discarded, so HTML responses still produced 45,935 rows/view and `promoted=True` | callback deleted; pure `decoder.py` parses the captured bodies; provenance requires the URL path and the payload's declared basis to corroborate, applies to benchmarks, and records body hash, schema, run id and mode | 21 |
| R2 | acceptance passed with only `P4=PASS`, with a mandatory gate marked advisory, with `V3b` absent, `V3b=UNKNOWN`, or `V3b=FAIL` advisory | gate inventory owned internally (20 research / 25 warm-up); missing, duplicate or weakened gates fail closed; `V3b` must exist, be required and be exactly FAIL; acceptance bound to manifest hash, calendar hash and the approved 50+2 population | 12 |
| R3 | 52 consecutive 404 jobs returned `completed`/`promoted`; a transport `RunAborted` was retried 3x; a `ValueError` was retried 3x; an infinite timeout was accepted | consecutive-failure stop at 20 with reset-on-success; honest rollups and publication only from complete collection; `RunAborted` re-raised before wrapping; only TimeoutError/ConnectionError transient; `math.isfinite` validation; hidden-retry check enforced at construction | 13 |
| R4 | the guard accepted trading == history and destination == another's `.partial`; two sequential `os.replace` calls left new trading + old history plus a stray partial | pairwise distinctness across all four final/temporary roles; a fresh run directory per run that must not already exist; publication is one pointer write after complete collection AND successful acceptance; no unowned partial is unlinked | 14 |

- Results: `test_m2a.py` **60 cases, 0 unexpected, exit 0**. The accepted M1 suites still pass unmodified: `temporal_contract.py` 13/13, `test_acceptance_gates.py` 46/46, `test_staging_gate_e2e.py` 67/67, all exit 0. Production databases unchanged; no `staging/` directory; manifest sha `97e251ae84fc9274`; HEAD `73f266d`.
- The integrated chain is now proven end to end through the unchanged M1 command: good bodies collect, validate (exit 0), accept and publish; **HTML bodies produce 0 stored rows, 0 successful jobs and no publication** - the exact counterexample that previously wrote 45,935 rows per view; a qfq-declaring payload on the correct raw path is rejected as UNKNOWN with 0 rows stored; and provenance rows carry the body SHA-256, run id, `run_mode=offline_synthetic_fixture` and an explicit note that copying one fetch into two stores is lineage consistency, not independent corroboration.
- Two defects found in my own new code and fixed before delivery: the decoder accepted `2025-13-99` on shape alone (the same defect class the M1 review found in D1), and it silently dropped `volume` for benchmarks so every index job failed downstream. Both now have regressions.
- Corrected a test that encoded misleading success: all-jobs-failed previously asserted `completed`; it now asserts `completed_with_failures`, `collection_complete=False` and `published=False`.
- Deliberately unimplemented and failing closed: the real Sina JS-encoded payload decoder. It needs the vendor routine and a real sample to validate against, which an offline milestone does not have, so `SINA_KLC_JS` is registered KNOWN-UNSUPPORTED and raises rather than guessing.
- Limitations carried forward unwaived: no strict-PIT evidence; historical universe / ST / suspension / delist / BJ mapping UNKNOWN; corpus unit evidence UNKNOWN with the 293 STAR-board events still a hypothesis and nothing rescaled; `identity` the only supported transformation; A2 and the 746 legacy evaluations a separate prerequisite; warm-up collection acceptance is data integrity, never feature readiness.
- Not authorized and not done: the live smoke test, the 52-symbol pilot, full-market rebuild, production promotion, training, A2, commits, pushes. **Neither the smoke test nor the pilot is presented as ready for authorization on this implementation.**


### 2026-09-06 — M2a closure of the seven remaining counterexamples (Claude)

- State: `ready_for_review`. Offline-only. No network or plugin call, download, real collection, production or runtime change, service, Git staging/commit/push, training or promotion. Changes confined to `claude methods/_m2_pilot/` and the English M2a documents. Reviewer artifacts in `_m2_codex_review/` untouched; M0/M1 not reopened; the live decoder deliberately not implemented.
- Changed files: `_m2_pilot/pilot_runner.py`, `_m2_pilot/acceptance.py`, `_m2_pilot/transport.py`, `_m2_pilot/test_m2a.py`. `decoder.py` and `provenance.py` unchanged.

| ID | Counterexample | Fix |
|---|---|---|
| R1 | the deleted `fetcher` had become the public `responses` mapping; HTML responses plus replacement envelopes produced 52 jobs and 45,935 rows/view with body hashes matching the replacement | the parameter is removed; one captured response object is the sole source of body, hash and lineage |
| R2a | `enforce=False` accepted a report containing only `P4=PASS`, and the delivered happy-path test used that flag | the switch is removed; reduced fixtures use private helpers so a test cannot widen production |
| R2b | swapping `SH688001` for `SH600998` kept 50+2 and passed; hashes optional and prefix-compared | manifest hash, calendar path/hash and candidate fingerprint are mandatory and compared exactly |
| R2c | a `FAILED … P4` line followed by an all-pass report and `SUCCEEDED` was accepted (last verdict won) | more than one verdict line is a rejection |
| R2d/R4 | run A's collection and acceptance Boolean let runner B publish a pointer naming two nonexistent databases | `finalize()` replaces the Boolean and verifies run identity, file existence and verdicts bound to this candidate's exact bytes, re-checked before the pointer moves |
| R3 | the first transport-raised `RunAborted` never latched `aborted_reason`, so the next call returned 200 and attempts reached 2 | the reason is latched before propagating; a second call raises without touching the transport |
| R4 | `CURRENT.json`/`.tmp` were not path roles; a hardlink at the fixed temp name let publication overwrite a protected sentinel | publication roles are guarded at construction and re-checked at publication; the temp is run-specific and `O_EXCL`-created; a pre-existing one is refused, never followed or deleted; on failure only our own temp is removed and the previous pointer and pair are preserved |

- Results: `test_m2a.py` **73 cases, 0 unexpected, exit 0** (60 -> 73; eleven new `C-` regressions on the public path plus the full chain). Accepted M1 suites unmodified and still passing: 13/13, 46/46, 67/67, all exit 0. Production databases unchanged; no `staging/` directory; manifest sha `97e251ae84fc9274`; HEAD `73f266d`; index empty.
- The `FULL` case drives the approved 50 stocks + 2 benchmarks and pinned calendar through fake transport -> decoder -> both staging views -> the unchanged M1 `snapshot`/`validate` -> **both public acceptance functions with full hashes and the candidate fingerprint** -> `finalize`: 52/52 jobs, research exit 0, warm-up exit 1 with exactly the pinned 14-security shortfall, both verdicts accepted, publication succeeds.
- Corrections to my own earlier handoff claims, all of which were wrong: the callback was not fully deleted (it became `responses`); acceptance bindings were optional and prefix-compared, not mandatory and exact; the abort was not sticky and only the first call was tested; and the "integrated chain" happy path used `enforce=False` with a reduced population while the publication-failure test injected an HTTP failure rather than a pointer failure.
- Unchanged limitations: the real Sina JS payload decoder remains KNOWN-UNSUPPORTED and is not implemented here; no strict-PIT evidence; universe / ST / suspension / delist / BJ mapping UNKNOWN; corpus unit evidence UNKNOWN with the 293 STAR-board events still a hypothesis; `identity` the only supported transformation; A2 and the 746 legacy evaluations a separate prerequisite; warm-up collection acceptance is data integrity, never feature readiness.
- Not authorized and not done: live sampling, the 52-symbol collection, full-market rebuild, production promotion, training, A2, commits, pushes. Neither live sampling nor the pilot is presented as ready.


### 2026-09-06 — M2a R2 binding closure (Claude)

- State: `ready_for_review`. Offline-only. No network, download, real collection, production or runtime change, service, Git staging/commit/push, training or promotion. Changes limited to the binding mechanism, its focused tests and the English M2a documents. Reviewer artifacts untouched; M0/M1 not reopened; live decoder still not implemented.
- Changed files: `_m2_pilot/pilot_runner.py`, `_m2_pilot/test_m2a.py`. `acceptance.py`, `transport.py`, `decoder.py`, `provenance.py` and every M1 artifact unchanged.

| ID | Defect | Fix |
|---|---|---|
| R2.1 | `bind_inputs()` merely checked that a fingerprint was supplied and copied it into the verdict, so the gate execution never entered the binding. Candidate A's untouched report plus candidate B's genuine fingerprint produced accepted verdicts, and B - 45,934 rows/view, own research gate exiting 1 on M1/M3 - published. | `validate_candidate(mode, ...)` is runner-owned and now performs the M1 invocation itself against these exact views and frozen inputs, fingerprinting before and after, refusing a candidate that changes mid-run, and passing the fingerprint IT measured to acceptance. It returns a `ValidationReceipt`; the raw-text helpers still return `Verdict`s, which finalization refuses. |
| R2.2 | Both finalization slots only required `accepted=True` plus a matching fingerprint, so passing the research verdict twice published a candidate whose real warm-up gate reported `W1_pricing=FAIL`. | `finalize(collection, receipts)` requires **one `research` and one `warmup_collection`** receipt for the same run, candidate and frozen inputs. Mode is explicit on the receipt, never inferred from argument position, and two receipts of one mode are refused. |

- Results: `test_m2a.py` **79 cases, 0 unexpected, exit 0**. Accepted M1 suites unmodified and still passing: 13/13, 46/46, 67/67, all exit 0. Production databases unchanged; no `staging/` directory; HEAD `73f266d`; index empty; reviewer artifact hashes unchanged.
- New regressions: a short candidate refused by its own official validation; candidate A's receipt unable to publish candidate B; no public way to mint a receipt from raw gate text; a research receipt unable to satisfy warm-up; a single receipt insufficient; a candidate mutated *during* the gate run refused by the same binding; and `B-FULL`, the approved 50+2 publishing through the official path with research `gate_exit=0`, warm-up `gate_exit=1` and exactly the pinned 14-security shortfall, recording `validated_modes: [research, warmup_collection]`.
- The short-candidate and warm-up-gap fixtures omit a day from **both** response envelopes, so the shortfall is genuine rather than doctored after collection.
- Correction to my earlier handoff: I wrote that acceptance was "bound to the candidate fingerprint". It was bound to a fingerprint *the caller supplied*, which is not the same thing and is precisely what the review exploited. The binding is now produced by the code that runs the gate.
- Unchanged limitations: live Sina decoder KNOWN-UNSUPPORTED and not implemented; no strict-PIT evidence; universe / ST / suspension / delist / BJ mapping UNKNOWN; corpus unit evidence UNKNOWN with the 293 STAR-board events still a hypothesis; `identity` the only transformation; A2 and the 746 legacy evaluations a separate prerequisite; warm-up collection acceptance is data integrity, never feature readiness.
- Not authorized and not done: live sampling, the 52-symbol collection, full-market rebuild, production promotion, training, A2, commits, pushes.


### 2026-09-07 — M2a technically VALIDATED by Codex (offline pilot-runner scope)

- State: **`validated`** — technically, for the current offline pilot-runner scope only. Recorded from `claude methods/M2A_ACCEPTANCE_CODEX.md` (Codex, 2026-09-07 ≈ 00:04 Asia/Taipei). This is **not** user acceptance and **not** authorization for any live execution; Codex found no outstanding blocker in the bounded closure review.
- Independently executed by Codex: delivered `test_m2a.py` **79 cases, 0 unexpected, exit 0**; independent `_m2_codex_review/review_m2a_receipts.py` **12 scenario groups passed** plus unchanged-production/input and cleanup assertions, exit 0, with socket connections blocked. The independent full-chain fixtures used the actual approved 50-stock / two-benchmark manifest and pinned calendar with synthetic response bodies only, exercising the real collector, decoder, both disposable staging databases, runner-owned `validate_candidate`, the unchanged M1 validation and receipt-based finalization.
- Closure results accepted: R1 (one response-body path; the removed body override is refused before any request; HTML yields no successful job), R2 (mandatory contract checks; truncated hashes, missing calendar pins and contradictory verdicts refused), R2.1 (candidate A's genuine report cannot publish candidate B; B's own official validation detects its missing research row), R2.2 (research receipts cannot replace warm-up; the honest failed warm-up pair is refused), binding during and after validation, R3 sticky abort, R4 protected publication paths; healthy chain 52 jobs, **45,935 synthetic rows per view**, research exit 0, warm-up exit 1 with exactly the approved 14-security depth shortfall.
- Scope statement carried forward: validated = the offline, trusted single-process engineering workflow and its reviewed rejection/publication behaviour on synthetic fixtures. **Not validated or authorized:** real Sina payload decoding or live transport (both deliberately unsupported/disabled); live source semantics, amount meaning, unit correctness, adjustment evidence, endpoint completeness, vendor limits or independent corroboration; any three-year corpus, full-market coverage, strict point-in-time reconstruction, feature readiness, trained model, strategy effectiveness or profitability; production migration/promotion, services, commits or pushes. `ValidationReceipt` is an ordinary dataclass, not a security boundary against hostile in-process code. A2 and the 746 legacy evaluations remain a separate prerequisite.
- Safety evidence at acceptance: production main/WAL metadata at the established baseline (`trading_local.sqlite3` 1,346,048,000 B / mtime_ns 1788517646307317700; `market_history.sqlite3` 1,234,956,288 B / 1788493486739967200; `-wal` 0 B) — metadata checks, not new full-content hashes; reviewed M1/M2 files, manifest and calendar hashes retained; HEAD `73f266d`; index empty; no real `staging/pilot_20260906`. Reviewed SHA-256: `pilot_runner.py` `943a8c3f…`, `test_m2a.py` `5ec05456…`, `pilot_symbols.csv` `97e251ae…`.
- Instruction recorded from the acceptance: preserve the validated implementation; do not reopen M0/M1 or repeat the completed M2a repair cycle without new evidence; next, **prepare (not execute)** a bounded three-symbol real-source verification request that makes the live-decoder gap explicit; synchronize the stale Section 14 (48 cases; "live smoke versus 52-symbol pilot" presented as the immediate choice) with this result while preserving historical sections as superseded records.


### 2026-09-07 — Handoff synchronized; M2b three-symbol real-source verification request prepared (Claude)

- State: M2a `validated` (unchanged); **M2b `proposed`, awaiting the user.** Documentation and planning only: no network or plugin call, download, production/runtime/dataset write, staging or `tmp/` directory, service, commit, push, training or promotion. The validated M2a code is untouched (`_m2_pilot/`: `pilot_runner.py` `943a8c3f…`, `test_m2a.py` `5ec05456…`, `decoder.py` `8291e9f2…`, `transport.py` `f57bbc6c…`, `provenance.py` `21197f57…`, `acceptance.py` `efa46c13…`), as is the accepted M1 code (`_m1_closure/`, sha256 computed 2026-09-07: `staging_gate.py` `7152d773…`, `coverage_gap_generator.py` `ad327ee9…`, `test_staging_gate_e2e.py` `f87efede…`, `test_acceptance_gates.py` `e1e4d7fb…`, `temporal_contract.py` `ef4778ef…`, `acceptance_runner.py` `59b67c18…`, `pilot_selection.py` `d7930607…`); M0/M1/M2a not reopened.
- Local reconfirmation on 2026-09-07: `test_m2a.py` **79 cases, 0 unexpected, exit 0** (same command as Codex); production database metadata identical to the acceptance table; manifest sha `97e251ae…` and calendar sha `f1f1ce33…` unchanged; HEAD `73f266d`, index empty; no `staging/` or `tmp/` directory.
- Files: new `claude methods/M2B_REAL_SOURCE_VERIFICATION_REQUEST.md`; this file — Section 14 marked superseded, Section 15 added, these two ledger entries. `M2A_OFFLINE_PILOT_RUNNER.md` still carries its pre-acceptance `ready_for_review` header and was deliberately not edited; the acceptance report and this ledger are authoritative for M2a's status.
- Selection from the unchanged manifest: **`SH600011` 华能国际** (`ordinary_control`; listed 2001-12-06; 538 local rows with 0 null `amount`), **`BJ920000` 安徽凤凰** (`bj_code_history`; listed 2020-12-23; local history starts exactly at the 2024-08-13 code boundary, so one request settles whether pre-boundary history is served under `bj920000`), **`SH000300`** (benchmark; separate index path). All three owe 728 research and 250 warm-up sessions on the pinned calendar.
- Budget reconfirmed from installed akshare 1.18.64: 3 jobs ordered `SH600011`, `SH000300`, `BJ920000` so the consecutive-failure stop cannot skip the two capability jobs; 3 provider calls; **5 HTTP attempts without retries, ceiling 15**; pacing ≥ 1.5 s, concurrency 1, timeouts 10 s / 30 s, no redirects, library retries asserted 0, 403/429 sticky abort, 2 consecutive job failures stop, 15-minute wall-clock cap, run only outside continuous trading hours with the local stack stopped; run outputs only under the gitignored `tmp/m2b_smoke_<run_id>/`, and at cleanup the evidence subset (report, checks, capture manifest and, by default and subject to the user's choice, the five raw bodies) is moved to the untracked, never-staged `claude methods/_m2_smoke/evidence_<run_id>/`; production and all M1/M2a artifacts fingerprinted before/after and opened read-only or not at all (`market_history.sqlite3` never opened); TLS trust store pinned; a write-nothing `--plan` mode prints the five URLs and the pre-flight results before any authorization; an offline, socket-blocked replay of the installed adapter on the captured bodies is a required check; verdicts are per job plus a capability verdict, with BJ non-service under the `92xxxx` code a documented finding rather than a capability failure; no M1 gate run, no `PilotRunner`, no basis label stamped.
- Live-path findings from reading the installed adapter (new evidence, outside M2a's validated offline scope; recorded as prerequisites, not as a reopening — no M2a test fails): (1) the `getAmountBySymbol` response is an **outstanding-share** series (万股 × 10,000, `stock_zh_a_sina.py:196-208`), not traded amount — `amount` comes from the `klc_kl.js` payload itself, so M2a's `merge_stock_responses` semantics cannot be used live; (2) the index adapter path is `…/hisdata/klc_kl.js?d=2020_2_4` (`index_stock_zh.py:302-303`), not the `hisdata_klc2` template in `provenance.py`; (3) the adapter lowercases symbols in URLs while `expected_urls()` formats the uppercase manifest symbol; (4) the vendor decode routine `hk_js_decode` (sha256 `39a599c9…`) loads offline in mini-racer 0.14.1; it dispatches on a header to six decoders, of which only branch `_3466`/`O` emits `amount`, and `prevclose` is an optional per-record key rather than a basis marker — no real sample exists to validate the routine against, and that is the smoke's purpose; (5) the shell environment routes `requests` through the loopback proxy `http://127.0.0.1:7892` via `HTTP(S)_PROXY`, to be recorded per request with the TLS trust store pinned; (6) M2a `provenance.derive` expects a response-declared basis that the Sina payload does not carry, so the P1 basis-label design must derive the basis from the adapter code path.
- Pass/fail is fully specified in the request: transport, source-schema, decode, identity (read-only cross-check against the local cache), raw-basis evidence (code-derived: raw branch plus no factor URL), unit/amount semantics and date-coverage checks, with the benchmark handled separately and the outstanding-share series never labelled amount. The smoke produces basis evidence; it does not assign `none` (P1 stays open).
- The draft was adversarially reviewed the same day (four read-only lenses plus per-finding skeptics); the corrections — `prevclose` is optional per record and not basis evidence, the wall-clock cap and consecutive-job stop live in the smoke code rather than in `PacedTransport`, `requests` exceptions must be mapped to the builtin transient types the transport recognises, the index query parameter and production's third `qfq.js` GET are stated, the evidence-directory write is disclosed everywhere, `-shm` files are recorded but do not invalidate a run, the TLS trust store and stack-not-running pre-flights were added, and from the completeness critic a write-nothing `--plan` mode, the offline adapter replay, the captured-artefact definition (`response.content` with encodings recorded), per-job verdicts, a reviewer reproduction step and the filled handoff record — are folded into the request before delivery.
- Boundaries: preparing the request authorizes nothing. Boundary 1a (offline smoke code + socket-blocked tests under `claude methods/_m2_smoke/`, stopping at `ready_for_review` with Codex review as the protocol default) and 1b (executing the five requests) are separate user decisions; boundary 2 (the 52-symbol pilot) is later and separate and requires a smoke PASS, the live-path corrections with tests, the P1 decision and a revised M2 request. Not authorized and not done: live calls, downloads, the 52-symbol collection, full-market rebuild, training, promotion, services, commits, pushes.


### 2026-09-07 - M2b boundary 1a: offline smoke implementation (Claude)

- State: `ready_for_review`. Boundary 1a only. **1b was not executed**: no network or plugin call, download, real collection, production or runtime change, service operation, Git staging/commit/push, training or promotion. New code confined to `claude methods/_m2_smoke/`; the English M2b request and this ledger were the only edits. Validated M1 and M2a imported unmodified and still passing; reviewer artefacts in `_m2_codex_review/` untouched.
- Files added: `_m2_smoke/smoke_capture.py` (P-A), `_m2_smoke/sina_klc_decoder.py` (P-B), `_m2_smoke/smoke_checks.py` (P-C), `_m2_smoke/test_m2_smoke.py` (P-D). `pilot_runner.py` still sha256 `943a8c3f...`, `test_m2a.py` still `5ec05456...`.

| ID | Review finding | Implementation |
|---|---|---|
| S1 | the 15-minute limit was checked only before each request, so a trickling response, an in-flight read or an unbounded decode could outlive it; `requests` consumes `r.content` inside `session.get` when `stream=False`, so no outer check can regain control | an end-to-end deadline on an injected clock covering body consumption, retries, backoff and decoding: `stream=True` plus chunked reading with a deadline and byte budget checked after every chunk; a supervised daemon worker per job for a blocked call or a stuck decoder; `DeadlineExceeded` subclasses the unchanged `RunAborted`, so the stop is sticky; response 8 MiB / run 32 MiB / payload 4M chars / 20k rows / JS 20 s and 256 MiB limits; documented bounded shutdown allowance of deadline + 45 s, with the honest statement that no thread is killed and no process is terminated |
| S2 | C2 turned any non-200, empty or undecodable response into `not_served_under_92_code` and allowed capability PASS, contradicting T3's five-200 rule and the failed-job skip | one exhaustive outcome table over (transport state, payload state) deciding request result, job result, evidence class, skip and abort; transport failures, TLS failures, empty bodies, markup and decoder errors stay FAILED or INCONCLUSIVE; only an explicit 404/410 yields `vendor_explicit_absence_at_path`, with its cause recorded as **not established**; 403/429 remain unconditional aborts; T3 reads the same table so counts and outcomes always agree; a new capability verdict `PASS_WITH_DOCUMENTED_BJ_NON_SERVICE` records a documented BJ limitation without being an unqualified PASS and authorizes nothing |
| S3 | checks read live cache rows while retention kept only bodies plus a summary, so a replay against a refreshed cache could change results with identical response hashes | F2 freezes `reference/reference_extract.json` (only the consumed rows and fields, plus SQL, symbols, window, thresholds and hashes); every check reads it; `replay()` installs `db_guard()` so opening production during a replay raises; `checks.json` splits a hashed deterministic block from volatile `run_meta`; a mixed-basis overlap, zero denominator, missing amount or thin overlap yields an explicit INCONCLUSIVE with a stated reason instead of a repaired number |

- Minor clarifications closed: P-C compares the bytes-to-**text** step against the captured `response.text` hash; B2 now records that hfq **multiplies** and qfq **divides** (the earlier wording was wrong) and reads all three properties out of the installed adapter source; U4 is date-aligned; credential-bearing headers and proxy userinfo are redacted.
- Results: `test_m2_smoke.py` **79 cases, 0 unexpected, exit 0**; `smoke_capture.py --plan` exit 0 with F1-F8 all PASS and nothing written. Accepted suites unchanged and still passing: `test_m2a.py` 79/0, `temporal_contract.py` 13/13, `test_acceptance_gates.py` 46, `test_staging_gate_e2e.py` 67. Production databases unchanged (`trading_local.sqlite3` 1,346,048,000 B / mtime_ns 1788517646307317700; `market_history.sqlite3` 1,234,956,288 B / 1788493486739967200; `-wal` 0 B); no `tmp/` or `staging/`; HEAD `73f266d`; index empty.
- One documented departure from the plan's wording: the tests block **remote connections**, not the `socket.socket` class. `py_mini_racer` - the engine the vendor routine and therefore the R1 adapter replay run in - opens a loopback `socketpair()` on Windows, so a blanket class block would have made the adapter replay fail at 1b for a reason unrelated to the vendor while the test suite stayed green. A test proves a remote host is refused, a remote name will not resolve, and the engine still starts.
- Defect found in my own first draft and fixed: the outcome mapping classified a failed attempt by searching the error text for "transient", and "non-transient" contains it, so a TLS failure was classified as a retryable network fault - the exact confusion S2 exists to prevent. Failure class now comes from the unchanged M2a transport's own per-attempt classification; no check parses a message; a regression covers it.
- Unchanged limitations: the real Sina payload has still never been decoded or replayed - there is no real sample and inventing one would repeat the M2a R1 defect; no strict-PIT evidence; universe / ST / suspension / delist / BJ mapping UNKNOWN; corpus unit evidence UNKNOWN with the 293 STAR-board events still a hypothesis; `identity` the only transformation; A2 and the 746 legacy evaluations a separate prerequisite.
- Not authorized and not done: the five live requests (boundary 1b), evidence retention, the 52-symbol pilot, full-market rebuild, production promotion, training, A2, commits, pushes.


### 2026-09-07 - M2b boundary 1a closure: B1-B5 (Claude)

- State: `ready_for_review`. Boundary 1a only. **1b was not executed**: no network or plugin call, download, real collection, production or runtime change, service operation, Git staging/commit/push, training or promotion. Code confined to `claude methods/_m2_smoke/`; the English M2b request and this ledger were the only other edits. Accepted M1/M2a imported unmodified and still passing; the reviewer's report and `_m2_codex_review/review_m2b_1a.py` untouched and not adapted to pass.
- Context: the first 1a delivery passed 79 helper tests and still contained five integration defects, because the tests exercised helpers rather than the real call chains. Codex reproduced eight scenarios; all eight are now closed.

| ID | Defect | Closure |
|---|---|---|
| B1 | `capture()` supervised only the download; decoding, checks and the installed-adapter replay ran with no active deadline, and the armed CLI captured and printed a status line rather than running a workflow | `run_pipeline` is the single armed entry point (capture -> decode -> checks -> report -> retention) under ONE deadline handed from capture into `run_checks`; finalization has its own declared 120 s allowance and an offline replay its own 600 s budget; an already-spent budget refuses to decode, check or replay at all; decode and replay are supervised; the installed adapter's JS engine is swapped for one carrying the decoder's `timeout_sec`/`max_memory`; the manifest is flushed after every attempt and every write after finalization is refused |
| B2 | capture treated every HTTP 200 as success, so HTML for all three KLC bodies produced five issued requests and a `completed` run that its own checker then contradicted | the outcome table moved to a shared `smoke_outcomes.py` that BOTH sides import; `classify_payload` runs in capture before the dependent request is issued; an unusable payload skips the job's remainder and feeds the consecutive-failed-job stop (HTML on requests 1 and 3 now issues `[1, 3]` and never calls the BJ job); skips carry a `job_local`/`run_global` scope that T3 checks; `EV6` compares capture's recorded state with the retained bytes' state |
| B3 | `SSLError` inherits `ConnectionError`, so a certificate failure was mapped to the transient builtin and retried three times; and status handling ran only after full body consumption, so a 403/429 whose body timed out became a retryable timeout with the abort latch NULL | `SSLError` is caught first and raised as a non-retryable `TlsFailure` with its own `tls_failure` state (1 call, `retryable=False`, `error`); 403/429 are latched from the response headers with no body read (1 call, `RunAborted`, latch set); failed non-200 attempts retain a size-capped body and headers so they are no longer evidence-free |
| B4 | the recorded attempt start was taken before the pacing wait and retries had none, so a correctly paced run was recorded as `0.0, 0.0, 1.5, 3.0, 4.5` and failed its own T3 with a 0.000 s gap | a `TimedTransport` wrapper stamps the actual post-pacing start of every attempt including retries; T3 validates pacing from those stamps and fails a manifest that lacks one per attempt; recorded now equals actual `0.0, 1.5, 3.0, 4.5, 6.0` and T3 PASSes |
| B5 | `run_valid`/`invalidating_changes` were never consumed, the reference hash was copied rather than recomputed or bound, the calendar pin was recorded not enforced, and reference units were not qualified - so an invalidated capture, mismatched hashes, and every unit changed to `unknown` all returned PASS (the last with an identical deterministic hash) | gates `EV0` (valid, complete capture envelope), `EV3` (recomputed reference hash bound to the manifest, and the recomputed value is what enters the deterministic block), `EV4` (calendar/akshare/`hk_js_decode` pins), `EV5` (the frozen symbol/window/basis/threshold contract compared against the constants actually applied), plus unit and source qualification before any fixed ratio is interpreted; corruption regressions run through both the initial checks and the retained-evidence replay |

- Hardening: the offline guard no longer trusts loopback - it refuses non-loopback hosts, the **configured proxy endpoint** (read from the environment, matched by address, never contacted), and `requests.Session.request` itself, while still permitting the JS engine's loopback self-pipe. The request's self-contradicting status line ("1a implemented" beside "no code has been written") is corrected. `--plan` reference extraction stays PLANNED by design and says so.
- Results: `test_m2_smoke.py` **104 cases, 0 unexpected, exit 0** (79 -> 104); `smoke_capture.py --plan` exit 0 with F1-F8 all PASS and nothing written; the unmodified reviewer probe now exits 1 at its first defect assertion (`{'calls': 1, 'retryable': False, 'attempt_classifications': ['error']}`). Accepted suites unchanged and still passing: `test_m2a.py` 79/0, `temporal_contract.py` 13/13, `test_acceptance_gates.py` 46, `test_staging_gate_e2e.py` 67. Production databases unchanged; no `tmp/`, `staging/` or evidence directory; HEAD `73f266d`; index empty.
- Files: `_m2_smoke/smoke_capture.py`, `_m2_smoke/smoke_checks.py`, `_m2_smoke/test_m2_smoke.py` changed; `_m2_smoke/smoke_outcomes.py` added; `_m2_smoke/sina_klc_decoder.py` unchanged. The deliverable is five files, not four, because capture needs the outcome table too.
- Unchanged limitations: the real Sina payload has still never been decoded or replayed - there is no real sample and inventing one would repeat the M2a R1 defect; no strict-PIT evidence; universe / ST / suspension / delist / BJ mapping UNKNOWN; corpus unit evidence UNKNOWN with the 293 STAR-board events still a hypothesis; `identity` the only transformation; A2 and the 746 legacy evaluations a separate prerequisite; `PASS_WITH_DOCUMENTED_BJ_NON_SERVICE` is deliberately not an unqualified PASS and authorizes nothing.
- Not authorized and not done: the five live requests (boundary 1b), evidence retention, the 52-symbol pilot, full-market rebuild, production promotion, training, A2, commits, pushes.


### 2026-09-07 - M2b boundary 1a closure round 3: R1-R4 (Claude)

- State: `ready_for_review`. Boundary 1a only. **1b was not executed**: no network or plugin call, download, real collection, production or runtime change, service operation, Git staging/commit/push, training or promotion. Code confined to `claude methods/_m2_smoke/`; the English M2b request (Section 14, plus its round-2 status line, boundary row and handoff record), this ledger entry and the Section 15 heading/annotation were the only other edits. Accepted M1/M2a imported unmodified and still passing; both reviewer drivers and reports untouched and not adapted to pass; the eight round-2 closures preserved.
- Context: `M2B_1A_CLOSURE_CODEX_REVIEW.md` verified 104 tests and the eight previous scenarios closed, and reproduced four remaining boundary defects. Only those four were changed. The first draft of this closure was then attacked by an independent offline self-review, which reproduced further holes in it; those are fixed here and named below.

| ID | Defect | Closure |
|---|---|---|
| R1 | `cancelled` guarded two manifest helpers while the raw body was written by a bare `Path.write_bytes`; a worker paused there woke after finalization and created an unindexed raw file | an `EvidenceStore` owns the tree: bodies are staged in a sibling `<out_root>.pending/` and published body + record + manifest in one **transactional** critical section (a failing record half returns the body to staging); abandonment is a **store-level refusal** set inside the same critical section that writes the abandonment record, closing the pre-seal window the self-review found on three paths; a second terminal record per request is refused and skips are idempotent; a late call refused before the wire is evidenced as such so the records agree with the transport's own count; the seal is one bounded critical section |
| R2 | the 120 s finalization budget was checked once before an unbounded synchronous cleanup; an overrun that returned was reported `done`/PASS | finalization runs step by step under its own deadline, each supervised; a later step that cannot start is an **overrun** naming that step, not an abandonment; owner writes stage outside the tree and move in under a **guarded** operation with the token re-checked, so an abandoned write cannot land; `keep_raw=False` **detaches** the raw directory instead of deleting inside the tree; retention is one rename with the cross-device fallback removed and a new **F6 same-volume pre-flight**; `exit_code_for` is 0 only when finalization completed within budget |
| R3 | T3 checked only a ceiling and the timestamps of whatever attempts existed, so `attempts=[]` beside five successes validated; the manifest was flushed per retry group | `TimedTransport` is the attempt boundary with `request_index`/`attempt_no` and start/end persistence (the paced sleeper flushes before it waits); `reconcile_attempts` fails closed on empty, missing, truncated, duplicated, misbound, orphaned, unfinished, out-of-order and terminally inconsistent evidence, and - added by the self-review - cross-checks each attempt's classification against the status/error M2a would classify, a failed request's terminal fields against its final attempt, and the genuine in-flight shape; `attempt_positions` is read, not merely written |
| R4 | the job result was the worst row, so a 404 on the auxiliary outstanding-share request became BJ history non-service and produced the BJ-qualified PASS | `aggregate_job` decides by request kind: only the KLC history request's explicit 404/410 yields `NOT_SERVED_AT_PATH`; an absent/failed auxiliary is `INCONCLUSIVE_AUXILIARY` with the history checks still run; **a vendor stop or run abort on the auxiliary stays FAILED** (the self-review caught the first draft softening that reviewed row) and a header-latched 403/429 recorded as `aborted` is still classified `vendor_stop`; a run-global skip is inconclusive with that reason; C2 records `decided_by`, the per-kind summary and `auxiliary_evidence` in both branches |

- Results: `test_m2_smoke.py` **132 cases, 0 unexpected, exit 0** (104 -> 132; the new `K-` regressions drive the real worker, pipeline, transport and check paths); `smoke_capture.py --plan` exit 0 with F1-F8 all PASS and nothing written; the unmodified round-2 driver walks its eight closed scenarios and exits 1 at its first now-closed R1 assertion; the remaining reviewer scenarios were replayed in scratch drivers: overrun -> `incomplete_finalization`/exit 1, `attempts=[]` -> T3 FAIL/capability FAIL on first check and replay, share-endpoint 404 -> `INCONCLUSIVE_AUXILIARY`/INCONCLUSIVE, and the pre-seal wire-call window -> 5 records, no duplicates, nothing published. Accepted suites unchanged and still passing: `test_m2a.py` 79/0, `temporal_contract.py` 13/13, `test_acceptance_gates.py` 46, `test_staging_gate_e2e.py` 67. `git diff --check` exit 0. Production databases unchanged (`trading_local.sqlite3` 1,346,048,000 B / mtime_ns 1788517646307317700; `market_history.sqlite3` 1,234,956,288 B / 1788493486739967200; `-wal` 0 B); no `tmp/`, `staging/`, `*.pending` or evidence directory; HEAD `73f266d`; index empty.
- Files: `_m2_smoke/smoke_capture.py` `b17f8d0d...`, `smoke_checks.py` `b2b8aaa9...`, `smoke_outcomes.py` `53a43019...`, `test_m2_smoke.py` `5cb4cc3e...` changed; `sina_klc_decoder.py` `65992852...` unchanged. Manifest schema `m2b.capture_manifest.v3`.
- Limitations restated: no thread is killed and no process terminated - a refused or revoked worker cannot publish into, write into or clean up the tree, but when its blocked call returns is not controlled; a worker blocked inside one guarded operation completes exactly that one atomic rename and nothing after it; a forced seal lets one in-flight publication complete and reports the run unsealed and not retained; the lock/seal waits are wall-clock, bounded at 30 s each, and not driven by the injected clock; the vendor decode and the adapter replay have never seen a real body; `PASS_WITH_DOCUMENTED_BJ_NON_SERVICE` is reachable only through an explicit 404/410 on the KLC history request and authorizes nothing.
- Not authorized and not done: the five live requests (boundary 1b), evidence retention, the 52-symbol pilot, full-market rebuild, production promotion, training, A2, commits, pushes.


### 2026-09-08 - M2b boundary 1a technically VALIDATED by Codex (offline smoke scope)

- Reviewer verdict: `M2B_1A_ACCEPTANCE_CODEX.md`, 2026-09-08 - **VALIDATED for the offline scope**, evidence assessment "share with caveats". The four blocking findings R1-R4 of `M2B_1A_CLOSURE_CODEX_REVIEW.md` are closed on the reviewed revision and no remaining blocker was found for this bounded stage. **This is a reviewer's technical verdict on boundary 1a only.** It is not user authorization for live work, it does not complete M2, and it establishes nothing about corpus, feature or training readiness.
- Reproduced locally before recording this entry: `test_m2_smoke.py` **132 cases, 0 unexpected, exit 0**; `review_m2b_1a_round3.py` (the reviewer's independent R1-R4 closure probes) **exit 0**; `smoke_capture.py --plan` **exit 0** with F1-F8 PASS and nothing written.
- Frozen revision, unchanged by this entry: `smoke_capture.py` `b17f8d0d...`, `smoke_checks.py` `b2b8aaa9...`, `smoke_outcomes.py` `53a43019...`, `sina_klc_decoder.py` `65992852...`, `test_m2_smoke.py` `5cb4cc3e...`. Accepted M2a pins still match (`943a8c3f...`, `5ec05456...`, `efa46c13...`, `f57bbc6c...`); `_m1_closure/` and all reviewer artefacts untouched (`df22a06f...`, `2a38ba4c...`, `7b200b49...`). Production databases unchanged (`trading_local.sqlite3` 1,346,048,000 B / mtime_ns 1788517646307317700; `market_history.sqlite3` 1,234,956,288 B / 1788493486739967200; `-wal` 0 B); no `tmp/`, `staging/`, `*.pending` or evidence directory; HEAD `73f266d`; index empty.
- Documentation-only changes made in response, with **no source file touched** so the reviewed hashes stay frozen: (a) Section 3 of the request said production's `adjust="qfq"` path *multiplies* the klc OHLC by its factor - it **divides** (`stock_zh_a_sina.py:293-296`), while the **hfq** branch multiplies (`:254-257`) and `adjust=""` applies neither (`:219-232`); the sentence is corrected and the correction is marked. Only the narrative was wrong: B2 has read these three properties out of the installed source since the round-2 closure, and no raw-data basis was reinterpreted to match the old sentence. (b) The **timing restriction is recorded as an operator condition, not a checked gate**: F1-F8 read no clock and the `--plan` output prints no time (verified), so a green pre-flight does not establish timing-window compliance; the operator must verify and record the Asia/Shanghai wall clock immediately before arming, and F8 is passed by the stack already being stopped, never by stopping a service. (c) New Section 15 of the request records the acceptance, the frozen hashes, all four reviewer caveats and the 1b preconditions; the status line, boundary table and handoff record are synchronized.
- **Boundary 1b remains `proposed` and unauthorized, and was not executed.** Passing this review is not the authorization. It needs the user's explicit, separate instruction, which must also settle the evidence-retention choice: whether the captured raw bodies and the minimal frozen reference extract are retained **locally only** under the reviewed evidence directory to permit independent offline replay (the reviewer's recommendation). No Git staging, external upload or production promotion is authorized either way.
- If and when authorized: **one** run of the existing three-symbol smoke - SH600011, SH000300, BJ920000 in the fixed five-request order, at most 15 attempts including per-request retries, concurrency 1, spacing >= 1.5 s, unchanged TLS checks and abort rules - outside continuous trading (before 09:15 or after 15:30 Asia/Shanghai, verified and recorded by hand) and only with a fresh passing pre-flight. No endpoint substitution and no symbol expansion after a failure. Report the process exit code, pipeline summary, retained manifest/checks/report/hashes/frozen reference, the actual request count, duration, failures, coverage and unresolved semantics; repeat the deterministic checks offline from the retained evidence; stop at `ready_for_review` for Codex.
- Carried-forward limitations, unchanged: no real Sina body has ever been decoded or replayed, so decoder behaviour, identity, units, adjustment basis, session coverage and adapter losses are all unproven on live data; cancellation is not thread termination (a worker inside one guarded filesystem operation may finish it, and a forced-unsealed capture is partial and not retained); no strict-PIT evidence; universe / ST / suspension / delist / BJ mapping UNKNOWN; corpus unit evidence UNKNOWN with the 293 STAR-board events still a hypothesis; `identity` the only transformation; A2 and the 746 legacy evaluations a separate prerequisite; `PASS_WITH_DOCUMENTED_BJ_NON_SERVICE` is reachable only through an explicit 404/410 on the KLC history request and authorizes nothing.
- Not authorized and not done: the five live requests, evidence retention, the 52-symbol pilot, full-market rebuild, basis labelling, production writes, service operations, training, A2, commits, pushes.


### 2026-09-08 - M2b boundary 1b executed once; capability FAIL; two defects found (Claude)

- Authorization: the user authorized **exactly one** boundary 1b smoke run on 2026-09-08 for `SH600011`, `SH000300` and `BJ920000`, with raw responses and the minimal frozen reference extract retained **locally only**. Executed once, run_id `20260908T021722Z`. Evidence: `claude methods/_m2_smoke/evidence_20260908T021722Z/`. Stopped at `ready_for_review` for Codex. Nothing committed, pushed, staged, promoted or trained; no service started or stopped; no production database written; no endpoint substituted; no symbol added. The authorization is now spent.
- **The timing condition was NOT satisfied.** Verified immediately before arming: 2026-09-08 **10:17:14 Asia/Shanghai (Tuesday)** - inside continuous trading, so outside the permitted before-09:15 / after-15:30 window. I reported the violation and recommended holding ~5 h 20 m for the window; the user explicitly chose to run anyway. Observed consequence in this capture: none visible - both decoded series end at 2026-09-07, the previous session, with no partial bar for the in-progress session. That is one observation on two symbols, not a rule.
- Wire result: **2 HTTP attempts of a 5-request plan** (ceiling 15), 0 retries, starts 0.000 s and 1.500 s apart with a 1.203 s pacing sleep inserted; capture 1.97 s of the 900 s deadline; finalization 0.109 s of 120 s, completed; process exit code 1. Requests 1 and 3 (the KLC history endpoints for `sh600011` and `sh000300`) returned **HTTP 200** with real bodies of 73,353 and 100,465 bytes (`application/x-javascript`, gzip, `Tengine`); both classified `undecodable`, which skipped request 2 job-locally and then aborted the run on "2 consecutive failed jobs" before the BJ job. **`BJ920000` was never contacted**, so C2 and the amount/outstanding-share separation are unanswered. Verdicts: `sh600011` INCONCLUSIVE, `sh000300` INCONCLUSIVE, `bj920000` FAIL, **capability FAIL**. Every evidence gate (EV0, EV2, EV3, EV4, EV5) and T1/T2/T3 passed; the failure is S2 on both bodies.
- **D1 - the decoder is too strict for the real body; our defect, not the vendor's.** `extract_payload`'s regex requires the body to END at the assignment, but the real body is `var NAME="<payload>";` followed by a `/* ... */` trailer (281 and 308 chars). The synthetic envelopes never had a trailer, so no offline test could have caught it. The installed adapter's own positional extraction returns exactly the right payload on both bodies (verified byte for byte against the retained evidence), so the adapter would have decoded them; the stricter cross-check rejected the whole body.
- Offline analysis of the retained bytes (read-only, not a check result): both payloads decode with the **pinned** routine. `sh600011` selects branch **O** (3466), 5,935 rows **2001-12-06** (its listing date) to 2026-09-07, keys `date/open/high/low/close/volume/amount/prevclose` plus `postVol`/`postAmt`; `sh000300` selects branch **D** (1479), 5,987 rows 2002-01-04 to 2026-09-07, **no `amount`**. Both strictly increasing with no duplicates and exactly one row after 2026-09-04. This matches Section 10's stated expectations, but identity, units, basis and coverage remain **unverified** because the required checks never ran.
- **D2 - pre-flight F8 fails OPEN on this machine, and always has.** `default_process_lister` decodes the PowerShell inventory strictly as UTF-8 (`text=True`); this machine's inventory contains byte `0xb9`, the reader thread dies, `stdout` is empty, `json.loads(... or "[]")` yields `[]`, F8 matches nothing and reports PASS. The manifest records `process_inventory_size: 0` while a decode-tolerant repeat sees **289 processes**, so F8's PASS **in this run** is vacuous. **Correction (2026-09-08, after `M2B_1B_CODEX_HANDOFF.md`):** an earlier version of this entry also claimed every historical `--plan` F8 PASS on this machine was vacuous. That is withdrawn as unsupported - the failure is condition-dependent (it needs an undecodable byte to be present in the inventory at that moment), it did not reproduce in Codex's probe, which saw 293 processes with no Unicode error, and the retained `plan.txt` records no inventory size, so past outputs cannot settle the question either way. Independently checked decode-tolerantly after the run: **0 genuine project-stack processes** were running, so the stack really was stopped and the run was not compromised, but F8 did not establish that.
- Neither defect was fixed: both are code changes outside this authorization, and the five reviewed hashes stay frozen for Codex (`b17f8d0d...`, `b2b8aaa9...`, `53a43019...`, `65992852...`, `5cb4cc3e...`, all verified unchanged after the run).
- Offline replay from the retained evidence reproduced the deterministic block **byte for byte** (`02e1b764...`, `matches_stored: True`) under `db_guard`, with no production database opened; `R1urls` PASS. The per-symbol `R1` adapter replay did not run because no job had all its requests served.
- State after the run: production metadata unchanged (`trading_local.sqlite3` 1,346,048,000 B / mtime_ns 1788517646307317700; `market_history.sqlite3` 1,234,956,288 B / 1788493486739967200; `-wal` 0 B); `invalidating_changes: []`, `run_valid: true`; the run's `tmp/m2b_smoke_20260908T021722Z/` removed and no `*.pending` left (`tmp/` present and empty); no `staging/`; HEAD `73f266d`; index empty; `test_m2_smoke.py` still 132 cases, exit 0.
- Established by this run: the live transport, TLS path, pacing, attempt accounting, outcome table, evidence store, finalization, retention and deterministic replay all work on real traffic, and the vendor serves full decodable history for `SH600011` and `SH000300` at the reconfirmed URLs. Not established: identity, units, adjustment basis, session coverage, adapter losses, the amount/outstanding-share separation, and anything at all about `BJ920000`. Nothing advances the 52-symbol pilot, the basis label, the corpus, production promotion or training.
- Recommended next step, for the user and Codex to decide and **not** taken here: fix D1 (accept a trailing comment while keeping the adapter cross-check) and D2 (read the inventory as bytes, decode tolerantly, and fail **closed** when it cannot be read), add regressions built from the retained real bodies, then consider a second authorized run inside the timing window.


### 2026-09-08 - M2b D1/D2 offline corrections; original 1b FAIL preserved (Claude)

- Trigger: `M2B_1B_CODEX_HANDOFF.md`. Codex verified the retained failure evidence and reproduced the FAIL exactly; **source-capability acceptance remains FAIL**. Scope here is bounded offline corrections only: no live call, production write, service operation, commit, push or training, and no new capture is authorized.
- **Original evidence immutable.** `evidence_20260908T021722Z/` was verified byte-identical (7 files) before and after this work; its manifest, `checks.json` and FAIL are untouched. Revised results live in a separately named directory, `revision_20260908T021722Z_d1d2/`.
- **D1 - bounded trailer support.** The extractor required the body to END at the assignment, so both retained real bodies were rejected. The real grammar is `var NAME="<payload>";` followed by a non-executable `/* ... */` block (281 and 308 chars). Fixed with a **scanner, not a looser pattern**: the assignment is still matched strictly and anchored, and the remainder is walked accepting only whitespace and **closed** block comments, bounded at 8,192 chars and 8 comments. A second statement, another assignment, a bare identifier, a call, a line comment, an unterminated comment or an oversized trailer are all refused. Strict bytes-to-text, dual-extraction agreement, the pinned routine hash and all payload/row/JS limits are unchanged; raw downloaded JavaScript is still never evaluated. On the retained bodies: `sh600011` branch O, 5,935 rows, `amount` present; `sh000300` branch D, 5,987 rows, no `amount`.
- **D2 - fail-closed inventory and accurate recognition.** Three defects closed. (i) The lister swallowed every failure into `[]`; it now raises `InventoryUnavailable` on non-zero exit, blank output, strict-decode failure, invalid JSON, a non-list, an **empty** list, or a record missing `ProcessId`/`CommandLine`, and F8 fails on each - an empty inventory is a failed query, not an idle machine. (ii) The producer now states its own encoding and the parent decodes bytes strictly as `utf-8-sig`; lossy replacement is explicitly not the fallback, because a mangled command line could hide a running worker. (iii) Recognition is structural, not substring: `classify_process` tokenizes the command line, honours quoting and stops at the first inline-program flag (`-c`, `-Command`, `-EncodedCommand`), so a shell quoting the names is not mistaken for one running them. It recognises `python -X utf8 -m uvicorn app.main:app` (the form `run_stack.ps1:338` uses, which the old `uvicorn\b.*backend` regex could not match), any `backend/scripts/*.py` worker, `node .../vite/bin/vite.js`, `npm run dev`, and `run_stack.ps1`/`ensure_stack.ps1`. A stack-image process with an **unreadable** command line is `ambiguous` and fails F8: unproven absence is not absence.
- A regression asserts no smoke code path contains `Start-Process`, `Stop-Process`, `taskkill`, `os.kill`, `terminate()` or a service verb, and that the only subprocesses launched are `git`, `ps` and `powershell`. Another drives the real `capture()` with an unavailable inventory and a transport that raises if called: `PreflightError` naming F8, transport never invoked, no `tmp/` and no evidence directory created.
- Results: `test_m2_smoke.py` **146 cases, 0 unexpected, exit 0** (132 -> 146; 14 new `L-` regressions, five of them driven by the retained real bodies referenced by SHA-256 so a substituted file fails rather than passes). Unchanged and still passing: `test_m2a.py` 79/0, `temporal_contract.py` 13/13, `test_acceptance_gates.py` 46, `test_staging_gate_e2e.py` 67. The unmodified reviewer driver `review_m2b_1b.py` now exits 1 at `matches_stored is True`, and its D2 assertions now describe closed defects.
- Changed hashes: `sina_klc_decoder.py` `6599285a...` -> `d39e02c8...`; `smoke_capture.py` `b17f8d0d...` -> `fadcaf3c...`; `test_m2_smoke.py` `5cb4cc3e...` -> `748b5131...`. `smoke_checks.py` `b2b8aaa9...` and `smoke_outcomes.py` `53a43019...` unchanged. Accepted M1/M2a artefacts and all historical reviewer scripts untouched.
- Revised offline pass (`revision_20260908T021722Z_d1d2/`), same retained bytes, corrected code: **capability FAIL, deliberately**. `sh000300` now passes every required semantic check - D1-D4, I2 (close ratio in tolerance over 10 sessions), I3 (volume ratio ~ 1), C3 (2002-01-04 .. 2026-09-07, span complete) and **R1, the installed adapter replayed on the real body, 5,987 rows, 0 fabricated dates**. The run still fails correctly: EV6 reports the capture recorded both bodies as `undecodable` while the retained bytes now classify as `decoded`; T3 refuses the skip of request 2 whose trigger no longer exists; `sh600011` and `bj920000` never had all their requests issued. **The original run is not retro-promoted**; a capability PASS needs a new authorized capture.
- Provenance: the deterministic block depends on the retained bytes AND the implementation reading them, so the corrected code yields `784ffa66...` instead of `02e1b764...` and `matches_stored: False`. The original hash stays reproducible against the frozen pre-fix implementation, whose five SHA-256s are recorded beside the new ones in the revision's `PROVENANCE.json`.
- Receipts: `receipts_20260908T021722Z/` preserves the original 1b console receipts byte for byte with their original mtimes - stdout (the source of exit code 1 and the 0.109 s finalization figure), stderr (the two `UnicodeDecodeError` tracebacks), the shell `EXIT_CODE` line, the task output line, and the pre-execution Asia/Shanghai clock verification recording the timing **violation**. Nothing reconstructed or backdated; the user's authorization and out-of-window waiver were given in conversation and are referenced, not reproduced. That waiver is **not** standing permission for another out-of-window run.
- **Correction carried into the earlier entries:** the claim that every historical `--plan` F8 PASS on this machine was vacuous is **withdrawn as unsupported**. The failure is condition-dependent, it did not reproduce in Codex's probe (293 processes, no Unicode error), and the retained `plan.txt` records no inventory size, so past outputs cannot settle it. What is established is this run's `process_inventory_size: 0` and that F8 could fail open at all.
- Still not established: no new live evidence; `BJ920000` never contacted; identity, units, basis, coverage and adapter losses for `SH600011` unverified because its auxiliary request was never issued; source-capability acceptance **FAIL**. Not authorized and not done: any further live run, the 52-symbol pilot, basis labelling, production writes, service operations, commits, pushes, training.


### 2026-09-08 - M2b D2 process-gate closure: seven F8 false passes (Claude)

- Trigger: `M2B_D1D2_CODEX_REVIEW.md` - **D1 validated**, D2 changes requested after seven independently reproduced F8 false passes, each driven through the real `preflight()`. All seven are closed in the three bounded groups the review defined. Offline only: no live capture, production database operation, service action, 52-symbol work, Git staging/commit/push or training. D1, accepted M1/M2a, the sealed 1b evidence and its FAIL, the receipts and every reviewer script are unchanged. **M2b source-capability acceptance remains FAIL** and no new capture is authorized.
- **P1a - incomplete or unidentifiable records.** `cmdline_available` was `command is not None`, so an empty or whitespace-only command line counted as evidence, and a record with no `Name` and a null `CommandLine` was classified unrelated. `_normalize_inventory` now marks a blank command line unavailable and rejects non-string `Name`/`CommandLine`; `classify_process` treats blank as missing, and a record with neither a usable name nor a readable command line is `ambiguous`. The legitimate `System`/`Registry` null-command records still classify as unrelated.
- **P1b - backend-relative worker paths.** The matcher required `backend/scripts/` in the command line, so `python.exe -X utf8 scripts\control_plane_loop.py` - the same script started from the backend working directory - read as a stopped machine. Recognition is now by basename against the ten known entrypoints `run_stack.ps1` starts, in absolute, backend-relative or bare form, with the absolute `backend/scripts/*.py` rule kept for anything not on the list. The interpreter identity check still stops an editor or a grep naming those files from matching.
- **P1c - inline execution treated as discussion.** Everything after `-c`/`-Command` was discarded, removing real launches along with innocent quoted text; `python -c "import uvicorn; uvicorn.run('app.main:app', ...)"` runs the API inside that same process. `_inline_verdict` now reads (never evaluates) the inline program, bounded at 4,096 chars, and returns `stack` on a recognised launch shape naming a stack target, `other` when the target appears only in a literal `print(...)` or a read-only PowerShell listing verb, and **`ambiguous`** in any other shape - so an unresolved relevant launch fails closed. The comment claiming inline code is necessarily only talking about a launch is gone; it was the assumption behind the defect.
- The `no code path starts or stops a process` regression began failing when `Start-Process` entered the source as a **detection pattern**. It was tightened, not relaxed: `taskkill`, `os.kill`, `terminate()` and service verbs stay banned as text; `Start-Process`/`Stop-Process` are allowed only on a `re.compile(...)` line or in a comment, never in an executed string; the only subprocesses remain `git`, `ps`, `powershell`; and the one PowerShell program executed is asserted free of mutating verbs. No test launches or stops anything - every process record is synthetic.
- Results: `test_m2_smoke.py` **158 cases, 0 unexpected, exit 0** (146 -> 158; 12 new `M-` regressions covering all three groups, the exact seven reviewer counterexamples, and a capture-refusal proof). The **unchanged** reviewer driver `review_m2b_d1d2.py` now reports **55 checks, 55 passed, 0 failures, exit 0** (was exit 1, 48/55). Unchanged and passing: `test_m2a.py` 79/0, `temporal_contract.py` 13/13, `test_acceptance_gates.py` 46, `test_staging_gate_e2e.py` 67.
- Changed hashes: `smoke_capture.py` `fadcaf3c...` -> `37942c38...`; `test_m2_smoke.py` `748b5131...` -> `4103f03b...`. `sina_klc_decoder.py` `d39e02c8...` (D1, untouched), `smoke_checks.py` `b2b8aaa9...` and `smoke_outcomes.py` `53a43019...` unchanged. The revision directory was regenerated so its declared pins match the code that produced it; its result is identical (`784ffa66...`, capability FAIL), confirming the D2 change touches only the pre-flight. Sealed original evidence verified byte-identical, 7 files.
- Documentation notes closed: `PROVENANCE.json` now states that old-code replay is **currently unverified by me** - a digest identifies content without preserving it, and this workspace holds no artifact of the pre-fix sources, so `02e1b764...` cannot be reproduced here; nothing was reconstructed or backdated, and Codex's earlier verification of that replay stands on its own record. The test docstring no longer claims there is no real sample: it names the two pinned real bodies and states they establish decoder grammar on two symbols for one day, not the live path, the semantic checks or a corpus.
- Remaining limitations: F8 inspects a snapshot and proves nothing about what ran before or after; recognition is bounded pattern matching over known launch shapes, so a launch obfuscated beyond them lands in `ambiguous` if it names a stack target and in `other` if it does not - a deliberate residual gap preferred over a shell parser; `ambiguous` failing F8 means an unrelated process naming a stack target in an unrecognised shape blocks a run until it exits; on this machine the corrected gate currently reports F8 PASS with 283 processes inventoried, zero recognised and zero unreadable relevant, which is one observation and not certification.
- Not authorized and not done: another boundary-1b run (a fresh one-run user authorization is required after this safety review closes), the 52-symbol pilot, production writes, service operations, commits, pushes, training.


### 2026-09-08 - M2b D2 literal-program boundary closed (Claude)

- Trigger: `M2B_D2_LITERAL_BOUNDARY_CODEX_REVIEW.md`. The earlier seven F8 counterexamples are confirmed closed and D1 remains validated; one boundary remained - the harmless-program exception proved nothing about the WHOLE program, so three executable programs were accepted as harmless and one literal print was misread as a launch. All four fixed, nothing else touched. Offline only: no live capture, production database operation, service operation, pilot collection, Git staging/commit/push or training. **Source-capability acceptance remains FAIL.**
- The defect: `_PY_LITERAL_ONLY` was `^\s*(print|repr|str)\s*\(.*\)\s*;?\s*$` with a greedy `.*`, so a program merely STARTING with a print satisfied it; `_PS_LISTING_ONLY` inspected only the first verb. Both were **replaced, not reordered** - the review was explicit that swapping order would not do, because the harmless rules were themselves unsound.
- Python now uses a bounded **AST shape proof**: every statement must be an expression statement calling `print`/`repr`/`str`/`len`/`format` by bare name with literal arguments only (bare literals allowed), under a 400-node cap. An import, assignment, loop, attribute call, name argument, comprehension or syntax error is not inert. Parsing is not evaluation, and a regression proves it by handing the checker a program whose execution would create a file and asserting the file never appears.
- PowerShell now requires **one complete simple read-only command**: the program is refused outright if it contains `; | & backtick { } ( ) $ > <` or a newline, then the first token must be a known read-only verb and every remaining token a literal. A refusal rule, not a shell parser.
- Order matters and is now correct: inertness is established FIRST over the whole program, and the invocation patterns - which are substring searches and cannot tell a call from the same characters inside a string literal - are consulted only afterwards. A relevant program that is neither proven inert nor a recognised launch is **ambiguous**, which fails F8.
- The four counterexamples now resolve as required: `print('uvicorn.run(app.main:app)')` PASS (`other`, provably inert); `print('starting'); from uvicorn import run; run('app.main:app')` FAIL (`ambiguous`); `Get-Item .; python.exe scripts/control_plane_loop.py` FAIL (`ambiguous`); `Get-Item $(python.exe scripts/control_plane_loop.py)` FAIL (`ambiguous`).
- Results: `test_m2_smoke.py` **165 cases, 0 unexpected, exit 0** (158 -> 165; 7 new `N-` regressions). The **unchanged** driver `review_m2b_d2_literal_boundary.py` now reports **8 checks, 8 passed, exit 0** (was exit 1, 4/8). Unchanged and passing: `test_m2a.py` 79/0, `temporal_contract.py` 13/13, `test_acceptance_gates.py` 46, `test_staging_gate_e2e.py` 67.
- **One expected cross-version mismatch, reported not fixed:** `review_m2b_d1d2.py` now exits 1 at 54/55 on `revision implementation matches declared pins`, because that assertion compares current sources against the producer pins declared by the sibling `..._d1d2` revision and those sources changed for this fix. Per the reviewer's clarification this is version-specific, not functional; no evidence directory, revision or reviewer script was edited to make it green.
- Changed hashes: `smoke_capture.py` `37942c38...` -> `0ed93f05...`; `test_m2_smoke.py` `4103f03b...` -> `d14a4f98...`. `sina_klc_decoder.py` `d39e02c8...` (D1), `smoke_checks.py` `b2b8aaa9...` and `smoke_outcomes.py` `53a43019...` unchanged.
- Provenance: the offline re-check went into a **new** directory `revision_20260908T021722Z_d2_literal/` naming its own producer hashes and parent evidence; the sealed original evidence (7 files) and the sibling `..._d1d2` revision (7 files) were both verified unchanged afterwards. Its result is again `784ffa66...`, capability FAIL, confirming this change touches only the pre-flight.
- **Honest record of the earlier overwrite:** on 2026-09-08 I regenerated `revision_20260908T021722Z_d1d2/` in place so its declared pins matched the producing code, overwriting its `PROVENANCE.json` and `checks.json` and rewriting the rest from the sealed parent. The preservation boundary asked for that revised evidence to stay unchanged and I crossed it. **No pre-overwrite artifact exists** - nothing was copied aside, nothing committed - so there is no locator, and it is deliberately not reconstructed or backdated. What is known is only what was recorded before it happened: the same deterministic result `784ffa66...` with capability FAIL, and pins naming `smoke_capture.py` `fadcaf3c...` and `test_m2_smoke.py` `748b5131...`. The sealed original evidence was never touched.
- Remaining limitations: inertness proves a narrow shape, not general harmlessness - anything outside it is `ambiguous` rather than allowed, at the cost of blocking a pre-flight until such a process exits; a `bash -c` program is still classified only by its argument vector, so a launcher hidden in one would be missed (unchanged by this fix, out of its scope); F8 remains a snapshot and says nothing about what ran before or after; and no new live evidence exists, `BJ920000` has never been contacted, and `SH600011`'s identity, units, basis, coverage and adapter losses are unverified because its auxiliary request was never issued.
- Not authorized and not done: a new boundary-1b run, the 52-symbol pilot, production writes, service operations, commits, pushes, training.


### 2026-09-08 - M2b D1/D2 offline corrections technically VALIDATED by Codex; one new 1b run requested (Claude)

- Reviewer verdict: `M2B_D2_ACCEPTANCE_CODEX.md`, 2026-09-08 - **validated within the bounded offline D1/D2 correction scope**. The seven earlier F8 counterexamples and the four literal-boundary counterexamples are closed with no blocking defect found. **This is not M2b source-capability acceptance, which remains FAIL**, and it is not user acceptance. The correction loop is closed; no further classifier redesign is requested.
- Reviewer's runs: `test_m2_smoke.py` 165 cases exit 0; `review_m2b_d2_literal_boundary.py` 8/8 exit 0; `review_m2b_d2_final.py` 32/32 exit 0; `review_m2b_d1d2.py` 54/55 exit 1 - the single **expected** cross-version producer-pin mismatch, confined to `smoke_capture.py` and `test_m2_smoke.py`, not a functional failure and not made green by editing evidence or drivers. The suites overlap deliberately and are not summed.
- Locally reconfirmed before recording: all five accepted pins match, the new revision's two anchors match, `test_m2_smoke.py` 165/0 exit 0, both current drivers exit 0, `--plan` F1-F8 PASS with 277 processes inventoried and all classified.
- **Reviewed implementation frozen locally** at `_m2_smoke/frozen_impl_20260908_d1d2_accepted/`: byte-for-byte copies of the five validated files, hash-verified before and after the copy, with a `MANIFEST.json` of digests, sizes and original mtimes. Untracked and never staged; source files only - no credentials, private files, datasets, production databases, evidence or revisions. It exists because a hash identifies content without preserving it, which is how the earlier revision's pre-overwrite provenance became unrecoverable.
- Section 19's limitation wording was narrowed per the acceptance's caveat 1: it now says an **unproven relevant** program is `ambiguous`, and states explicitly that a program naming no stack target returns `other` without any inertness proof, that F8 is a point-in-time check of known visible launch forms rather than a sandbox or writer lock, and that bash, encoded/obfuscated launches and code with no recognisable target marker are not certified by it.
- **Prepared, not executed: a request for ONE new boundary-1b run** (Section 20 of the request). Same five requests, same job order, endpoints derived at run time from installed akshare 1.18.64; unchanged limits - 15-attempt ceiling, 1 concurrent, >= 1.5 s pacing on actual wire starts, connect 10 s / read 30 s, <= 3 retries with 2 s/8 s backoff and never on TLS, 403/429 latched at the headers, 2-consecutive-failed-job stop, 15-minute end-to-end deadline, redirects disabled, TLS pinned to certifi in `backend/.venv`, 8 MiB/32 MiB caps. Fresh `run_id` and fresh paths: `tmp/m2b_smoke_<new_run_id>/` during the run and `_m2_smoke/evidence_<new_run_id>/` at cleanup; `20260908T021722Z` is never reused and every existing evidence, receipt, revision and frozen directory is preserved untouched, with the original FAIL and `02e1b764...` standing as that run's record.
- The request states the operator timing condition (before 09:15 or after 15:30 Asia/Shanghai, clock verified and recorded immediately before arming, with a green pre-flight explicitly not establishing it), the fresh F1-F8 requirements including a complete decodable non-empty inventory with no known launch form and no unresolved relevant process, the read-only reference scope (`trading_local.sqlite3` `daily_bar_cache` only, `mode=ro` + `query_only`, read once at F2 and frozen; `market_history.sqlite3` never opened; replay under `db_guard`), and the four open questions the run should answer: whether the corrected decoder works on live bytes end to end, `SH600011` semantics that depend on the never-issued request 2 (I2/I3/U2/U3/D5/C4/R1/C1), `BJ920000`'s completely unanswered C2 classification, and whether `d=2020_2_4` bounds the index history (C3).
- **Preparation only. Nothing is armed.** The 2026-09-08 authorization was consumed and the reported out-of-window waiver is not standing permission. Awaiting fresh one-run user authorization plus the retention choice before any clock check or arming.
- Not authorized and not done: any live HTTP, production database operation, service action, 52-symbol pilot, Git staging/commit/push, training.


### 2026-09-08 - ONE boundary-1b run AUTHORIZED by the user; held for the timing window (Claude)

- The user authorized **exactly one** boundary-1b run on the Section 20 plan - unchanged five requests, job order, endpoints, 15-attempt ceiling, pacing, timeouts, TLS and abort rules - with the raw bodies and the frozen reference extract **retained locally only** under a new evidence directory. Given in conversation in answer to an explicit question from me; this entry is my account of it, not the instruction itself. It covers one run and nothing further.
- **Nothing was armed.** At the moment of authorization the Asia/Shanghai clock read **2026-09-08 13:23 Tuesday** - inside continuous trading, so the operator timing condition was not satisfied. Offered the choice, the user elected to **hold** rather than run out-of-window or have me wait unattended, and will re-trigger after **15:30 Asia/Shanghai** (or before 09:15 on a later day). Deliberately the opposite of the 10:17 out-of-window run earlier that day.
- On re-trigger, in order: verify and record the Asia/Shanghai wall clock and abort if outside the window; `--plan` with F1-F8 green in-process; arm once with a **fresh** UTC `run_id` and fresh paths (`tmp/m2b_smoke_<run_id>/`, `_m2_smoke/evidence_<run_id>/`); retain evidence locally; offline replay; stop at `ready_for_review`. `20260908T021722Z` is not reused and every existing evidence, receipt, revision and frozen directory stays untouched. A failed pre-flight - including an ambiguous process record - refuses before any HTTP call, and is reported rather than cleared.
- Unchanged: M2b source capability remains **FAIL**; D1/D2 are technically validated for the offline scope only. Not authorized: a second run, the 52-symbol pilot, production writes, service operations, Git staging/commit/push, training.


### 2026-09-08 - Boundary-1b execution preparation completed; window closed, nothing armed (Claude)

- **No live request was issued.** Clock verified independently at **2026-09-08 13:31:41 Asia/Shanghai** (05:31:41 UTC) - inside continuous trading, so the approved window was **closed** and nothing was armed. Codex's own check at 13:27:38 agreed. The window opens at 15:30 Asia/Shanghai.
- Verified and standing: the Section 20 one-run authorization is **unused** (no new evidence directory, no `tmp/m2b_smoke_*` tree, no `.pending` sibling, no run_id minted); the frozen bundle `frozen_impl_20260908_d1d2_accepted/` matches its accepted pins **and** the live sources still match the same pins; `evidence_20260908T021722Z/`, both revision directories and `receipts_20260908T021722Z/` are untouched against their anchors.
- The 165-case suite and reviewer drivers were **not** re-run: the sources are unchanged since they last passed this session, and re-running them would add no evidence.
- Added Section 21 of the request, the genuinely outstanding preparation: (a) a nine-step **execution checklist** for the moment of arming - clock, authorization still unused, source-integrity re-verification against the frozen pins, `--plan` with F1-F8 green and the five URLs matched, fresh UTC run_id, arm once with in-process F1-F8, retain locally, offline replay, report and stop - with every failure stopping the run rather than being worked around; (b) an inventory of what the run must answer, **derived from the sealed `checks.json`** rather than assumed; and (c) the ten-part structure the 1b acceptance report needs so Codex can decide source capability.
- The derived inventory of unanswered checks: **never produced for any symbol** - `D5`, `U1`, `U2`, `U3`, `U4`, `C1`, `C4`; **produced for `sh000300` only**, and only in the corrected offline re-check rather than in flight - `D1`-`D4`, `I2`, `I3`, `R1`, `C3`, `B3`/`B4`; **`sh600011`** has transport-level checks only (`EV2`, `S1`, `T1`, `T2`) plus the `EV6` FAIL recording that the capture called the body undecodable while the retained bytes decode; **`bj920000`** has nothing but a `C2` FINDING recording that it was never contacted.
- Scope unchanged: D1/D2 remain technically validated for the offline scope only, **M2b source capability remains FAIL**, and the authorization still covers exactly one run on the unchanged plan.
- **Stopped in a ready-to-run state.** No timer, background job or automatic resumption exists; a later user re-trigger is required at or after 15:30 Asia/Shanghai (or before 09:15 on a later day), at which point the checklist begins at step 1.
- Not authorized and not done: any live HTTP, production data write, service launch, 52-symbol pilot or three-year collection, training, Git staging/commit/push, or any change to existing evidence. Live trading remains disabled.


### 2026-09-08 - Boundary-1b run 2 executed IN WINDOW; capability FAIL; BJ and stock semantics answered (Claude)

- The authorized single run was executed once as `20260908T082833Z`. **All four gates passed before arming**: Asia/Shanghai clock **16:27:57** (after 15:30, window OPEN, recorded); the authorization confirmed unused; all five live sources matching the frozen accepted pins; a fresh `--plan` with F1-F8 all PASS and the five printed URLs matching the Section 20 table. (**Correction:** that standalone `--plan` reported 280 inventoried processes; the run's own in-process F1-F8 recorded **279**, the number in the retained `plan.txt` and manifest. Two snapshots seconds apart; 279 is the capture's inventory.) Exit code 1. Evidence at `_m2_smoke/evidence_20260908T082833Z/`, retained locally only.
- **All five requests were issued**, all HTTP 200: 73,353 / 1,108 / 100,465 / 16,057 / 1,705 bytes. **5 attempts of a 15 ceiling, zero retries**, wire starts 0.000/1.515/3.015/4.515/6.015 s - a 6.015 s first-to-fifth span, matching the corrected >= 6 s floor. Run consumed 7.5 s of the 900 s deadline; finalization 0.594 s of 120 s. `run_status: completed`, `run_valid: true`, no invalidating changes.
- **`BJ920000` answered for the first time.** C2 = **`pre_boundary_history_served`**: the vendor does serve pre-2024-08-13 history under the `92xxxx` code - 1,393 rows, branch O, `C2span` PASS. This settles the manifest's "mapping unknown" note and the expected keys of the seven `bj_code_history` symbols.
- **`SH600011` stock semantics measured, not assumed**: `U2` volume unit **share**; `U3` amount ratio **~1.00** (yuan, no 万元 scaling); `I3` volume ratio **~100**, confirming the cache stores 手 while the vendor serves 股; `I2` close ratio in tolerance over 10 sessions; `C1` coverage **first 2001-12-06 (its listing date) to 2026-09-07, span complete**; `U1`/`D2`/`D3`/`D4` PASS; `C4` 0 duplicate OHLCVA rows. `BJ920000` independently reproduces `U2`, `U3`, `I2`, `I3`. `SH000300` passes `D1`-`D4`, `I2`, `I3`, `C3` **in flight**.
- **Capability FAIL**, per job `sh600011` FAIL / `sh000300` INCONCLUSIVE / `bj920000` FAIL, on three defects - all ours, none fixed this turn because a one-run authorization covers the run and its report, not a new correction round:
  1. **The outstanding-share payload is a list of OBJECTS, not pairs**: `[{"date":"2001-12-06","amount":14660.5}, ...]` behind an XSS-guard comment `/*<script>location.href='//sina.com';</script>*/`. `parse_outstanding_share` expects `[[date, value], ...]`. Note the vendor names that field **`amount`** while it is outstanding shares in 万股 - exactly the G3 mislabel this project has warned about since the plan, now confirmed in live data. Consequence: `S2` FAIL on requests 2 and 5, `D5` INCONCLUSIVE, `U4` not computable, per-symbol `R1` INCONCLUSIVE.
  2. **`D1`'s JS-variable check false-FAILs on the stock prefix**: the variable is `KLC_K2_sh600011`, digit extraction yields `2600011` (the `2` from `K2`), which is not a substring of `sh600011`, so it FAILs a body it had just decoded (5,935 rows, branch O). The index form `KLC_KL_sh000300` yields `000300` and passes, which is why no earlier run exposed it.
  3. **The `R1` replay harness passes empty start/end dates**: it calls `stock_zh_a_daily(symbol, "", "")`, so the adapter reaches `temp_df["":""]` on a `DatetimeIndex` and raises `TypeError`. Our call site, not an adapter defect.
- The `INCONCLUSIVE_AUXILIARY` rollup behaved exactly as the R4 work intended: history served and decoded, auxiliary request unusable, and that is not allowed to become a PASS.
- Offline replay reproduced the deterministic block byte for byte - `8ffb30b06a70aee4d301f4d7cea53c34e0ea8374dc0587d69b8848cb4f2ed5c2`, `matches_stored: True` - under `db_guard`, no production database opened.
- Preservation verified after the run: `evidence_20260908T021722Z/` unchanged (still capability FAIL, raw bodies `adc5a391...`/`ef2180be...`), both revision directories unchanged, receipts unchanged, the frozen implementation bundle unchanged, production metadata unchanged, `tmp/` run tree and `.pending` removed at cleanup, nothing staged, HEAD `73f266d`.
- Established: the corrected decoder works on live bytes end to end; the full pipeline ran a complete five-request capture; `BJ920000` serves pre-boundary history; `SH600011` identity, unit, currency and coverage are measured. Not established: anything needing the outstanding-share series (`D5`, `U4`) or the adapter replay (`R1`), and therefore **source capability, which remains FAIL**.
- **The authorization is now consumed.** No second run is authorized. Not done: production writes, service operations, 52-symbol pilot, basis labelling, Git staging/commit/push, training.


### 2026-09-08 - R2-A/B/C offline corrections; capability still FAIL on the EV6 provenance gate (Claude)

- Trigger: `M2B_RUN2_CODEX_REVIEW.md`. The five-request capture is independently reproducible; source capability remains FAIL and its one-run authorization is consumed. **No further capture was made.** Offline only: no network call, production write, service change, pilot expansion, training, staging, commit or push. Both capture directories, both earlier revisions, both receipt sets, the frozen bundle and every reviewer script are unchanged.
- **R2-A** - the auxiliary bodies are arrays of **objects** behind an XSS-guard comment, parsed as data and never executed; the variable name is bound to the expected exchange and symbol; dates, schema and numerics validated. Confirmed on the retained bodies: **26** entries for SH600011, **42** for BJ920000. The vendor's `amount` field is outstanding shares in 万股, not traded amount (`stock_zh_a_sina.py:207-208` multiplies by 10,000 and divides volume by it), and is renamed `outstanding_share_wan` at the boundary with the conversion constant recorded. **Zero policy**: BJ's 2015-03-06 and 2015-09-15 zeros are **kept**, flagged `usable: False` with a reason, and never used as a denominator - nothing fabricated, nothing dropped, no division by zero; a **negative** count is impossible rather than uninformative and is refused. The series is a step function, so `outstanding_share_as_of` carries the last usable value **forward and never backfills**, matching the adapter's `ffill`; `share_series_quality` reports in-window versus pre-window entries and every unusable row separately. SH600011 has **zero in-window entries** (last observation 2019-10-15) yet a well-defined value in force, so `U4` moved from exact-date matching - which reported "0 common dates" - to as-of alignment, now covering **728 research rows** for both stocks with 0 lacking an applicable observation - and reporting the DENOMINATOR AGE, because "0 exceed 100%" would otherwise read as a fresh measurement: SH600011 resolves every in-window row to the single 2019-10-15 observation (median 1,975 days, max **2,516 days = 6.9 years**), while BJ920000 is median 173 / max 511.
- **R2-B** - observed grammar across every retained body of both captures: `KLC_K2_<sym>` (stock history), `KLC_KL_<sym>` (index), `KKE_ShareAmount_<sym>` (auxiliary). The **complete** name is now matched against the expected exchange and symbol. The old digit collection turned `KLC_K2_sh600011` into `2600011` - the `2` from the `K2` prefix - and failed a body it had just decoded, while `KLC_KL_sh000300` gave `000300` and passed, which is why only the stock path showed it. Regressions cover correct stock/index/auxiliary names plus wrong symbol, wrong exchange, swapped prefixes, wrong payload family, a trailing suffix and the old synthetic name.
- **R2-C** - the replay passed empty strings, so the adapter reached `temp_df["":""]` on a `DatetimeIndex` and raised `TypeError`; it now passes the declared window explicitly as `20220824`/`20260904`. On the retained bytes both stock adapters return **978 rows, 2022-08-24..2026-09-04**, and the index adapter (no date arguments) returns **5,987** - matching Codex's diagnostic. `R1` asserts returned rows and dates rather than absence of an exception, and a **NOT EVALUATED** job is worded and statused distinctly from a failed one. The claim that an auxiliary body "was not captured" is corrected - in run 2 it was captured and failed to parse. `C4` no longer reports share-dependent statistics as measured zeros when the series is absent; it says NOT MEASURED with `share_series_available: false`.
- Results: `test_m2_smoke.py` **175 cases, 0 unexpected, exit 0** (165 -> 175; 10 new `O-` regressions, five of them driven by the retained run-2 bodies referenced by SHA-256 so a substituted file fails rather than passes).
- **New offline re-evaluation in a NEW directory**, `revision_20260908T082833Z_r2abc/`, with parent link, producer hashes and input hashes in its `PROVENANCE.json`. Original live verdict FAIL (sh600011 FAIL / sh000300 INCONCLUSIVE / bj920000 FAIL) is untouched; the corrected offline re-evaluation is **FAIL** (sh600011 FAIL / **sh000300 PASS** / bj920000 FAIL). Per check, the corrections are visible: `D1` PASS for all three with the exact expected names, `D5` PASS for both stocks, `R1` PASS for all three with real rows and dates, `C4` measuring again.
- **Capability is still FAIL deliberately, on the EV6 provenance gate**: the capture-time parser recorded requests 2 and 5 as `undecodable` while the corrected parser reads the same bytes as `decoded`. That is a genuine **parser version difference**, declared as such in the provenance file, and **EV6 is not waived** - it is exactly the condition EV6 exists to surface. While it disagrees, this retained capture cannot yield a corrected capability PASS from these inputs; establishing capability under the corrected implementation needs a **new authorized capture**, which this work neither has nor requests. Nothing was forced green and no stored input was massaged.
- Reporting corrections: the **seven-symbol BJ generalization is withdrawn** - one BJ path was contacted, so what is established is that `BJ920000` serves pre-boundary history under its `92xxxx` code, not the mapping mechanism nor the coverage of the other six `bj_code_history` symbols (corrected in Sections 2 and 22; the frozen manifest is unchanged); the **process counts are distinguished** - the standalone pre-arming `--plan` reported 280 while the run's own in-process F1-F8 recorded **279**, the number in the retained `plan.txt` and manifest; and the **current handoff no longer says the second run is unused** - both authorizations are consumed and the pre-run terms are archived as such.
- Remaining limitations: no new live evidence and none sought; the EV6 gate blocks a corrected capability verdict from the retained inputs; SH600011's and BJ920000's semantics are measured on one day's capture of one security each; the BJ result does not generalize; **source capability remains FAIL**.
- Not authorized and not done: a third live capture, the 52-symbol pilot, production writes, service operations, basis labelling, Git staging/commit/push, training.


### 2026-09-08 - R2-ABC closure: denominator validity (C1) and R1 date validation (C2) (Claude)

Bounded **offline** round answering `M2B_R2ABC_CODEX_REVIEW.md`; no live request, production
database access, service change, token access, dataset change, staging, commit, push or
training, and no capture. **C1:** `outstanding_share_as_of` took the last *usable*
observation, so a newer explicit zero was skipped and an older positive denominator
silently restored across it; the state is now the **latest** observation at or before the
date, and an explicitly unusable one withholds a denominator until a later valid
observation supersedes it. Zeros are preserved with their reason, nothing is backfilled,
and `share_series_quality` now reports the deciding state and every invalid interval; `U4`
counts rows-before-the-series apart from rows-under-an-invalid-observation. Verified
against the installed pandas (`[100, 0, NaN, 200].ffill()` = `[100, 0, 0, 200]`). No
measured value in either retained window changes: both `BJ920000` zeros precede its first
positive observation. **C2:** `R1` now requires an actual date sequence consistent with the
row count and first/last metadata, and applies the declared stock window to the stock
interface only, never to the index's full-series interface. **C3:** Section 15's operative
handoff replaced with one authoritative state box; old text kept as explicitly dated
history, and the historical accepted D1/D2 freeze distinguished from the current producer
pins. `test_m2_smoke.py` **182 cases, exit 0** (7 new P- cases incl. an end-to-end U4);
new closure driver `closure_r2abc_v2.py` **49/49 exit 0** (recorded as 48/48 when
written - a miscount in my summary, corrected 2026-09-08 per
`M2B_R2ABC_CLOSURE_CODEX_REVIEW.md`; same driver, same hash `63f73196...`, no result
changed); Codex's unchanged
`review_m2b_r2abc.py` **36/39** with the three expected cross-version failures against the
superseded revision reported, not erased — its four previously failing assertions now pass.
New revision `_m2_smoke/revision_20260908T082833Z_r2abc_v2/` (hash `099640a2…`); capability
still **FAIL**, `EV6` the only failing gate and **not waived**. All eight prior
evidence/revision/receipt/frozen directories verified unchanged.

### 2026-09-08 - R2-ABC closure technically VALIDATED by Codex (bounded offline scope) (Claude)

`M2B_R2ABC_CLOSURE_CODEX_REVIEW.md`. Codex technically validates C1 (denominator validity),
C2 (actual-date-sequence consistency) and C3 (the operative two-captures /
two-consumed-authorizations handoff), **bound to the five producer hashes** `059d0c43...`,
`4b062a55...`, `5bbb6ef0...`, `c6d736b1...`, `23b917c5...`. Runs of record:
`test_m2_smoke.py` **182/182 exit 0**; Codex's new `review_m2b_r2abc_closure_codex.py`
**76/76 exit 0**; my `closure_r2abc_v2.py` **49/49 exit 0**; Codex's unchanged
`review_m2b_r2abc.py` **36/39 exit 1**, whose four previously failing functional
expectations now pass while one producer-pin and two stored-result comparisons fail across
versions as expected - neither it nor the superseded revision was edited to turn them
green. Codex also recorded two scope clarifications: U4 aligns the **728 research
sessions**, not the 978-row replay (the other 250 are warm-up); and the v2 deterministic
block still holds **71 checks**, with only two U4 and three R1 entries changed in counts,
thresholds or wording - **no status, verdict or authorization state moved**. Clerical
correction: my closure driver is **49/49**, not the 48/48 I first reported (same hash
`63f73196...`). **This is not source-capability acceptance, user acceptance, corpus
certification, training readiness, or authorization for another capture**; the earlier
R2-A/B/C round remains **partial** technical acceptance. Source capability remains **FAIL**
on the two `EV6` parser-version disagreements, not waived. Both boundary-1b authorizations
stay consumed; no third capture requested. Documentation-only round: no implementation,
evidence, revision, receipt, frozen-bundle or reviewer artifact changed; nothing staged,
committed or pushed.

### 2026-09-09 - P1 basis module implemented offline; BR-R1..BR-R4 closed for the reviewed hashes (Claude)

The adoption of the bounded **U-1, U-2, U-3, U-4, U-5 and U-7** recommendations, the
deferral of **U-6**, and the authorization of the offline module reach this ledger as a
**user instruction in the Claude session on 2026-09-09** - **Claude-reported and not
independently verified by Codex**, because no file artifact in this repository records it
(see the attribution note in Section 15 and Section 26 of the request for its exact
bounded scope). It is **not** inferred from Codex's technical validation, and no
authorization receipt has been created. Under that instruction, exactly three things were
created:
`_m2_smoke/basis_record.py`, `_m2_smoke/test_basis_record.py` and one fresh output
directory. The module reads ONE selected revision, verifies it (presence, the required
input inventory and recomputed hashes, structure, **both** digest anchors, revision
binding, cross-file identity, upstream pins, output path), derives one record per job,
and evaluates basis-dependent eligibility with **no `eligible=true` path at all**.

Codex's first implementation review (`M2B_P1_BASIS_IMPLEMENTATION_CODEX_REVIEW.md`) withheld
acceptance with four findings - a missing-field bypass in input verification and an
incomplete consumed-file ledger (BR-R1), an output guard that accepted reviewer roots and
was case-sensitive on Windows (BR-R2), access/replay associations that did not gate the
positive transform claim (BR-R3), and a view evaluation that ignored mixed record-producer
identities (BR-R4). **Those findings are preserved as history**, together with the first
output `_m2_smoke/basis_eval_revision_20260908T082833Z_r2abc_v2/`, which remains unchanged
as the historical artifact of the pre-correction module.

All four were corrected and **technically validated** by
`M2B_P1_BASIS_IMPLEMENTATION_CODEX_REVIEW_R2.md` (2026-09-09), **closed for the reviewed
hashes** `basis_record.py` `0fda4f7e…` and `test_basis_record.py` `51add34e…`: my suite
**41/41 exit 0** run by the independent driver, Codex's **21/21** independent expectations,
new output `_m2_smoke/basis_eval_revision_20260908T082833Z_r2abc_v2__br_r1_r4/` with records
digest `f9bef731…`, and 104 protected files unchanged during execution. **P1 remains OPEN,
U-6 deferred, every eligibility `false`, M2b source capability FAIL and both capture
authorizations consumed.** Technical validation of an implementation is **not** policy
adoption, corpus certification, training readiness or operational authorization; no gate was
wired, no production schema or label changed, and nothing was staged, committed or pushed.

## 11. Archived kickoff instruction — M1 (superseded by Section 12)

M0 is technically validated. Begin the read-only three-year data readiness audit now and complete its deliverables without requesting routine implementation guidance.

1. Read the latest Progress Ledger first. Preserve the reviewed A0/A1 candidate and its isolated worktree. Do not rework M0 unless new evidence invalidates it; report any such discovery explicitly.
2. Use explicit SQLite read-only connections for production. Avoid constructors such as `SQLiteStore.init()` and service constructors that initialize or migrate storage. Write audit code and reports only as local, uncommitted artifacts under `claude methods/`; do not modify raw datasets, strategy sets, existing methodology materials, production databases, or knowledge stores.
3. Inventory the relevant stores, including `trading_local.sqlite3` and `market_history.sqlite3`. State which table/database actually feeds each backtest. Measure the fixed research interval 2023-09-04 through 2026-09-04, with any required pre-window feature warm-up treated separately. Report valid rows, distinct securities, benchmark rows, first/last dates, source, adjustment mode, and field availability. Do not count indices as stocks or raw row totals as usable coverage.
4. Produce a per-symbol coverage manifest and an aggregate readiness report. Define the denominator as eligible trading sessions during each security's listing interval. Separate missing historical data, new listings, suspensions, delistings, invalid dates, stale updates, and unavailable listing-history evidence. Where the historical universe cannot be reconstructed, state that survivorship bias is unresolved; do not invent a full-market completeness percentage. Treat any numerical coverage target as a proposed gate requiring an explicit denominator.
5. Audit adjustment consistency, OHLC validity, volume/amount units, duplicate dates, mixed sources, corporate-action discontinuities, and timestamp availability. Investigate the known ERROR pseudo-date read-only. For any apparent anomaly, provide the query, a minimal local example, affected count, and whether it blocks research or merely limits a field.
6. Clarify the temporal research contract before building labels: features, candidate selection, and simulated decisions must use only information available at their cutoff. Forward-return and future phase outcome labels may use subsequent observations only after maturation; they must never leak into earlier features or splits. Do not interpret the earlier wording as prohibiting legitimate future outcome labels. Current qfq history is not automatically historical point-in-time data. Specify temporal splits, outcome-overlap purging/embargo, and the limits of the available adjustment history as proposals for review.
7. Inventory read paths for the 746 legacy evaluations and retain A2 as an explicit prerequisite before official historical evaluation/scoreboard consumption. Do not delete or relabel old rows and do not implement A2 as an unannounced expansion of this audit.
8. Deliver a concrete backfill proposal: exact missing periods and symbols, eligible existing providers, estimated requests/rows/storage and runtime range, verified or unverified rate-limit assumptions, retry/checkpoint design, staging destination, backup/promotion/rollback approach, and before/after acceptance queries. Estimate from measured capability where possible; do not call the live plugin, begin downloads, or start full-market backfill during this read-only gate.
9. Save the report as `claude methods/M1_THREE_YEAR_DATA_READINESS.md`, link its local evidence artifacts, and append a concise Progress Ledger entry. Report actual coverage, remaining gaps, unresolved choices, and one recommended M2 plan. Stop at `ready_for_review` for Codex. Keep commits, pushes, production migration, source-policy changes, service startup, and bulk data writes pending separate authorization.

Continue through all safe M1 audit steps until the report is ready for review. A missing historical field should produce an explicit limitation and alternatives, not an invented value or an unnecessary pause before the remaining independent checks.

## 12. (SUPERSEDED 2026-09-06) Archived kickoff instruction — K1/K2 repairs, now completed and accepted

> This instruction is retained as a historical record only. The K1/K2 repairs it requests were completed and independently accepted (`M1_ACCEPTANCE_CODEX.md`); M1 is recorded as technically `validated`. Do not action this section. The current handoff was Section 13 at the time; Section 13 and Section 14 have since been superseded — see Section 15.

Read `claude methods/M1_KEY_CONTRACT_CODEX_REVIEW.md` in full. It is the current handoff and does not authorize M2. The previous G1a/G1b/G2a/G2b counterexamples are repaired; preserve those behaviors and G3. The clean actual 50+2 fixture now passes. Close K1 by comparing eligible keys in both directions, including extra dates for a known symbol that appear in both views. Explicitly resolve K2 by declaring the feature warm-up source view(s), validating the required consumers, and limiting readiness claims accordingly. Preserve M0, the accepted census and selected securities. Do not restart a broad audit or invoke another multi-agent review.

Production remains read-only. Write only the local audit artifacts and your progress entry under `claude methods/`. Preserve M0 and all unrelated workspace changes. No production migration, dataset/knowledge edits, network/plugin calls, download pilot, service startup, commits or pushes.

At completion, provide a K1/K2 resolution table, exact commands and actual real-CLI results. Keep the actual 50+2 clean control and all previously verified failures. Add same-pre-listing-key-in-both-views and synthetic post-delisting-key tests; legitimate declared warm-up must remain distinct from unexpected research records. Test clean eligible warm-up and missing/divergent warm-up in every required consumer view. If history is intentionally not a feature source, declare that boundary and do not report history/both-view readiness. Retain or restore earlier CLI regressions rather than replacing them to keep the count at 36. Preserve archive/baseline hashes and production data. Stop at `ready_for_review`; downloads, full-market rebuilding and promotion still require their separate approvals.

## 13. (superseded by Section 14, itself superseded 2026-09-07 by Section 15) M2 pilot authorization request

M1 is technically `validated` for the data-contract and staging-acceptance scope. Do not reopen M0, M1, K1/K2/G3, the coverage census, or the unchanged 50-stock plus two-benchmark selection.

The current artifact is `claude methods/M2_PILOT_AUTHORIZATION_REQUEST.md` (rev. 2). It pins the population, research and warm-up intervals, consumed views, price representation, request budget, execution limits, acceptance rule and rollback.

**The request is not executable as written.** Two prerequisites block execution and are stated rather than worked around:

- **P1** — the Sina adapter labels a raw call `adjustment_mode="unknown"`, not `none` (`akshare_provider.py:114`), so a declared `--pricing-basis none` correctly fails the stored-basis gate. Deriving the label from a validated request/response path is a runtime change and is **not** authorized here.
- **P2** — no source can currently supply the full 978-session window: the Tonghuashun adapter caps at 500 bars with no date-bounded pagination (`tonghuasun_provider.py:214-247`). There is no proven fallback; a failed symbol job is reported, not substituted.

Warm-up integrity is blocking; warm-up depth is not. Because `staging_gate.py` gates `W1_pricing`, `W1_history`, `W2` and `V3b` together on `required=warm_required`, that separation is enforced by an acceptance rule over per-gate statuses, not by a flag.

Nothing is authorized beyond preparing this request: no network or plugin call, download, dataset or production write, runtime edit, service start, staging directory, commit, push, training or promotion.

## 14. (SUPERSEDED 2026-09-07 by Section 15) Archived handoff — M2a offline pilot runner, R1-R4 closure

> Historical record only. The **48**-case count below and the framing of "the 3-symbol live smoke test or the 52-symbol staging pilot" as the immediate choice are stale: M2a closed at **79** cases and was technically **validated** by Codex on 2026-09-07 (`M2A_ACCEPTANCE_CODEX.md`). Do not action this section; the current handoff is Section 15.

M1 is technically `validated`. M2 execution is **not** authorized and M2a starts none of it.

The current artifact is `claude methods/M2A_OFFLINE_PILOT_RUNNER.md`, backed by
`claude methods/_m2_pilot/` (`transport.py`, `provenance.py`, `acceptance.py`,
`pilot_runner.py`, `test_m2a.py`). It is offline-only: `plan()` is the default and writes
nothing, `collect()` refuses unless explicitly armed, and the live transport refuses to run.

Reproduce:

```bash
cd "claude methods/_m2_pilot"  && ../../backend/.venv/Scripts/python.exe -B -X utf8 test_m2a.py
cd "claude methods/_m1_closure" && ../../backend/.venv/Scripts/python.exe -B -X utf8 test_staging_gate_e2e.py
```

48 M2a cases and the 67/46/13 accepted M1 suites all pass, exit 0.

Do not reopen M0, M1, K1/K2/G3, the coverage census, or the unchanged 50-stock plus
two-benchmark selection. The next decision is the user's: either the bounded 3-symbol live
smoke test proposed in the M2a document, or the 52-symbol staging pilot — each a separate
authorization. Full-market rebuild, training and production promotion remain outside both.

## 15. Current handoff — both boundary-1b authorizations consumed; the R2-ABC closure (C1/C2) and the P1 basis module are technically validated by Codex in bounded offline scopes; P1 itself still OPEN; capability still FAIL on the EV6 provenance gate; no further capture authorized

> **AUTHORITATIVE CURRENT STATE (2026-09-08, updated 2026-09-09).** Everything below this
> box is either detail or dated history; where they disagree, this box governs.
>
> * **Two** boundary-1b captures have occurred: `20260908T021722Z` (2 of 5 requests,
>   capability **FAIL**) and `20260908T082833Z` (5 of 5 requests, capability **FAIL**).
> * **Both one-run authorizations are consumed. No further capture is authorized**, and
>   none is requested. A third would need a new, explicit one-run authorization from the
>   user, inside the operator window (before 09:15 or after 15:30 Asia/Shanghai).
> * The **R2-ABC closure (C1/C2)** is **technically validated by Codex within its bounded
>   offline scope**, on the five producer hashes below
>   (`M2B_R2ABC_CLOSURE_CODEX_REVIEW.md`, 2026-09-08; Sections 24-25 of the request).
>   That validation is **not** source-capability acceptance, **not** user acceptance,
>   **not** corpus certification or training readiness, and **not** authorization for
>   another capture. The preceding R2-A/B/C round was **partial** technical acceptance
>   (`M2B_R2ABC_CODEX_REVIEW.md`), not final acceptance.
> * **M2b source capability remains FAIL**, blocked on the two `EV6` parser-version
>   disagreements (`sh600011`, `bj920000`), which are **not waived**. No third capture is
>   requested or authorized to clear them.
> * Independent runs of record: my `test_m2_smoke.py` **182/182 exit 0**; Codex's new
>   `review_m2b_r2abc_closure_codex.py` **76/76 exit 0**; my `closure_r2abc_v2.py`
>   **49/49 exit 0**; Codex's **unchanged** `review_m2b_r2abc.py` **36/39 exit 1** — its
>   four previously failing functional expectations now pass, while one producer-pin and
>   two stored-result comparisons fail **across versions**, as expected. Neither that
>   reviewer nor the superseded revision is edited to turn them green.
> * The current offline revision remains
>   **`_m2_smoke/revision_20260908T082833Z_r2abc_v2/`** (hash `099640a2…`).
> * **The P1 basis module is technically validated for its reviewed hashes, and P1 itself
>   is still OPEN.** `_m2_smoke/basis_record.py` `0fda4f7e…` and
>   `_m2_smoke/test_basis_record.py` `51add34e…` were implemented **offline** under a
>   **Claude-reported** user adoption of **U-1, U-2, U-3, U-4, U-5 and U-7** and
>   authorization of the module (2026-09-09; see the attribution note below - **not
>   independently verified by Codex**), and Codex closed
>   **BR-R1 … BR-R4 for exactly those hashes**
>   (`M2B_P1_BASIS_IMPLEMENTATION_CODEX_REVIEW_R2.md`, 2026-09-09; Section 26 of the
>   request). Runs of record: my suite **41/41, exit 0**, executed by the independent
>   driver, and Codex's **21/21** independent expectations. Output directory
>   **`_m2_smoke/basis_eval_revision_20260908T082833Z_r2abc_v2__br_r1_r4/`**, records
>   digest **`f9bef731a8f3e7541f4e266a9b8ad11096727e851a551ce75d657af45b83da9d`**.
>   **`U-6` remains deferred, every eligibility result is `false`** — the module exposes no
>   `eligible=true` path — and **P1 is not closed**. This is a bounded *implementation*
>   validation: **not** policy adoption beyond U-1…U-5/U-7, **not** source-capability
>   acceptance, **not** corpus certification, **not** training readiness and **not** an
>   operational authorization of any kind. The first output,
>   `_m2_smoke/basis_eval_revision_20260908T082833Z_r2abc_v2/`, is preserved unchanged as
>   the **historical** artifact of the pre-correction module
>   (`M2B_P1_BASIS_IMPLEMENTATION_CODEX_REVIEW.md` records the BR-R1…BR-R4 findings against
>   it, and those findings are preserved as history, not erased).
> * Nothing beyond `claude methods/_m2_smoke/` and the two request/goal documents has been
>   touched: no production write, service change, dataset change, staging, commit, push,
>   pilot expansion or training.
>
> **Current producer pins** (`_m2_smoke/`): `smoke_capture.py` `059d0c43…`,
> `smoke_outcomes.py` `5bbb6ef0…`, `smoke_checks.py` `4b062a55…`,
> `sina_klc_decoder.py` `c6d736b1…`, `test_m2_smoke.py` `23b917c5…`,
> `closure_r2abc_v2.py` `63f73196…`. `test_m2_smoke.py` stands at **182 cases, exit 0**.
> These are **not** the historical accepted D1/D2 freeze — see “Current state” below,
> which distinguishes the two.
>
> **P1 basis-module hashes** — a *separate* set that is **not** part of the five smoke
> producer pins above and does not alter them: `basis_record.py` `0fda4f7e…`,
> `test_basis_record.py` `51add34e…`; that suite stands at **41 cases, exit 0**.
>
> **Attribution of the P1 adoption and authorization — Claude-reported, not independently
> verified (DOC-R1).** The adoption of U-1…U-5 and U-7, the deferral of U-6 and the
> authorization of the offline module were given to me as a **user instruction in the
> Claude session on 2026-09-09**, immediately before the implementation round. Its exact
> bounded scope is quoted in **Section 26 of the request**. **No file artifact in this
> repository records that instruction**, so Codex cannot verify it independently and it is
> labelled **Claude-reported** wherever it appears. It is **not** inferred from Codex's
> technical validation; **neither** a Codex review, the module's own header, nor any
> suggested instruction text is the authorization; and **no authorization receipt has been
> created, backdated or requested**.

M1 and M2a are technically `validated` (Codex: `M1_ACCEPTANCE_CODEX.md`, `M2A_ACCEPTANCE_CODEX.md`). M2a's validated scope is the **offline** single-process pilot runner on synthetic fixtures: `test_m2a.py` **79 cases, 0 unexpected, exit 0** (Codex 2026-09-07; reconfirmed locally the same day). M2a's own live path remains deliberately unsupported and unvalidated within M2a. **Two live captures have since been made by this workstream** — boundary-1b runs `20260908T021722Z` and `20260908T082833Z`, both on 2026-09-08, both ending in capability **FAIL** (see below). Both one-run authorizations are consumed and no further capture is authorized. Neither M1 nor M2a status is user acceptance.

Do not reopen M0, M1, M2a, K1/K2/G3, the coverage census or the 50 + 2 selection without new evidence. Preserve `claude methods/_m1_closure/` and `_m2_pilot/` unchanged (the `_m2_pilot` and `_m1_closure` file hashes, the manifest `97e251ae…` and the calendar `f1f1ce33…` are in the 2026-09-07 ledger entries; pre-flight F2 of the M2b request re-fingerprints them before and after any run). The live-path findings recorded on 2026-09-07 (outstanding-share versus amount, the index URL, symbol case, the response-declared basis that the real payload lacks) are prerequisites for later live work, not defects in the validated offline scope.

**2026-09-07:** boundary 1a was authorized and implemented under `claude methods/_m2_smoke/` (Sections 12-14 of the request). Codex reviewed it three times (`M2B_1A_CODEX_REVIEW.md`, `M2B_1A_CLOSURE_CODEX_REVIEW.md`, and the round-3 closure of R1-R4 in Section 14).

**2026-09-08:** Codex **technically validated boundary 1a for the offline scope** (`M2B_1A_ACCEPTANCE_CODEX.md`; Section 15 of the request): `test_m2_smoke.py` 132 cases, 0 unexpected, exit 0, the independent R1-R4 closure probes pass, `--plan` F1-F8 PASS. That is a reviewer's verdict on the **offline engineering path only** - not user acceptance, not completion of M2, and no statement about corpus, feature or training readiness. The five source hashes reviewed **at that time** were `smoke_capture.py` `b17f8d0d...`, `smoke_checks.py` `b2b8aaa9...`, `smoke_outcomes.py` `53a43019...`, `sina_klc_decoder.py` `65992852...`, `test_m2_smoke.py` `5cb4cc3e...`. **Those are historical**: the D1/D2 corrections have since changed three of them. The pins in force now are listed under “Current state” below.

### Boundary 1b: two captures happened, both failed, and both authorizations are consumed

These are two different runs and must not be conflated.

**History — run `20260908T021722Z`, executed and FAILED.** Authorized on 2026-09-08 for one run; armed at **10:17 Asia/Shanghai**, inside continuous trading, after I reported the timing violation and the user instructed the run anyway. It issued **2 of 5 requests**, both HTTP 200, and aborted on two consecutive failed jobs; `BJ920000` was never contacted. Capability **FAIL**, deterministic hash `02e1b76483cd659b5a16f1df78304392e37effcc706a5c325317eefd42448703`. **That authorization is consumed.** Its evidence, receipts and two offline revisions are sealed and unchanged. The failure was our decoder rejecting the vendor's trailing comment (D1) and a pre-flight that could pass on an unreadable process inventory (D2); both are fixed and technically validated (`M2B_D2_ACCEPTANCE_CODEX.md`).

**Run 2 — `20260908T082833Z`, executed 2026-09-08 at 16:27:57 Asia/Shanghai, IN WINDOW; that authorization is now CONSUMED.** All five requests served HTTP 200, 5 attempts of 15, no retries, 7.5 s of the 900 s budget, run completed. Capability **FAIL**, but `BJ920000` is answered for the first time (`pre_boundary_history_served`, 1,393 rows) and `SH600011`'s unit (`share`), currency (yuan, ratio ~1.00), identity and coverage (2001-12-06 to 2026-09-07, complete) are measured. Three of our own defects remain, unfixed by design: the outstanding-share payload is a list of objects rather than pairs, `D1`'s JS-variable digit check false-FAILs on the `KLC_K2_` prefix, and the `R1` harness passes empty start/end dates. See Section 22 of the request. **No further live run is authorized. Both boundary-1b authorizations are now consumed** — the first by run `20260908T021722Z` and the second by run `20260908T082833Z`. A third capture would need a new, explicit one-run authorization from the user, inside the operator window.

> **ARCHIVED — the pre-run authorization terms, no longer operative.** The text that followed here described the second run *before* it was executed: that it had not been armed, that no `run_id` had been minted, and that only a re-trigger was needed. All of that was true until 16:27:57 Asia/Shanghai on 2026-09-08 and is false now. The terms it recorded — same implementation, same three symbols, same five requests and order, unchanged budgets, TLS checks and stop conditions, evidence retained locally only, clock verified by hand, fresh in-process F1–F8, no service started or stopped, no endpoint substituted, no symbol added — were all honoured by the run that consumed the authorization. They are preserved in Section 20 of the request as the authorization record, and the run itself is in Section 22.

### Current state

Two sets of hashes exist and they are **not** interchangeable.

**Historical accepted pins — the D1/D2 freeze, 2026-09-08.** `smoke_capture.py`
`0ed93f05...`, `test_m2_smoke.py` `d14a4f98...`, `sina_klc_decoder.py` `d39e02c8...`,
`smoke_checks.py` `b2b8aaa9...`, `smoke_outcomes.py` `53a43019...`, at 165 cases. This is
the implementation Codex accepted in `M2B_D2_ACCEPTANCE_CODEX.md` and the one that
**executed capture `20260908T082833Z`**. It is preserved byte-for-byte at
`_m2_smoke/frozen_impl_20260908_d1d2_accepted/` as the record of what ran. It is **not**
the current implementation.

**Current producer pins — after R2-A/B/C and the R2-ABC C1/C2 closure.**
`smoke_capture.py` `059d0c43…`, `smoke_outcomes.py` `5bbb6ef0…` (both changed in the
earlier R2-A/B/C round and unchanged in this one), `smoke_checks.py` `4b062a55…`,
`sina_klc_decoder.py` `c6d736b1…`, `test_m2_smoke.py` `23b917c5…`, plus the new closure
driver `closure_r2abc_v2.py` `63f73196…`. `test_m2_smoke.py` stands at **182 cases,
exit 0**. These pins are recorded in
`_m2_smoke/revision_20260908T082833Z_r2abc_v2/PROVENANCE.json`, whose
`cross_version_producer_pins` block names the three sources that changed since the
superseded `…_r2abc` revision.

**M2b source capability remains FAIL.** Run 1 aborted with three of five requests never
issued; run 2 issued all five and still failed, and the corrected offline re-evaluation of
its retained bytes remains FAIL on the `EV6` provenance gate, which is not waived. The
execution checklist and the outstanding-check inventory are Section 21 of the request; the
two correction rounds are Sections 23 and 24.

Current artifact: **`claude methods/M2B_REAL_SOURCE_VERIFICATION_REQUEST.md`** — the bounded three-symbol real-source verification request: `SH600011`, `BJ920000`, `SH000300`; exact endpoints reconfirmed from installed akshare 1.18.64; **5 HTTP attempts, ceiling 15**, pacing ≥ 1.5 s, concurrency 1, finite timeouts, sticky 403/429 abort, 15-minute wall-clock cap; run outputs only under the gitignored `tmp/m2b_smoke_<run_id>/`, with the evidence subset moved at cleanup to the untracked, never-staged `claude methods/_m2_smoke/evidence_<run_id>/` (raw-body retention: **decided** — retained locally only); adapter/decoder prerequisites P-A..P-D with socket-blocked tests; pre-flight F1–F8 (including TLS trust pinning and stack-not-running) printed by a write-nothing `--plan` mode; explicit pass/fail checks with the benchmark handled separately, an offline replay of the installed adapter on the captured bodies, and per-job plus capability verdicts; cleanup, rollback, a reviewer reproduction step and a filled handoff record.

It separates four boundaries: **0** — the preparation, which authorized nothing; **1a** — the offline smoke code and tests, now implemented and technically validated; **1b** — execute the five requests **once**, outside continuous trading (before 09:15 or after 15:30 Asia/Shanghai): run twice on 2026-09-08 — `20260908T021722Z` (2 of 5 requests) and `20260908T082833Z` (5 of 5, in window) — both capability FAIL, and **both authorizations consumed**, with no further capture authorized; **2** — the 52-symbol pilot, later and separate, requiring a smoke PASS, the live-path corrections, the P1 basis-label decision and a revised M2 request, and **not** authorized by the 1b authorization. The 52-symbol collection, model training, full-market rebuild and production promotion are not on the table in this handoff.

Reproduce the validated state (offline, no network):

```bash
cd "claude methods/_m2_pilot"        && ../../backend/.venv/Scripts/python.exe -B -X utf8 test_m2a.py             # 79 cases, exit 0
cd "claude methods/_m2_codex_review" && ../../backend/.venv/Scripts/python.exe -B -X utf8 review_m2a_receipts.py  # 12 groups, exit 0
cd "claude methods/_m1_closure"      && ../../backend/.venv/Scripts/python.exe -B -X utf8 test_staging_gate_e2e.py # 67 checks, exit 0
```

> **HISTORICAL RECORD — SUPERSEDED, AND SO IS THE CORRECTION NOTE INSIDE IT.** This
> paragraph and the note that follows were written on 2026-09-08 **before** run 2. Neither
> has current operational authority. In particular, “a single new run **is already
> authorized and still unused**” and “nothing further is required from the user except an
> **in-window re-trigger**” were true when written and are **false now**: that run was
> executed at 16:27:57 Asia/Shanghai on 2026-09-08 and **both** authorizations are
> consumed. Both are kept unedited as the record of how the round unfolded.
> It is a chronological log that accreted across the 1b round and its reviews, and its later sentences were overtaken as that round closed. Three statements in it are now wrong if read as current: that D1 and D2 are *not fixed*; that the next action is *Codex's review of that correction*; and that the next action is the user's *fresh one-run authorization plus the retention choice*. In fact D1/D2 were corrected and **technically validated** (`M2B_D2_ACCEPTANCE_CODEX.md`), the correction loop is closed, a single new run **is already authorized and still unused**, and the retention choice is **decided** (raw bodies and the frozen reference retained locally only). Nothing further is required from the user except an **in-window re-trigger**.
>
> The text is kept unedited because it is the record of how the round unfolded. For what is true now, read the **“Current state”** block and the **“Boundary 1b”** subsection above, and **Section 21** of `claude methods/M2B_REAL_SOURCE_VERIFICATION_REQUEST.md` for the execution checklist and the inventory of still-unanswered checks.

Scope of what the 1b authorization does and does not permit: it permits exactly one armed run of the reviewed implementation, its `tmp/m2b_smoke_<run_id>/` working tree, the local evidence directory `claude methods/_m2_smoke/evidence_<run_id>/`, and read-only access to `trading_local.sqlite3` for the frozen reference extract. It permits nothing else: no further code beyond the reviewed `_m2_smoke/` files, no `staging/` directory, no database or runtime write, no service start or stop, no commit, no push, no training, no promotion, and no 52-symbol collection. **That single run was executed on 2026-09-08** (run_id `20260908T021722Z`; ledger entry above, Section 16 of the request): capability **FAIL**, 2 of 5 requests issued, `BJ920000` never contacted, evidence retained locally, offline replay byte-identical. It surfaced two defects in reviewed code - D1, the decoder rejects the real body's `/* ... */` trailer, and D2, pre-flight F8 fails open when the process inventory cannot be decoded - neither of which is fixed, because that is outside the spent authorization and the reviewed hashes are frozen. **The authorization was for exactly one run and is now spent.** Codex then reviewed that run (`M2B_1B_CODEX_HANDOFF.md`): the retained FAIL reproduces exactly, **source-capability acceptance is NOT passed**, and bounded offline corrections were requested. Those are done (ledger entry above, Section 17 of the request): D1 accepts the real body's non-executable trailer while still refusing executable or malformed ones, D2 makes the process inventory fail closed and recognises the launch forms `run_stack.ps1` actually uses, `test_m2_smoke.py` is at 146 cases exit 0, and the original evidence and its FAIL are preserved byte-identical with the revised results in a separate directory. **The next action is Codex's review of that correction.** Codex then reviewed that correction (`M2B_D1D2_CODEX_REVIEW.md`): **D1 validated**, D2 blocked by seven reproduced F8 false passes. Those are closed (ledger entry above, Section 18 of the request) - blank/unidentifiable records, backend-relative worker paths and genuine inline execution are all recognised, with unresolved relevant launches failing closed as `ambiguous`. A further review (`M2B_D2_LITERAL_BOUNDARY_CODEX_REVIEW.md`) then found one remaining boundary - the harmless-program exception proved nothing about the whole program - and that is closed too (Section 19): Python inertness is now a bounded AST shape proof and PowerShell requires one complete simple read-only command, with anything unproven treated as `ambiguous`. `test_m2_smoke.py` is at **165 cases exit 0**, the unchanged literal-boundary driver reports **8/8 exit 0**, and the older `review_m2b_d1d2.py` reports an **expected cross-version pin mismatch** (54/55) that is reported rather than fixed. Codex then **technically validated** the bounded D1/D2 offline corrections (`M2B_D2_ACCEPTANCE_CODEX.md`, 2026-09-08) and closed the correction loop. The reviewed implementation is frozen locally at `_m2_smoke/frozen_impl_20260908_d1d2_accepted/`. **M2b source-capability acceptance remains FAIL** - the only real capture aborted and three of its five requests were never issued. Section 20 of the request now prepares **one** new boundary-1b run on the unchanged five-request plan and unchanged limits, with a fresh run_id and fresh paths, preserving every existing evidence, receipt, revision and frozen directory. **It is preparation only and nothing is armed**: the next action is the user's fresh one-run authorization plus the retention choice, after which the Asia/Shanghai clock is verified and recorded immediately before arming.

**End of the superseded historical paragraph.** Current position (2026-09-08): the D1/D2 corrections are technically validated, **two captures have been executed and both boundary-1b authorizations are consumed**, no further capture is authorized or requested, the R2-ABC C1/C2 closure is corrected offline and at `ready_for_review`, and **M2b source capability remains FAIL** on the `EV6` provenance gate. See the authoritative box at the head of this section, “Current state” above, and Sections 23-24 of the request.
