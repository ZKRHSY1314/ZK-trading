# V5.6-P23 Dataset2 Controlled Cleanup Apply Dry-Run

## Scope

V5.6-P23 adds an aggregate-only apply dry-run after the V5.6-P22 controlled cleanup execution preflight. It records review evidence in the existing `events` table and does not execute cleanup.

## Implemented Surface

- `POST /api/learning/dataset2/staging/cleanup-execution-controlled-apply-dry-run`
- `GET /api/learning/dataset2/staging/cleanup-execution-controlled-apply-dry-runs`
- Dashboard panel and button: `Dataset2 apply dry-run`
- Release checklist entries for P23
- `a-share-trading-cockpit` skill stage map and playbook update

## Safety Boundary

The apply dry-run reads staged aggregate metadata only:

- staging and learning-sample counts
- cleanup operation counts
- field counts
- quality-flag counts
- lock-key traceability
- transaction and rollback requirements
- allowed and forbidden table scope

It must not include source record bodies, normalized rows, affected row bodies, SQL, executable code, patches, exports, downloads, or full evidence packages.

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

- Missing P22 preflight returns blocked and writes no event.
- Blocked P22 preflight may record a blocked apply dry-run but cannot become review-ready.
- Passed P22 preflight can produce a review-ready aggregate dry-run.
- Repeated API smoke confirms safety flags remain false.
- Real DB smoke must leave `dataset2_staging_records` and `learning_samples` counts unchanged.
