# V5.6-P38 Dataset2 Controlled Cleanup Apply Execution Plan Execution Final Preflight

## Goal

Add a metadata-only final preflight gate after the accepted V5.6-P37 final approval. This stage rechecks the current environment, counts, lock key, table scope, and aggregate-only payload before any future final dry-run is considered.

## Implemented Scope

- Add `dataset2_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_preflight` events.
- Add `staging_cleanup_execution_controlled_apply_execution_plan_execution_final_preflight(...)`.
- Add `list_staging_cleanup_execution_controlled_apply_execution_plan_execution_final_preflights(...)`.
- Add API endpoints:
  - `POST /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-preflight`
  - `GET /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-preflights`
- Add dashboard controls and report block for the P38 final preflight result.
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

The next stage should be a separate final dry-run gate. It should read a passed P38 final preflight, simulate the aggregate final cleanup impact, keep SQL/executable payloads out of the response, preserve rollback/transaction evidence, and continue to block actual staging mutation and training.
