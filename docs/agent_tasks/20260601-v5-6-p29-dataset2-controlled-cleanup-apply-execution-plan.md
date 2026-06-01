# V5.6-P29 Dataset2 Controlled Cleanup Apply Execution Plan

V5.6-P29 adds a metadata-only planning gate after the V5.6-P28 controlled cleanup apply execution dry-run review. It converts accepted aggregate review evidence into future execution batches and manual backfill batches for a later preflight, without executing cleanup, writing SQL, mutating staging records, or promoting records into `learning_samples`.

## Scope

- `POST /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan`
- `GET /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plans`
- `Dataset2TrainingReadinessService.staging_cleanup_execution_controlled_apply_execution_plan`
- Dashboard button and latest plan card for the P29 plan result.

## Required Safety

- The plan writes only an `events` row.
- The ready state requires an accepted P28 review and `prepared_for_controlled_cleanup_apply_execution_plan_preflight`.
- The plan stores aggregate metadata only; no record bodies, SQL, executable code, exports, source dataset edits, staging mutation, `learning_samples` writes, or training start.
- `cleanup_execution_approved_now`, `cleanup_application_allowed_now`, `cleanup_executed_now`, `can_execute_cleanup_now`, `writes_learning_samples_now`, `training_started_now`, and `can_start_training_now` remain false.

## Verification

- Targeted backend tests cover missing review, blocked review, ready plan, and API smoke.
- Frontend type-check/build must keep the new panel compatible with the existing Dataset2 dashboard.
- Real local DB smoke should prove staging count and learning sample count remain unchanged.
