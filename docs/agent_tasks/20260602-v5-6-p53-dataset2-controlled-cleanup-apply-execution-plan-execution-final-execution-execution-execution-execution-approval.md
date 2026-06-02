# V5.6-P53 Dataset2 Controlled Cleanup Final Execution Execution Execution Execution Approval

## Summary

Add a metadata-only approval gate after the accepted V5.6-P52 final execution execution execution dry-run review. This stage records operator approval evidence for a future, separate final execution execution execution execution preflight. It must not execute cleanup, mutate staging rows, write learning samples, start training, modify source datasets, export files, or affect live trading.

## Scope

- Add service/API support for `dataset2_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_execution_execution_execution_execution_approval`.
- Expose:
  - `POST /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-execution-execution-execution-execution-approval`
  - `GET /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-execution-execution-execution-execution-approvals`
- Add dashboard evidence for status, source review, accepted flag, preflight readiness, next action, and safety flags.
- Update release checklist and `a-share-trading-cockpit` stage map.

## Safety Requirements

- Source input must be an accepted P52 review.
- Accepted decision must be exactly `approved_for_controlled_cleanup_apply_execution_plan_execution_final_execution_execution_execution_execution_preflight`.
- Store aggregate metadata only.
- Preserve lock key, transaction/rollback requirement, table scope, and no-record-body evidence.
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
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_dataset2_readiness.py -q -k "execution_execution_execution_execution_approval or api_smoke"`
- `cd frontend && npm exec vue-tsc -- --noEmit`
- Full Dataset2 and repository validation before commit.
