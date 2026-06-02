# V5.6-P39 Dataset2 Controlled Cleanup Apply Execution Plan Execution Final Dry-Run

## Goal

Add the final dry-run gate after V5.6-P38 final preflight. This stage only simulates aggregate cleanup impact from approved preflight metadata and records review evidence in the existing events table.

## Safety Boundary

- Do not execute cleanup.
- Do not execute SQL cleanup statements.
- Do not mutate `dataset2_staging_records`.
- Do not write `learning_samples`.
- Do not modify Dataset2 source files.
- Do not export files or create downloads.
- Do not start training.
- Do not optimize live positions, connect brokers, place orders, or control trading screens.

## Expected Deliverables

- `Dataset2TrainingReadinessService.stage` is `V5.6-P39`.
- New event type: `dataset2_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run`.
- New service methods:
  - `staging_cleanup_execution_controlled_apply_execution_plan_execution_final_dry_run`
  - `list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_dry_runs`
- New API endpoints:
  - `POST /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-dry-run`
  - `GET /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-dry-runs`
- Frontend Dataset2 panel shows final dry-run result and exposes a `Dataset2 final dry-run` button.
- Tests prove the stage writes only review metadata and leaves staging/training unchanged.

## Required False Flags

- `cleanup_execution_approved_now=false`
- `cleanup_application_allowed_now=false`
- `cleanup_executed_now=false`
- `can_execute_cleanup_now=false`
- `writes_staging_records_now=false`
- `writes_learning_samples_now=false`
- `mutates_staging_records_now=false`
- `training_started_now=false`
- `can_start_training_now=false`
- `live_trading_enabled=false`

## Validation

- `backend\.venv\Scripts\python.exe -m py_compile backend\app\learning\dataset2_readiness.py backend\app\api\routes.py`
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_dataset2_readiness.py -q`
- `npx.cmd vue-tsc --noEmit`
- Real DB smoke must show staging count unchanged and learning sample count unchanged.
