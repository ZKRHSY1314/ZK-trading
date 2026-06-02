# V5.6-P50 Dataset2 Controlled Cleanup Final Execution Execution Execution Preflight

## Scope

Implement and review the metadata-only preflight that follows a passed V5.6-P49 final execution execution execution approval.

## Expected Behavior

- Add a POST/GET API pair for `cleanup-execution-controlled-apply-execution-plan-execution-final-execution-execution-execution-preflight`.
- Require an accepted P49 approval before recording any preflight event.
- Recheck lock key, staging count, learning-sample count, transaction/rollback, table scope, aggregate-only payload, and no executable content.
- Write only an `events` metadata row when a valid source approval exists.
- Keep source Dataset2 files, `dataset2_staging_records`, `learning_samples`, and training state unchanged.

## Safety Requirements

- `cleanup_execution_approved_now=false`
- `cleanup_application_allowed_now=false`
- `cleanup_executed_now=false`
- `can_execute_cleanup_now=false`
- `mutates_staging_records_now=false`
- `writes_staging_records_now=false`
- `writes_learning_samples_now=false`
- `training_started_now=false`
- `can_start_training_now=false`
- `live_trading_enabled=false`

## Validation

- `python -m py_compile backend/app/learning/dataset2_readiness.py backend/app/api/routes.py backend/tests/test_dataset2_readiness.py`
- `pytest backend/tests/test_dataset2_readiness.py -q -k "execution_execution_execution_preflight or api_smoke"`
- `npm --prefix frontend exec vue-tsc --noEmit`
- `npm --prefix frontend exec vite build`

