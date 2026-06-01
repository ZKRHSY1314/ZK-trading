# V5.6-P24 Dataset2 Controlled Cleanup Apply Dry-Run Review

## Scope

V5.6-P24 adds a metadata-only manual review gate after the V5.6-P23 controlled cleanup apply dry-run. It records whether the aggregate dry-run evidence is accepted for a future, separate execution approval path.

## Implemented Surface

- `POST /api/learning/dataset2/staging/cleanup-execution-controlled-apply-dry-run-review`
- `GET /api/learning/dataset2/staging/cleanup-execution-controlled-apply-dry-run-reviews`
- Dashboard panel and button: `Dataset2 apply review`
- Release checklist entries for P24
- `a-share-trading-cockpit` skill stage map and playbook update

## Safety Boundary

The review event stores only:

- source apply dry-run ids
- lock key
- aggregate simulation summaries
- reviewer metadata
- check summaries
- safety flags

It must not store source record bodies, normalized rows, affected row bodies, SQL, executable code, patches, exports, downloads, or full evidence packages.

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

- Missing P23 apply dry-run returns blocked and writes no event.
- Blocked P23 apply dry-run can only produce a blocked review event.
- Passed P23 apply dry-run plus constrained review metadata can produce an accepted review event.
- API smoke confirms safety flags remain false.
- Real DB smoke must leave `dataset2_staging_records` and `learning_samples` counts unchanged.
