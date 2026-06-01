# V5.6-P12 Dataset2 Cleanup Execution Approval Plan

## Goal

Generate a metadata-only cleanup execution approval plan after a passed V5.6-P11 cleanup application review, so a later stage can ask for explicit manual execution approval before any staging mutation.

## Scope

- Add service/API/dashboard support for cleanup execution approval planning.
- Require an existing P11 cleanup application review with zero blocked checks and `prepared_for_manual_approval` planning metadata.
- Store only source event ids, evidence package hash, non-executable approval steps, check summaries, planning metadata, and safety flags.
- Keep cleanup execution, staging mutation, learning-sample writes, and training blocked.

## Safety Invariants

- `cleanup_execution_approved_now=false`
- `cleanup_application_allowed_now=false`
- `cleanup_executed_now=false`
- `can_execute_cleanup_now=false`
- `future_cleanup_execution_requires_separate_approval=true`
- `mutates_staging_records_now=false`
- `writes_staging_records_now=false`
- `writes_learning_samples_now=false`
- `can_promote_to_learning_samples_now=false`
- `training_started_now=false`
- `can_start_training_now=false`
- `live_trading_enabled=false`

## Validation

- Backend targeted Dataset2 tests must cover missing P11 review, blocked P11 review, and ready P11 review.
- API smoke must cover cleanup execution approval plan create/list endpoints.
- Frontend typecheck/build must keep the new dashboard card and button valid.
- Forbidden tracked-file scan must keep `.codegraph/`, local DBs, datasets, `.venv`, `node_modules`, `dist`, logs, and caches out of Git.
