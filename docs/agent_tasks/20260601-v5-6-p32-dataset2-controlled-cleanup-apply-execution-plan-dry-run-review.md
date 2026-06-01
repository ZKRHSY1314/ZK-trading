# V5.6-P32 Dataset2 controlled cleanup apply execution plan dry-run review

V5.6-P32 adds a metadata-only manual review gate after the V5.6-P31 controlled cleanup apply execution plan dry-run. It records whether the aggregate dry-run evidence is acceptable for a later, separately approved execution approval gate.

## Added surfaces

- `POST /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-dry-run-review`
- `GET /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-dry-run-reviews`
- Dashboard action: `Dataset2 apply execution plan review`

## Safety gates

- Requires an existing P31 dry-run.
- Accepted status requires `controlled_cleanup_apply_execution_plan_dry_run_ready_for_review`.
- Accepted status requires `approved_for_controlled_cleanup_apply_execution_plan_execution_approval`.
- Review summarizes aggregate dry-run metadata only.
- Manual backfill remains a warning and review item.
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
