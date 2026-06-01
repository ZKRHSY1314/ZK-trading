# V5.6-P22 Dataset2 Controlled Cleanup Execution Preflight

## Scope

Add a metadata-only preflight after the V5.6-P21 controlled cleanup execution approval.

## Implemented Surfaces

- `Dataset2TrainingReadinessService.staging_cleanup_execution_controlled_preflight`
- `Dataset2TrainingReadinessService.list_staging_cleanup_execution_controlled_preflights`
- API:
  - `POST /api/learning/dataset2/staging/cleanup-execution-controlled-preflight`
  - `GET /api/learning/dataset2/staging/cleanup-execution-controlled-preflights`
- Dashboard:
  - `Dataset2 Controlled Cleanup Preflight` status panel
  - `Dataset2 controlled preflight` action button

## Safety Contract

- Reads only the latest or specified P21 controlled approval.
- Writes only one metadata event to the existing `events` table.
- Validates lock key, staging count, learning-sample count, transaction/rollback requirement, and table scope before a later apply dry-run.
- Does not execute SQL, mutate staging rows, write `learning_samples`, write Dataset2 source files, export files, or start training.
- Keeps `review_only=true`, `simulation_only=true`, and `live_trading_enabled=false`.

## Validation Expectations

- Missing or blocked P21 approval returns blocked and must not become ready for apply dry-run.
- Passed P21 approval can advance only with `prepared_for_controlled_cleanup_execution_apply_dry_run`.
- The event must not include record bodies, affected row bodies, executable code, SQL, patches, or full evidence packages.
