# V5.6-P44 Dataset2 Controlled Cleanup Final Execution Dry-Run Review

## Summary

Add a metadata-only review gate after the V5.6-P43 final execution dry-run. This stage records operator review evidence for a future, separate final execution approval gate. It does not execute cleanup, mutate staging rows, write learning samples, start training, change source datasets, or enable live trading.

## Scope

- Add service/API/dashboard support for reviewing the latest or specified P43 final execution dry-run.
- Persist review metadata only into the existing `events` table.
- Preserve aggregate-only dry-run evidence: lock key, operation counts, simulated mutation count, transaction/rollback requirements, table scope, and no executable payload flags.
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

- Missing P43 dry-run returns blocked and writes no event.
- Passed P43 dry-run plus approved P44 review records an accepted metadata-only event.
- Rejected or needs-revision review remains blocked.
- API smoke covers create/list endpoints.
- Frontend shows P44 status and next action without any execution controls.
- Validation runs backend compile/tests, frontend type/build checks, safety scans, `/health`, and codegraph status.
