# V5.6-P42 Dataset2 Controlled Cleanup Apply Execution Plan Execution Final Execution Preflight

## Goal

Add a metadata-only final execution preflight gate after V5.6-P41 final execution approval. The gate prepares evidence for a future final execution dry-run without executing cleanup, writing learning samples, mutating staging rows, or starting training.

## Scope

- Add service methods for creating and listing final execution preflight records.
- Add API routes:
  - `POST /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-execution-preflight`
  - `GET /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-execution-preflights`
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

- Missing P41 approval returns blocked and does not write an event.
- Accepted P41 approval can produce a P42 preflight record only when current staging count, current learning-sample count, lock key, table scope, transaction/rollback gates, and no-executable-payload checks pass.
- Rejected or needs-revision preflight decisions are recorded but do not become ready for dry-run.
- The next required action after a ready preflight is a separate final execution dry-run.

## Validation

- `backend\.venv\Scripts\python.exe -m py_compile backend\app\learning\dataset2_readiness.py backend\app\api\routes.py backend\tests\test_dataset2_readiness.py`
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_dataset2_readiness.py -q`
- `npx.cmd vue-tsc --noEmit`
- `npx.cmd vite build`
- `git diff --check`
- `codegraph status`

