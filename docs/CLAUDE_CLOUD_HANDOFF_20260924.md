# Claude cloud implementation handoff — 2026-09-24

## Assignment

Continue implementing this repository in the cloud. This is an implementation assignment, not merely a request for another audit or roadmap. Work autonomously through the ordered, cloud-feasible tasks below, make reviewable commits, and leave a precise handoff for local Windows acceptance. Do not stop after proposing a plan. If one task depends on unavailable local data or desktop hardware, record that specific dependency and continue independent engineering work.

Repository: `https://github.com/ZKRHSY1314/ZK-trading`

Starting branch: `codex/control-plane-refactor`. Fetch and start from its latest pushed commit, NOT the older `main` branch. Record the actual starting SHA in your report. Create your own implementation branch from it; do not force-push or merge into main. If your cloud checkout starts on main, switch to the specified baseline before editing.

The user has approximately $250 of Claude cloud credit available. Treat this as available capacity, not a requirement to consume it. Prefer implementation and focused tests over repeated document generation or large agent fan-outs. Use cost information only if the platform actually exposes it; do not invent a remaining-dollar estimate. Finish bounded increments and preserve work if the platform limit approaches.

## Read first, in this order

1. `AGENTS.md`, `CODEX_CLAUDE_COLLABORATION.md`, and `CLAUDE.md`.
2. `claude methods/06_CODEX_进度建议复核_2026-09-13.md` — independently corrected priorities.
3. `claude methods/07_运行监督第一步验收_2026-09-13.md` and `docs/STACK_DIAGNOSTICS.md` — latest completed implementation increment and remaining operational scope.
4. `claude methods/M3_FINAL_ACCEPTANCE_20260910.md` and `claude methods/M4_FINAL_ACCEPTANCE_20260912.md` — research qualification gates.
5. `claude methods/05_进度复核与时间线_2026-09-13.md` as a proposal superseded where corrected by document 06.

Do not bulk-read the entire historical archive. Older documents contain obsolete instructions, proposed authorizations, local paths and historical progress claims. They are evidence/history, not current authorization. The old `claude methods/README.md` also predates the corrections in 06/07.

## What is and is not available in Git

Application code, scripts, tests, formal review documents and archived source scripts are included. Production SQLite files, real/frozen datasets, market captures, generated JSON receipts, large replay outputs, PDFs, caches, IDE state, logs and credentials are deliberately NOT included. Some archived scripts reference omitted local inputs or hard-coded Windows paths. Do not execute those scripts indiscriminately or create fake substitutes for their missing inputs.

The source archive preserves original files; historical existence or a report saying "passed" is not cloud reproduction. A cloud test must use its own clearly labelled synthetic fixture or an explicitly available, authenticated input. Do not download replacement market data merely to make frozen-data tests pass.

Several accepted M3/M4 files have byte-level SHA-256 contracts including CRLF. `.gitattributes` preserves those bytes across checkout. Do not normalize, autoformat, change pinned hashes, or rewrite frozen evidence just to make a check green. If a semantic change is required, retain the old baseline and introduce an explicitly versioned successor or integration adapter with migration evidence.

## Non-negotiable boundaries

- Keep live trading disabled. No broker login, credentials, account/fund access, real orders, real cancellations, bank transfer or unrestricted trading clicks.
- Do not assume the cloud can access the user's Windows desktop, Tonghuashun session, `D:` drive, loopback port 17180 or Windows scheduled tasks. Do not ask for the user's tokens or copy local authentication material.
- Do not deploy, install production schedules, launch production workers, refresh the user's market cache, mutate real datasets, or claim local runtime restoration from cloud work. Deliver and test the code; local production acceptance remains separate.
- Do not automatically dispatch other external agents or messages. The user will transfer the final result back to Codex for local review.
- M3 and M4 remain `technically_closed_evidence_target_not_met`. Keep `M3_complete=false`, `M4_complete=false`, `training_eligible=false`, and the historical `strict_pit=false` qualification. Do not start M5, tune trading thresholds, expand the real research universe or force disputed labels into positives.

## Current baseline and important findings

- The last independently checked local production state was September 13, NOT a current cloud observation. The stack was down after a Windows restart; its persistent supervisor task was absent. The initial cause of the September 4 interruption was not established. An old WinError 10054 is not proof that it killed the loop.
- The latest increment added `backend/scripts/stack_diagnostics.py`, `scripts/check_stack.ps1`, and `ensure_stack.ps1 -CheckOnly`. It distinguishes process identity, cycle outcome and market-cache coverage; it does not start workers or change the database. The first increment passed 70 focused tests locally.
- The diagnostic calendar is explicitly a weekday proxy and the coverage denominator is a recent-row-count peak, not an authenticated exchange calendar or historical universe. Never relabel these proxies as qualified data. `needs_attention` is expected when prerequisites are absent.
- Full startup currently bundles adaptive control, reference data, history refresh, features, capital flow, instrument catalog, calibration and optional Codex workers. It is not a minimal read-only recovery action.
- The production backtest allocates at the open using the same day's closing mark in `_positions_value`; full-day high/low/amount also influence assumed open execution. Those are unresolved time-of-availability problems. Do not make the existing production engine authoritative for return comparisons before fixing them.
- The old forecast evaluation of 3,630 observations / 121 folds per horizon uses repeated snapshots and has no canonical-policy version. September 13 inspection using `canonical_snapshot.v3` yielded only 5 inferred snapshots, 150 observations per horizon, and zero confirmed snapshots. These are dated local findings, not numbers to hard-code in the application.
- M3 had 32 matched cases, all disputed, with zero jointly positive cases. Scaling 50 stocks to 500 does not by itself resolve label semantics, contemporaneous universe membership, ST status, delistings or corporate-action evidence.
- Tonghuashun long history was demonstrated locally. The adapter's former 500-bar cap is not proof of an upstream limit. Conversely, large Sina production row counts do not certify the separate failed EV6 capability test. No new capture is authorized by this handoff.

## Ordered implementation work

### 1. Establish a trustworthy cloud/CI baseline

Install the repository-declared dependencies in an isolated environment. Run Ruff, backend tests, frontend tests/build and applicable syntax checks. Every test database must be temporary and live trading must be disabled before application imports. On Linux, clearly separate portable tests from Windows integration tests; do not claim a Linux skip proves Windows behavior.

Reproduce and fix the M4 test-host isolation problem: `conftest.py` imports `app`, while two standalone tests assert that no `app` module exists in the process. Preserve the actual no-side-effect assertions in a clean child process or a separate complete test invocation. Do not simply skip, delete or weaken the checks. Keep every relevant original case covered by CI.

Resolve the existing lint baseline without blanket disabling lint, autoformatting frozen source or silently changing its hashes. Narrow, documented compatibility handling for frozen style is preferable to destroying provenance; genuine code defects still need correction and versioning. Prove the committed tree, not only an uncommitted local workspace, can run the intended checks.

### 2. Finish the bounded supervision/recovery engineering

Refactor the startup contract so a caller can explicitly select a minimal review/diagnostic service profile instead of silently starting scoring, forecasting, model calls, calibration or simulation workers. Preserve the existing full profile's documented behavior and fail-closed live-trading checks.

Make worker selection, effective configuration, target database/manifest paths and expected writes explicit and auditable. Define backup/rollback and validation requirements for later local production recovery. Keep CheckOnly structurally unable to reach startup, shutdown, plugin configuration or data writes.

Test unavailable dependencies, stale or future heartbeat timestamps, process exit, PID reuse, mismatched worker configuration, partially updated cache, startup failure cleanup, repeated invocation and recovery. Distinguish a failed upstream cycle from a dead process; avoid whole-stack restart storms on transient provider failures. Report what was proven with fixtures and what still requires Windows acceptance. Do not actually register or activate the user's persistent task.

### 3. Unify canonical forecast evidence and its presentation

Use one canonical snapshot selector across evaluation, calibration and the scoreboard. Surface policy version, as-of timestamp, confirmed versus inferred provenance, distinct decision dates, horizon maturity, coverage denominator and insufficient-evidence reasons. Do not treat repeated snapshots as independent folds, missing evidence as zero, or old unversioned ready evaluations as current qualified evidence.

Separate runtime availability from strategy-evidence eligibility. A poor/unknown IC should prevent an unsupported strategy qualification, not disable read-only diagnostics. Add small deterministic fixtures covering duplicates, incomplete claims, orphans, inferred-only samples, tied ranks and partially matured horizons. UI changes should display those distinctions clearly without hard-coded September observations.

### 4. Correct execution causality before strategy A/B

Introduce a small, explicit production-to-M4 integration contract or an equivalently tested correction. Open-time sizing may use only information available at that time. Define the distinction between order intent and retrospective daily-bar fill assumptions, including capacity, price-band checks, fees, settlement and partial fills.

Required metamorphic test: holding all pre-open information fixed and changing only future close/high/low/amount must not change a committed open-time intent or its budget. Any later fill adjudication must have an explicit information-timing contract. Keep synthetic fees/capacity and projected fundamentals visibly unqualified; do not manufacture historical PIT eligibility.

Only after these corrections, prepare a deterministic same-input A/B harness with fixed manifests, costs and predeclared controls. Cloud synthetic runs may prove engineering behavior, not profitable strategy performance or qualified historical nonzero trading.

### 5. Leave a narrow research-evidence plan

Document what additional label clarification and historical input evidence would unblock M3/M4. Preserve both reviewers' disagreement. Do not perform unauthorized collection, expand to an arbitrary 500 stocks, change thresholds, use holdout data or start M5. Defer broad legacy-route migration and cosmetic cleanup until the correctness work is complete.

## Required delivery

- Separate reviewable commits by coherent change, preserving unrelated baseline work. Push your implementation branch and open a draft PR if your cloud environment supports that workflow; do not merge it.
- A concise report stating starting/final SHA, files changed, exact test commands and exit results, skipped or unavailable platform checks, known failures, data-write implications and remaining local acceptance steps.
- A local Windows acceptance checklist and rollback procedure for the recovery profile, with explicit worker/database/manifest scope. Do not supply a broad "run everything" command as the default.
- A final distinction between engineering completion, actual source capability, data readiness, historical execution evidence and training eligibility. Passing tests does not collapse these categories.

If you cannot finish every phase within the cloud run, finish and validate the current bounded phase, commit it, and state the next exact action. Never claim all phases complete because credit, context or execution time is running out.

## Publisher validation on 2026-09-24

See `docs/CLOUD_PUBLICATION_BASELINE_20260924.md` for the actual pre-push results and excluded-data policy. These results describe the publication baseline and are not instructions to preserve known failures.
