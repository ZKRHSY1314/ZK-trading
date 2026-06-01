# V5.6-P15 Dataset2 Cleanup Execution Dry-Run

## Goal

Generate an aggregate-only cleanup execution dry-run after a passed V5.6-P14 preflight, so a later manual review can inspect expected cleanup impact before any staging mutation.

## Scope

- Add service/API/dashboard support for cleanup execution dry-run metadata.
- Require an existing ready P14 preflight with zero blocked checks and `simulated_for_manual_review` operator metadata.
- Store source event ids, evidence package hash, aggregate candidate-record counts, cleanup operation counts, field counts, quality-flag counts, dry-run metadata, and safety flags.
- Keep cleanup execution, staging mutation, learning-sample writes, and training blocked.

## Safety Invariants

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
- `live_trading_enabled=false`

## Validation

- Backend targeted Dataset2 tests must cover missing P14 preflight, blocked P14 preflight, and ready P14 preflight.
- API smoke must cover cleanup execution dry-run create/list endpoints.
- Frontend typecheck/build must keep the new dashboard card and button valid.
- Real DB smoke must prove the event is metadata-only and staging/learning counts remain unchanged.
- Forbidden tracked-file scan must keep `.codegraph/`, local DBs, datasets, `.venv`, `node_modules`, `dist`, logs, and caches out of Git.
