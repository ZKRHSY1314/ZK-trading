# V5.6-P13 Dataset2 Cleanup Execution Manual Approval

## Goal

Record metadata-only manual approval for a passed V5.6-P12 cleanup execution approval plan, so a later stage can run a cleanup execution preflight before any staging mutation.

## Scope

- Add service/API/dashboard support for cleanup execution manual approval metadata.
- Require an existing ready P12 approval plan with zero blocked checks and `approved_for_cleanup_execution_preflight` operator metadata.
- Store only source event ids, evidence package hash, approval-step summary, check summaries, manual approval metadata, and safety flags.
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

- Backend targeted Dataset2 tests must cover missing P12 plan, blocked P12 plan, and ready P12 plan.
- API smoke must cover cleanup execution manual approval create/list endpoints.
- Frontend typecheck/build must keep the new dashboard card and button valid.
- Real DB smoke must prove the event is metadata-only and staging/learning counts remain unchanged.
- Forbidden tracked-file scan must keep `.codegraph/`, local DBs, datasets, `.venv`, `node_modules`, `dist`, logs, and caches out of Git.
