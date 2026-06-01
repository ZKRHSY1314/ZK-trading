# V5.6-P34 Dataset2 Controlled Cleanup Apply Execution Plan Execution Preflight

## Scope

Add the next metadata-only Dataset2 gate after V5.6-P33 approval:

- `POST /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-preflight`
- `GET /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-preflights`

## Required Behavior

- Read the latest or specified P33 execution approval.
- Validate lock key, staging count, learning-sample count, transaction and rollback requirement, table scope, aggregate-only evidence, no SQL, no executable payload, and no record bodies.
- Record only an `events` table metadata payload.
- Keep `dataset2_staging_records`, `learning_samples`, Dataset2 source files, exports, and training untouched.

## Safety Boundary

All outputs must keep:

- `review_only=true`
- `simulation_only=true`
- `live_trading_enabled=false`
- `cleanup_execution_approved_now=false`
- `cleanup_application_allowed_now=false`
- `cleanup_executed_now=false`
- `can_execute_cleanup_now=false`
- `writes_learning_samples_now=false`
- `training_started_now=false`

## Validation

- Backend targeted Dataset2 tests.
- API smoke for the new POST/GET endpoints.
- Real local SQLite smoke confirming staging count and learning-sample count are unchanged.
- Frontend typecheck/build.
- Full release validation before commit and push.
