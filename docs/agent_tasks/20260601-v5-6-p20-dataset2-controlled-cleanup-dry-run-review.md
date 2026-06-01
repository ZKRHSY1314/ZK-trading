# V5.6-P20 Dataset2 Controlled Cleanup Dry-Run Review

## Scope

Add a metadata-only review gate after the V5.6-P19 controlled cleanup dry-run.

## Implemented Surfaces

- `Dataset2TrainingReadinessService.staging_cleanup_execution_controlled_dry_run_review`
- `Dataset2TrainingReadinessService.list_staging_cleanup_execution_controlled_dry_run_reviews`
- API:
  - `POST /api/learning/dataset2/staging/cleanup-execution-controlled-dry-run-review`
  - `GET /api/learning/dataset2/staging/cleanup-execution-controlled-dry-run-reviews`
- Dashboard:
  - `Dataset2 Controlled Dry-Run Review` status panel
  - `Dataset2 controlled review` action button

## Safety Contract

- Reads only the latest or specified P19 controlled dry-run.
- Writes only one metadata event to the existing `events` table.
- Records reviewer metadata, aggregate simulation summaries, checks, and safety flags.
- Does not execute SQL, mutate staging rows, write `learning_samples`, write Dataset2 source files, export files, or start training.
- Keeps `review_only=true`, `simulation_only=true`, and `live_trading_enabled=false`.

## Validation Expectations

- Missing or blocked P19 dry-run returns blocked and must not become accepted.
- Passed P19 dry-run can be accepted only with `approved_for_controlled_cleanup_execution_review`.
- The event must not include record bodies, affected row bodies, executable code, SQL, patches, or full evidence packages.
