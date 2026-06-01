# V5.6-P16 Dataset2 Cleanup Execution Dry-Run Review

## Goal

Add a metadata-only manual review gate for the V5.6-P15 aggregate cleanup execution dry-run. This gate records whether the dry-run is acceptable evidence for a future cleanup execution plan, but it does not execute cleanup, mutate staging rows, write `learning_samples`, export files, or start training.

## Implemented Scope

- `Dataset2TrainingReadinessService.staging_cleanup_execution_dry_run_review`
- `Dataset2TrainingReadinessService.list_staging_cleanup_execution_dry_run_reviews`
- API:
  - `POST /api/learning/dataset2/staging/cleanup-execution-dry-run-review`
  - `GET /api/learning/dataset2/staging/cleanup-execution-dry-run-reviews`
- Dashboard:
  - Dataset2 dry-run review action
  - Latest review status, source dry-run id, aggregate record counts, acceptance state, execution/training safety flags

## Required Safety Evidence

- Uses only the existing `events` table for review metadata.
- Stores aggregate counts and hashes only.
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

- Dataset2 unit/API tests cover missing, blocked, and accepted review paths.
- Dashboard type check and build still pass.
- Real local DB smoke may create one blocked review event if the latest P15 dry-run is blocked; staging and `learning_samples` counts must remain unchanged.
