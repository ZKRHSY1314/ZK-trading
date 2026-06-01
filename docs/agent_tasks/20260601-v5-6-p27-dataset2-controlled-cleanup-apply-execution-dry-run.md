# V5.6-P27 Dataset2 Controlled Cleanup Apply Execution Dry-Run

## Summary

V5.6-P27 adds an aggregate-only dry-run after the V5.6-P26 controlled cleanup apply execution preflight. It simulates the future apply execution impact from staged metadata and records review evidence without executing cleanup or mutating any records.

## Implemented Surfaces

- `POST /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-dry-run`
- `GET /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-dry-runs`
- `Dataset2TrainingReadinessService.staging_cleanup_execution_controlled_apply_execution_dry_run`
- Dashboard panel and `Dataset2 apply execution dry-run` button
- Release checklist and `a-share-trading-cockpit` stage map updates

## Safety Boundary

- Does not execute cleanup.
- Does not execute SQL beyond existing event writes and aggregate reads.
- Does not mutate `dataset2_staging_records`.
- Does not write `learning_samples`.
- Does not start training, export files, modify Dataset2 source files, connect brokers, place orders, or change live-trading state.

## Validation Expectations

- Missing preflight returns `controlled_cleanup_apply_execution_dry_run_blocked_missing_preflight` and writes no event.
- Blocked source preflight records a blocked dry-run event while keeping cleanup and training disabled.
- Passed source preflight can produce `controlled_cleanup_apply_execution_dry_run_ready_for_review` only for `simulated_for_controlled_cleanup_apply_execution_review`.
- All outputs preserve `review_only=true`, `simulation_only=true`, and `live_trading_enabled=false`.
