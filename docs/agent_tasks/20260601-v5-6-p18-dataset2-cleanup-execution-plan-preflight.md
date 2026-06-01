# V5.6-P18 Dataset2 Cleanup Execution Plan Preflight

## Goal

Add a metadata-only preflight gate after the V5.6-P17 controlled cleanup execution plan. This stage checks whether the automated cleanup subset is ready for a later controlled dry-run, while still blocking actual staging mutation and training.

## Implemented Scope

- `Dataset2TrainingReadinessService.staging_cleanup_execution_plan_preflight`
- `Dataset2TrainingReadinessService.list_staging_cleanup_execution_plan_preflights`
- API:
  - `POST /api/learning/dataset2/staging/cleanup-execution-plan/preflight`
  - `GET /api/learning/dataset2/staging/cleanup-execution-plan/preflights`
- Dashboard:
  - Dataset2 plan preflight action
  - Latest preflight status, source plan id, staged count, automated operation count, dry-run readiness, execution/training safety flags

## Required Checks

- Source P17 plan exists and is ready for preflight.
- Staging record count matches the reviewed plan.
- Automated batches are limited to deterministic operations.
- Manual evidence and historical-outcome work remains separated.
- Transaction and rollback are required before any future execution.
- Table scope is limited to `dataset2_staging_records`; `learning_samples` remains forbidden.
- No SQL, runnable code, record bodies, affected-row bodies, or full evidence bodies are stored.

## Required Safety Evidence

- Uses only the existing `events` table for preflight metadata.
- Keeps all execution and training flags false:
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

## Validation Checklist

- Dataset2 unit/API tests cover missing, blocked, and ready-for-dry-run preflight paths.
- Dashboard type check and build still pass.
- Real local DB smoke may create one blocked preflight event if the latest P17 plan is blocked; staging and `learning_samples` counts must remain unchanged.
