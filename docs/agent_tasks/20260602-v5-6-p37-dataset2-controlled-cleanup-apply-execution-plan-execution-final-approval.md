# V5.6-P37 Dataset2 Controlled Cleanup Apply Execution Plan Execution Final Approval

## Goal

Add a metadata-only final approval gate after the accepted V5.6-P36 dry-run review. This stage records operator approval for a future, separately implemented final preflight. It must not execute cleanup, mutate staging records, promote records, or start training.

## Implemented Scope

- Add `dataset2_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_approval` events.
- Add `staging_cleanup_execution_controlled_apply_execution_plan_execution_final_approval(...)`.
- Add `list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_approvals(...)`.
- Add API endpoints:
  - `POST /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-approval`
  - `GET /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-approvals`
- Add dashboard controls and report block for the P37 final approval result.
- Add service and API smoke tests proving the gate remains metadata-only.

## Required Safety Invariants

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

## Next Step

The next stage should be a separate final preflight gate. It should validate the P37 approval, current staging count, current learning-sample count, lock key, transaction/rollback requirements, table scope, aggregate-only payload shape, and live-trading-disabled state before any later cleanup execution stage is considered.
