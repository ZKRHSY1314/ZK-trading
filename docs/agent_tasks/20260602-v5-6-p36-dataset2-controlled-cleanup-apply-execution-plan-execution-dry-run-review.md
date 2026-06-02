# V5.6-P36 Dataset2 Controlled Cleanup Apply Execution Plan Execution Dry-run Review

## Goal

Add a metadata-only review gate for the V5.6-P35 controlled cleanup apply execution plan execution dry-run.

This stage reviews aggregate dry-run evidence and records whether it is acceptable for a later, separate final approval gate. It must not execute cleanup, mutate staging records, write learning samples, start training, modify Dataset2 source files, export files, connect brokers, place orders, control trading screens, or change live-trading state.

## Backend

- Add `dataset2_staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review` events.
- Add `staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run_review(...)`.
- Add `list_staging_cleanup_execution_controlled_apply_execution_plan_execution_dry_run_reviews(...)`.
- Accept only a passed P35 dry-run plus `approved_for_controlled_cleanup_apply_execution_plan_execution_final_approval`.
- Store only source ids, aggregate dry-run summaries, reviewer metadata, checks, safety flags, and review-only decisions.

## API

- `POST /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-dry-run-review`
- `GET /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-dry-run-reviews`

## Frontend

- Show latest P36 review status, source dry-run id, simulated mutation count, warning count, accepted flag, blocked execution flag, and blocked training flag.
- Add a dashboard button to record the review metadata.
- Do not add cleanup execution, training, export, broker, order, credential, or screen-click controls.

## Required Safety Flags

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
- `writes_source_dataset=false`
- `writes_file=false`
- `live_trading_enabled=false`

## Validation

- `backend\.venv\Scripts\python.exe -m py_compile backend\app\learning\dataset2_readiness.py backend\app\api\routes.py`
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_dataset2_readiness.py -q`
- `npx.cmd vue-tsc --noEmit`
- Full release validation before commit.
