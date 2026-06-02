# V5.6-P45 Dataset2 Controlled Cleanup Final Execution Execution Approval

## Summary

Add a metadata-only approval gate after the V5.6-P44 final execution dry-run review. This stage records constrained operator approval evidence for a future, separate final execution execution preflight. It does not execute cleanup, mutate staging rows, write learning samples, start training, change source datasets, or enable live trading.

## Scope

- Add service/API/dashboard support for approving the latest or specified P44 review.
- Persist approval metadata only into the existing `events` table.
- Preserve aggregate-only scope: P43/P44 ids, lock key, operation counts, simulated mutation count, transaction/rollback requirements, table scope, and no executable payload flags.
- Keep all safety flags review-only and simulation-only.

## Required Safety Flags

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

## Acceptance Checks

- Missing P44 review returns blocked and writes no event.
- Accepted P44 review plus approved P45 decision records accepted metadata only.
- Rejected or needs-revision approval remains blocked.
- API smoke covers create/list endpoints.
- Frontend shows P45 status and next action without cleanup execution controls.
- Validation runs backend compile/tests, frontend type/build checks, safety scans, `/health`, and codegraph status.
