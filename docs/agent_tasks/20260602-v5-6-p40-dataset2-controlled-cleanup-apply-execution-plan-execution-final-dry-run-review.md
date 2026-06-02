# V5.6-P40 Dataset2 Controlled Cleanup Apply Execution Plan Execution Final Dry-Run Review

## Goal

Add a metadata-only review gate for the V5.6-P39 final dry-run. This gate records whether an operator reviewed the aggregate final dry-run evidence and whether it is ready for a future separate final execution approval gate.

## Scope

- Add a service method and list method for final dry-run reviews.
- Add API endpoints:
  - `POST /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-dry-run-review`
  - `GET /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-dry-run-reviews`
- Add dashboard evidence for the latest final dry-run review.
- Add backend unit and API smoke coverage.
- Update release checklist and `a-share-trading-cockpit` stage map.

## Safety Boundary

P40 may write only one metadata event to the existing `events` table. It must not execute cleanup, execute SQL, apply fixes, mutate `dataset2_staging_records`, write `learning_samples`, start training, modify Dataset2 source files, export files, optimize positions, connect brokers, place orders, control trading screens, or change live-trading state.

Required false flags:

- `cleanup_execution_approved_now=false`
- `cleanup_application_allowed_now=false`
- `cleanup_executed_now=false`
- `can_execute_cleanup_now=false`
- `mutates_staging_records_now=false`
- `writes_staging_records_now=false`
- `writes_learning_samples_now=false`
- `can_promote_to_learning_samples_now=false`
- `training_started_now=false`
- `can_start_training_now=false`
- `live_trading_enabled=false`

## Acceptance

- Missing P39 final dry-run returns a blocked response and writes no event.
- Passed P39 final dry-run plus `approved_for_controlled_cleanup_apply_execution_plan_execution_final_execution_approval` records an accepted review.
- `needs_revision` or `rejected` review decisions are recorded but remain blocked.
- Stored payload contains aggregate dry-run summaries only, with no record bodies, SQL, executable code, patch, shell command, or evidence package body.
- Frontend can show empty state, accepted review, blocked review, and safety flags.

## Validation

- `backend\.venv\Scripts\python.exe -m py_compile backend\app\learning\dataset2_readiness.py backend\app\api\routes.py`
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_dataset2_readiness.py -q`
- `npx.cmd vue-tsc --noEmit`
- Full validation before release: backend compileall, full pytest, pip check, health false, frontend build/audit, git diff check, forbidden tracked-file scan, and codegraph status.
