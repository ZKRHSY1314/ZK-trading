# V5.6-P26 Dataset2 Controlled Cleanup Apply Preflight

## Summary

V5.6-P26 adds a metadata-only preflight after the V5.6-P25 controlled cleanup apply execution approval. It validates the approved lock key, staging count, learning-sample count, transaction/rollback requirement, table scope, aggregate-only metadata, and no-executable-payload safety boundary before a future apply dry-run.

## Implemented Surfaces

- `POST /api/learning/dataset2/staging/cleanup-execution-controlled-apply-preflight`
- `GET /api/learning/dataset2/staging/cleanup-execution-controlled-apply-preflights`
- `Dataset2TrainingReadinessService.staging_cleanup_execution_controlled_apply_preflight`
- Dashboard panel and `Dataset2 apply preflight` button
- Release checklist and `a-share-trading-cockpit` stage map updates

## Safety Boundary

- Does not execute cleanup.
- Does not execute SQL beyond existing event writes and aggregate reads.
- Does not mutate `dataset2_staging_records`.
- Does not write `learning_samples`.
- Does not start training, export files, modify Dataset2 source files, connect brokers, place orders, or change live-trading state.

## Validation Expectations

- Missing approval returns `controlled_cleanup_apply_execution_preflight_blocked_missing_approval` and writes no event.
- Blocked source approval records a blocked preflight event while keeping cleanup and training disabled.
- Passed source approval can produce `controlled_cleanup_apply_execution_preflight_ready_for_dry_run` only for `prepared_for_controlled_cleanup_apply_execution_dry_run`.
- All outputs preserve `review_only=true`, `simulation_only=true`, and `live_trading_enabled=false`.
