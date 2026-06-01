# V5.6-P31 Dataset2 controlled cleanup apply execution plan dry-run

V5.6-P31 adds a metadata-only dry-run after the V5.6-P30 controlled cleanup apply execution plan preflight. It simulates aggregate plan impact for review, but it does not execute cleanup, write SQL, mutate staging records, promote records into `learning_samples`, export files, or start training.

## Added surfaces

- `POST /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-dry-run`
- `GET /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-dry-runs`
- Dashboard action: `Dataset2 apply execution plan dry-run`

## Safety gates

- Requires an existing P30 preflight.
- Ready status requires `controlled_cleanup_apply_execution_plan_preflight_ready_for_dry_run`.
- Ready status requires `simulated_for_controlled_cleanup_apply_execution_plan_review`.
- Current staging count must still match the P30 preflight scope.
- Simulation remains aggregate-only: no record bodies, no SQL, no runnable code, no executable payload.
- Manual backfill batches remain separated as warnings for later human review.

## Required false flags

- `cleanup_execution_approved_now=false`
- `cleanup_application_allowed_now=false`
- `cleanup_executed_now=false`
- `can_execute_cleanup_now=false`
- `writes_staging_records_now=false`
- `mutates_staging_records_now=false`
- `writes_learning_samples_now=false`
- `can_promote_to_learning_samples_now=false`
- `training_started_now=false`
- `can_start_training_now=false`
- `live_trading_enabled=false`

## Validation

- `python -m py_compile backend/app/learning/dataset2_readiness.py backend/app/api/routes.py`
- `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_dataset2_readiness.py -q`
- `npx vue-tsc --noEmit`
- `npm run build`
- `git diff --check`
- forbidden tracked-file scan
- `/health.live_trading_enabled=false`
- `codegraph status`
