# V5.6-P54 Dataset2 Controlled Cleanup Final Execution Execution Execution Execution Preflight

## Summary

Add a metadata-only preflight gate after the accepted V5.6-P53 final execution execution execution execution approval. This stage rechecks lock key, current staging count, current learning-sample count, table scope, and transaction/rollback requirements before a future separate final execution execution execution execution dry-run. It must not execute cleanup, execute SQL, mutate staging rows, write learning samples, start training, modify source datasets, export files, or affect live trading.

## Scope

- Add service/API support for `dataset2_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_execution_execution_execution_execution_preflight`.
- Expose:
  - `POST /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-execution-execution-execution-execution-preflight`
  - `GET /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-execution-execution-execution-execution-preflights`
- Add dashboard evidence for status, source approval, staging/learning count match, lock key, dry-run readiness, next action, and safety flags.
- Update release checklist and `a-share-trading-cockpit` stage map.

## Safety Requirements

- Source input must be an accepted P53 approval.
- Accepted decision must be exactly `prepared_for_controlled_cleanup_apply_execution_plan_execution_final_execution_execution_execution_execution_dry_run`.
- Store aggregate metadata only.
- Recheck lock key, staging count, learning-sample count, transaction/rollback requirement, and table scope.
- Keep all execution and training flags false:
  - `cleanup_execution_approved_now=false`
  - `cleanup_application_allowed_now=false`
  - `cleanup_executed_now=false`
  - `can_execute_cleanup_now=false`
  - `writes_staging_records_now=false`
  - `mutates_staging_records_now=false`
  - `writes_learning_samples_now=false`
  - `training_started_now=false`
  - `live_trading_enabled=false`

## Validation

- `backend\.venv\Scripts\python.exe -m py_compile backend\app\learning\dataset2_readiness.py backend\app\api\routes.py backend\tests\test_dataset2_readiness.py`
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_dataset2_readiness.py -q -k "execution_execution_execution_execution_preflight or api_smoke"`
- `cd frontend && npm exec vue-tsc -- --noEmit`
- Full Dataset2 and repository validation before commit.
