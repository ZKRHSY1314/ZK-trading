# V5.6-P30 Dataset2 Controlled Cleanup Apply Execution Plan Preflight

V5.6-P30 adds a metadata-only preflight gate after the V5.6-P29 controlled cleanup apply execution plan. It verifies the plan scope, lock key, current staging count, learning-sample count, execution batch metadata, transaction/rollback requirements, and table boundaries before any later dry-run can be considered.

## Scope

- `POST /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-preflight`
- `GET /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-preflights`
- `Dataset2TrainingReadinessService.staging_cleanup_execution_controlled_apply_execution_plan_preflight`
- Dashboard button and latest preflight card for the P30 result.

## Required Safety

- The preflight writes only an `events` row.
- The ready state requires a passed P29 plan and `prepared_for_controlled_cleanup_apply_execution_plan_dry_run`.
- The preflight stores aggregate metadata only; no record bodies, SQL, executable code, exports, source dataset edits, staging mutation, `learning_samples` writes, or training start.
- `cleanup_execution_approved_now`, `cleanup_application_allowed_now`, `cleanup_executed_now`, `can_execute_cleanup_now`, `writes_learning_samples_now`, `training_started_now`, and `can_start_training_now` remain false.

## Verification

- Targeted backend tests cover missing plan, blocked plan, ready preflight, and API smoke.
- Frontend type-check/build must keep the new panel compatible with the existing Dataset2 dashboard.
- Real local DB smoke should prove staging count and learning sample count remain unchanged.
