# V5.6-P43 Dataset2 Controlled Cleanup Apply Execution Plan Execution Final Execution Dry-Run

## Goal

Add an aggregate-only final execution dry-run after V5.6-P42 final execution preflight. The dry-run records simulated final execution impact for a future review gate without executing cleanup, writing learning samples, mutating staging rows, or starting training.

## Scope

- Add service methods for creating and listing final execution dry-run records.
- Add API routes:
  - `POST /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-execution-dry-run`
  - `GET /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-execution-dry-runs`
- Add dashboard state, action button, latest-result report, and startup history loading.
- Add backend tests and API smoke coverage.
- Update release checklist and cockpit skill boundary notes.

## Required Safety

- `review_only=true`
- `simulation_only=true`
- `live_trading_enabled=false`
- `cleanup_execution_approved_now=false`
- `cleanup_application_allowed_now=false`
- `cleanup_executed_now=false`
- `can_execute_cleanup_now=false`
- `writes_staging_records_now=false`
- `writes_learning_samples_now=false`
- `mutates_staging_records_now=false`
- `training_started_now=false`
- `can_start_training_now=false`

## Expected Behavior

- Missing P42 preflight returns blocked and does not write an event.
- Passed P42 preflight can produce a P43 dry-run record only when staging count, learning-sample count, lock key, table scope, transaction/rollback gates, and no-executable-payload checks remain valid.
- Rejected or needs-revision dry-run decisions are recorded but do not become ready for review.
- The next required action after a ready dry-run is a separate final execution dry-run review gate.

## Validation

- `backend\.venv\Scripts\python.exe -m py_compile backend\app\learning\dataset2_readiness.py backend\app\api\routes.py backend\tests\test_dataset2_readiness.py`
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_dataset2_readiness.py -q`
- `npx.cmd vue-tsc --noEmit`
- `npx.cmd vite build`
- `git diff --check`
- `codegraph status`

