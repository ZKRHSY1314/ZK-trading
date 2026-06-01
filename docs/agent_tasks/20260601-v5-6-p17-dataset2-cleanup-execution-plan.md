# V5.6-P17 Dataset2 Cleanup Execution Plan

## Goal

Turn an accepted V5.6-P16 aggregate dry-run review into a metadata-only controlled cleanup execution plan. This stage separates deterministic automated cleanup operations from manual evidence/backfill operations so later stages can preflight and execute only the safe subset before any training freeze.

## Implemented Scope

- `Dataset2TrainingReadinessService.staging_cleanup_execution_plan`
- `Dataset2TrainingReadinessService.list_staging_cleanup_execution_plans`
- API:
  - `POST /api/learning/dataset2/staging/cleanup-execution-plan`
  - `GET /api/learning/dataset2/staging/cleanup-execution-plans`
- Dashboard:
  - Dataset2 execution plan action
  - Latest plan status, source dry-run review id, automated/manual operation counts, preflight readiness, execution/training safety flags

## Plan Boundaries

- Automated scope is limited to deterministic cleanup operations such as `normalize_enum` and `parse_stringified_list_items`.
- Manual operations such as evidence backfill and historical outcome joins remain separated and must not be auto-executed.
- This stage records plan metadata only. It does not mutate staging rows or training tables.

## Required Safety Evidence

- Uses only the existing `events` table for plan metadata.
- Stores aggregate counts, batch metadata, and hashes only.
- Does not store source record bodies, normalized rows, affected row bodies, full evidence packages, SQL, runnable code, patches, or shell commands.
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

- Dataset2 unit/API tests cover missing, blocked, and ready-for-preflight plan paths.
- Dashboard type check and build still pass.
- Real local DB smoke may create one blocked plan event if the latest P16 review is blocked; staging and `learning_samples` counts must remain unchanged.
