# V5.6-P11 Dataset2 Cleanup Application Review

## Goal

Record a metadata-only cleanup application review gate after a passed V5.6-P10 manual evidence acceptance review, so a later stage can prepare a separately approved cleanup execution plan without mutating staging data now.

## Scope

- Add service/API/dashboard support for cleanup application review.
- Require an existing P10 acceptance review with zero blocked checks and `ready_for_future_cleanup_application` operator review metadata.
- Store only event ids, evidence package hash, section/check summaries, review metadata, and safety flags.
- Keep cleanup execution, staging mutation, learning-sample writes, and training blocked.

## Safety Invariants

- `cleanup_application_allowed_now=false`
- `cleanup_executed_now=false`
- `future_cleanup_execution_requires_separate_approval=true`
- `mutates_staging_records_now=false`
- `writes_staging_records_now=false`
- `writes_learning_samples_now=false`
- `can_promote_to_learning_samples_now=false`
- `training_started_now=false`
- `can_start_training_now=false`
- `live_trading_enabled=false`

## Validation

- Backend targeted Dataset2 tests must cover missing P10 acceptance, blocked P10 acceptance, and ready P10 acceptance.
- API smoke must cover cleanup application review create/list endpoints.
- Frontend typecheck/build must keep the new dashboard card and button valid.
- Forbidden tracked-file scan must keep `.codegraph/`, local DBs, datasets, `.venv`, `node_modules`, `dist`, logs, and caches out of Git.
