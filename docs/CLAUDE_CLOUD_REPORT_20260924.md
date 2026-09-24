# Claude cloud implementation report — 2026-09-24

Assignment: `docs/CLAUDE_CLOUD_HANDOFF_20260924.md`. Status: `ready_for_review`. This is code and tests validated in the cloud. It is not local production acceptance and not user `accepted`.

| | |
| --- | --- |
| Starting point | `codex/control-plane-refactor` @ `e3f9673e468ae666d402dd726a1ab1704c1f6f83` |
| Working branch | `claude/cool-euler-scl62u` (reset from the old `main` pointer to the start SHA; fast-forward only, nothing discarded) |
| Final code SHA | `67bf68207c2b327238890ab5f5d80d0287cc491c`, followed by this report's own commit (documentation only) |
| Pull request | Draft [ZKRHSY1314/ZK-trading#2](https://github.com/ZKRHSY1314/ZK-trading/pull/2) into `codex/control-plane-refactor`, not merged, nothing pushed to `main` |
| Cost | The platform exposes no cost figure, so no remaining-credit estimate is made |

## Commits

| SHA | Change |
| --- | --- |
| `f556e7f` | Phase 1: the frozen M4 "no `app` in this process" assertions run in a clean child interpreter, with a negative control. Also: byte-pin tests, narrow per-file Ruff exemptions for frozen style only, a conftest that always uses a temporary database, and CI with ubuntu and windows legs |
| `845bddf` | Phase 2: `-ServiceProfile review\|full`, a stdlib planner holding the explicit write scope, profile-aware ensure and diagnostics, a restart budget, the `/readyz` future-heartbeat fix, and a read-only database inventory for backup and rollback |
| `b0261f6` | Phase 3: one canonical selector, folds counted by decision date, maturity and due-coverage fields, a fail-closed strategy-evidence policy, calibration gating, runtime health separated from evidence, and an evidence API, UI card and read-only report |
| `aefb79f` | CI fix: the Windows leg's first Pytest failure was a collection-time clock in a pre-existing test. Also raises the job timeout to 45 min |
| `b414de5` | Phase 4: order intents committed before the open (`backtest_execution.v2`), a named fill policy, the metamorphic tests, and a deterministic A/B harness |
| `67bf682` | Phase 5: a narrow M3/M4 evidence plan. It is a plan only |

Changed files (44):

- **Backend.** `app/backtest/{engine,execution}.py`, plus new `execution_contract.py` and `ab_harness.py`. `app/forecasting/{canonical,feedback,ledger,calibration}.py`, plus new `evidence.py`. `app/control_plane/service.py`, `app/runtime/status.py`, `app/main.py`, and new `app/api/forecast_evidence_routes.py`.
- **Scripts.** New `stack_profiles.py`, `stack_recovery.py`, `db_inventory.py`, `forecast_evidence_report.py` and `run_backtest_ab.py`. Also `stack_diagnostics.py`, `scripts/run_stack.ps1` and `scripts/ensure_stack.ps1`.
- **Tests.** New test modules plus targeted fixture updates, listed under "Test changes to existing files".
- **Frontend.** New `ForecastEvidenceCard.vue`, plus `cockpit.ts`, `TradingDashboard.vue` and `ui-contract.test.mjs`.
- **Docs.** `RECOVERY_PROFILE.md`, `FORECAST_EVIDENCE.md`, `EXECUTION_CAUSALITY.md` and `RESEARCH_EVIDENCE_PLAN_20260924.md`, plus a pointer in `STACK_DIAGNOSTICS.md`.
- **Config.** `.github/workflows/ci.yml` and `backend/pyproject.toml`.

Untouched, verified by an empty `git diff e3f9673 HEAD`:

- all `backend/app/research/*` modules;
- the five frozen test files;
- the entire `claude methods/` archive;
- `.gitattributes`.

The five published SHA-256 pins match in a fresh checkout.

## Test results (actual)

The environment was Linux, Python 3.11.15, Ruff 0.16.6, pytest 9.1.1, Node 22.22.2 and npm 10.9.7. PowerShell 7.4.6 was downloaded into a temporary directory, for parse and `ensure_stack` refusal-path tests only.

**Baseline at `e3f9673`, before any change.**

- `python -B -m pytest -q` gave **1035 passed, 2 failed, 20 skipped**. The two failures were the known M4 isolation tests. The 20 skips are Windows-only.
- `ruff check app tests` reported **33 findings**, all in the frozen M4 files.
- The frontend (`npm test` and `npm run build`) passed.

**Final committed tree `67bf682`**, verified in a clean `git worktree` with a fresh venv (`pip install -e ".[dev]"`) and a fresh `npm ci`:

| Check | Command (from `backend/` unless noted) | Result |
| --- | --- | --- |
| Live-trading probe | `python -c "from app.config import settings; assert settings.enable_live_trading is False"` | exit 0 |
| Ruff | `python -m ruff check app tests scripts` | exit 0, all checks passed |
| PowerShell parse | Parser over `scripts/*.ps1` and `backend/scripts/*.ps1` (pwsh 7.4) | exit 0 |
| Frozen suites, standalone | `python -I -B -X utf8 tests/test_m4_execution.py` (and each of the others) | 62, 42, 36, 105 and 20 run; all OK |
| Backend suite | `python -B -m pytest -q -rs -p no:cacheprovider` | **1156 passed, 19 skipped, 0 failed; 70 subtests passed** (exit 0, 251 s) |
| Frontend | `npm ci && npm test && npm run build` (in `frontend/`) | typecheck + 7/7 UI contract tests; build OK |
| Tree after the checks | `git status --porcelain` | clean, apart from the ignored `dist`/`node_modules` |

**Skipped on Linux (19), with the reason printed by `-rs`.** These are not Windows evidence:

- 18 in `test_tonghuasun_startup_script.py`: Windows PowerShell startup integration;
- 1 in `test_stack_diagnostics.py`: Windows process identity (PID reuse against real `Win32_Process`).

The three `ensure_stack` tests that run under POSIX pwsh skip on Windows by design; their Windows equivalents are in the checklist. Compared with the baseline, the CheckOnly isolation test now runs under pwsh instead of skipping.

**GitHub Actions** (`review-only-ci`), first run on this branch at `f556e7f`:

- The frontend and `backend (ubuntu-latest)` legs were green.
- The `backend (windows-latest)` leg reached Pytest for the first time: **1070 passed, 1 failed**, with no skips, so the Windows integration tests ran and passed.
- The single failure was `test_simulation_account_does_not_claim_expired_or_unparsed_screen_holdings`. It took `datetime.now()` at collection time, and the 22-minute Windows run made the "fresh" evidence expire. `aefb79f` fixes this.
- The CI status of the later commits is recorded in the PR description as the runs complete.

**Proof that the causality test is not vacuous.** The metamorphic fixture was also run against the pre-fix engine, checked out at `b0261f6`. The entry's open-time quantity was 14,800 at baseline. It became 15,900 when only the held stock's later close changed, and 14,400 after an intraday stop crash. The fixed engine gives 14,800 in all three cases.

### Test changes to existing files, and why

- **`conftest.py`:**
  - Always uses a temporary database.
  - Forces the safe provider flags.
  - Adds fail-closed guards.
  - Routes exactly the two frozen isolation items to a clean child process. They are neither skipped nor deselected.
- **`test_runtime_health.py`.** Three fixtures used `2099-01-01` as a stand-in for "fresh". That relied on the `/readyz` clamp this work fixes, so they now use the current time. A new test covers the future-timestamp case.
- **`test_forecast_feedback.py`.** One fixture treated two same-day snapshots as two folds, which is the semantics the handoff forbids. It now uses two distinct decision dates.
- **`test_stack_diagnostics.py`.** The CheckOnly test also runs under pwsh. There are new profile, configuration-mismatch, failed-cycle-versus-dead-process and future-heartbeat cases.
- **`test_simulation_market_data.py`.** The clock is now taken when the test runs, not at collection. The assertions are unchanged.

## Data-write implications

**The cloud touched no data.** It had no production or frozen database, no market capture and no credentials. No worker, scheduled task or network data refresh was started, apart from a synthetic `uvicorn` and `vite` pair used for one UI screenshot, which was then stopped. Every test uses temporary SQLite files.

**Once the code runs locally:**

- **Recovery profile.** `review` starts no workers. The backend still runs `SQLiteStore.init()`, a schema and normalisation write, and requests from the UI can write. `docs/RECOVERY_PROFILE.md` defines backup-first and inventory before and after.
- **Stored evaluations.** `forecast_evaluations` identities hash the metrics. The metrics now carry new fields (`fold_unit`, maturity fields and so on), so the first evaluation after deployment inserts new rows rather than deduplicating against older ones. The old rows are untouched and are reported as history when they lack the current policy.
- **Calibration proposals.** Pending `forecast_calibration` proposals are updated in place, as before. Favourable but ineligible evidence now yields `continue_monitoring` rather than `retain_champion_validate_challenger`.
- **Control-plane runs.** They no longer go `partial` when the only problem is insufficient forecast evidence. The heartbeat keeps its normal interval.
- **Backtests.** New runs persist `metrics.execution_contract`. Their sizing semantics differ from pre-v2 runs, so old and new returns are not comparable. A run without a contract is pre-v2.
- **Heartbeats.** `/readyz` now reports a future-dated heartbeat as `invalid`. `ensure_stack` can therefore restart where it previously accepted the heartbeat, limited by the restart budget.

## Local Windows acceptance

Follow `docs/RECOVERY_PROFILE.md` → "Local Windows acceptance checklist". It has 11 steps and covers only the `review` profile and the runtime database. It includes the backup, the before and after inventories, profile-mismatch and restart-budget fault injection, and the restore. In addition:

1. **Run the Windows tests.** `python -m pytest -q -rs` on Windows should show 0 failures, and the Windows-only tests above should run rather than skip.
2. **Forecast evidence, read-only.** Run `backend\scripts\forecast_evidence_report.py --database trading_local.sqlite3` with the stack stopped. It opens the database `mode=ro`. Record the confirmed and inferred snapshot counts and the decision dates. Compare the file's SHA-256 before and after; it must be unchanged.
3. **UI.** With the `review` stack running, the "预测评估证据" card must show "不支持策略结论" until at least 20 confirmed, matured decision dates exist. Unknown values must read 未知 or 无到期, never 0.
4. **A/B.** Run `run_backtest_ab.py` only with a written manifest. It copies the database first; never point anything else at production.

**Code rollback:** revert the PR's commits, or check out `e3f9673`. **Runtime rollback:** step 6 of `RECOVERY_PROFILE.md`, restoring from the SHA-256-verified copy.

## Five separate categories

| Category | State after this work |
| --- | --- |
| Engineering completion | Phases 1–4 are implemented, tested in the cloud and committed. Phase 5 is a written plan. Windows execution of the edited PowerShell remains `integration_pending`. |
| Actual source capability | Unchanged and unverified here. There were no Tonghuashun, Sina or Tencent calls. The local long-history demonstration and the EV6 failure both stand as previously recorded. |
| Data readiness | Unknown in the cloud. The market cache was last reported stale on 2026-09-13, and nothing was refreshed. The calendar and coverage remain proxies. |
| Historical execution evidence | None. The engine is now causal at intent time, but fills are daily-bar assumptions, `qualified_historical_execution=false`. M4 remains `technically_closed_evidence_target_not_met`. |
| Training eligibility | `training_eligible=false`. M3 has 0 of 50 jointly positive cases. No horizon is strategy-eligible without at least 20 confirmed decision dates. M5 has not started. |

## Limitations and next exact actions

- **Windows behaviour untested here.** Windows PowerShell 5.1 execution of `run_stack.ps1` and `ensure_stack.ps1` was not run. The `review` profile's actual process set, `stop_stack.ps1` against a v2 PID file, and scheduled-task interaction are all unproven. **Next:** the local checklist.
- **Persistent task.** The scheduled task still runs the `full` profile, and its definition was not changed. `ensure_stack` refuses to switch a manual `review` stack to `full` (`profile_mismatch`).
- **Maturity proxy.** The "due" test uses weekdays, not an authenticated exchange calendar.
- **Review worker.** `app/ai/review_worker.py` still compares configurations with retrospective fills and reads a missing return as 0. **Next:** move it onto `ab_harness`. The in-session follow-up suggestion tool timed out, so this is recorded here instead.
- **No M4 adapter.** No production-to-M4 adapter was built. That needs dated ST, price-band, fee and capacity sources (`docs/RESEARCH_EVIDENCE_PLAN_20260924.md`).
- **Windows CI time.** The Windows CI leg takes about 22 minutes; the job timeout is now 45 minutes.
