# V5.6-P19 Dataset2 Controlled Cleanup Dry-Run

## Scope

Add a review-only controlled cleanup dry-run after the V5.6-P18 cleanup execution plan preflight.

## Implemented Surfaces

- `Dataset2TrainingReadinessService.staging_cleanup_execution_controlled_dry_run`
- `Dataset2TrainingReadinessService.list_staging_cleanup_execution_controlled_dry_runs`
- API:
  - `POST /api/learning/dataset2/staging/cleanup-execution-controlled-dry-run`
  - `GET /api/learning/dataset2/staging/cleanup-execution-controlled-dry-runs`
- Dashboard:
  - `Dataset2 Controlled Cleanup Dry-Run` status panel
  - `Dataset2 controlled dry-run` action button

## Safety Contract

- Reads only the latest or specified P18 plan preflight.
- Writes only one metadata event to the existing `events` table.
- Simulates aggregate automated/manual cleanup impact.
- Does not execute SQL, mutate staging rows, write `learning_samples`, write Dataset2 source files, export files, or start training.
- Keeps `review_only=true`, `simulation_only=true`, and `live_trading_enabled=false`.

## Validation Expectations

- Missing or blocked P18 preflight returns blocked and does not advance to review-ready.
- Passed P18 preflight can create a controlled dry-run with aggregate counts and lock-key traceability.
- The event must not include record bodies, affected row bodies, executable code, SQL, patches, or full evidence packages.
