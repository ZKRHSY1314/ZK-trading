# V5.6-P28 Dataset2 Controlled Cleanup Apply Execution Dry-Run Review

V5.6-P28 adds a metadata-only manual review gate after the V5.6-P27 controlled cleanup apply execution dry-run. It records operator review evidence for a future, separate apply execution plan without executing cleanup, writing SQL, mutating staging records, or promoting records into `learning_samples`.

## Scope

- `POST /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-dry-run-review`
- `GET /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-dry-run-reviews`
- `Dataset2TrainingReadinessService.staging_cleanup_execution_controlled_apply_execution_dry_run_review`
- Dashboard button and latest review card for the P28 review result.

## Required Safety

- Review writes only an `events` row.
- The accepted state requires a passed P27 dry-run and `approved_for_controlled_cleanup_apply_execution_plan`.
- The review stores aggregate simulation metadata only; no record bodies, SQL, executable code, exports, source dataset edits, staging mutation, `learning_samples` writes, or training start.
- `cleanup_execution_approved_now`, `cleanup_application_allowed_now`, `cleanup_executed_now`, `can_execute_cleanup_now`, `writes_learning_samples_now`, `training_started_now`, and `can_start_training_now` remain false.

## Verification

- Targeted backend tests cover missing dry-run, blocked dry-run, accepted dry-run review, and API smoke.
- Frontend type-check/build must keep the new panel compatible with the existing Dataset2 dashboard.
- Real local DB smoke should prove staging count and learning sample count remain unchanged.
