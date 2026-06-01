# V5.6-P33 Dataset2 controlled cleanup apply execution plan execution approval

V5.6-P33 adds a metadata-only approval gate after the V5.6-P32 controlled cleanup apply execution plan dry-run review. It records operator approval metadata for a later, separately checked execution preflight. It does not approve or execute cleanup.

## Added surfaces

- `POST /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-approval`
- `GET /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-approvals`
- Dashboard action: `Dataset2 apply execution approval`

## Safety gates

- Requires an existing accepted P32 dry-run review.
- Ready status requires `approved_for_controlled_cleanup_apply_execution_plan_execution_preflight`.
- Approval scope is limited to a later preflight gate.
- Manual backfill remains a warning and future review item.
- No record bodies, SQL, runnable code, source dataset edits, staging mutation, training-table writes, exports, broker actions, or screen control.

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
