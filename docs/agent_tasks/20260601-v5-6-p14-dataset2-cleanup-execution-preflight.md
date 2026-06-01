# V5.6-P14 Dataset2 Cleanup Execution Preflight

## Goal

Record metadata-only cleanup execution preflight evidence after a passed V5.6-P13 manual approval, so a later stage can run a cleanup execution dry-run before any staging mutation.

## Scope

- Add service/API/dashboard support for cleanup execution preflight metadata.
- Require an existing ready P13 manual approval with zero blocked checks and `prepared_for_cleanup_execution_dry_run` operator metadata.
- Store source event ids, evidence package hash, deterministic lock key, rollback requirement, environment metadata, staging counts, learning-sample counts, request metadata, and safety flags.
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

- Backend targeted Dataset2 tests must cover missing P13 approval, blocked P13 approval, and ready P13 approval.
- API smoke must cover cleanup execution preflight create/list endpoints.
- Frontend typecheck/build must keep the new dashboard card and button valid.
- Real DB smoke must prove the event is metadata-only and staging/learning counts remain unchanged.
- Forbidden tracked-file scan must keep `.codegraph/`, local DBs, datasets, `.venv`, `node_modules`, `dist`, logs, and caches out of Git.
