# V5.6-P25 Dataset2 Controlled Cleanup Apply Approval

## Scope

V5.6-P25 adds a metadata-only apply execution approval gate after the V5.6-P24 apply dry-run review. It records constrained operator approval for a future apply execution preflight.

## Implemented Surface

- `POST /api/learning/dataset2/staging/cleanup-execution-controlled-apply-approval`
- `GET /api/learning/dataset2/staging/cleanup-execution-controlled-apply-approvals`
- Dashboard panel and button: `Dataset2 apply approval`
- Release checklist entries for P25
- `a-share-trading-cockpit` skill stage map and playbook update

## Safety Boundary

The approval event stores only:

- source apply review ids
- source apply dry-run ids
- lock key
- aggregate approval scope
- reviewer metadata
- check summaries
- safety flags

The approval scope is `controlled_apply_preflight_only`. It must not execute cleanup, mutate staging rows, write `learning_samples`, include SQL, include runnable code, store record bodies, or start training.

Required false outputs:

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

## Validation Focus

- Missing P24 review returns blocked and writes no event.
- Blocked P24 review can only produce a blocked approval event.
- Accepted P24 review plus constrained approval metadata can become ready for a future apply execution preflight.
- API smoke confirms safety flags remain false.
- Real DB smoke must leave `dataset2_staging_records` and `learning_samples` counts unchanged.
