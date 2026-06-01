# V5.6-P21 Dataset2 Controlled Cleanup Execution Approval

## Scope

Add a metadata-only approval gate after the V5.6-P20 controlled cleanup dry-run review.

## Implemented Surfaces

- `Dataset2TrainingReadinessService.staging_cleanup_execution_controlled_approval`
- `Dataset2TrainingReadinessService.list_staging_cleanup_execution_controlled_approvals`
- API:
  - `POST /api/learning/dataset2/staging/cleanup-execution-controlled-approval`
  - `GET /api/learning/dataset2/staging/cleanup-execution-controlled-approvals`
- Dashboard:
  - `Dataset2 Controlled Cleanup Approval` status panel
  - `Dataset2 controlled approval` action button

## Safety Contract

- Reads only the latest or specified P20 controlled dry-run review.
- Writes only one metadata event to the existing `events` table.
- Records approval metadata for a future controlled cleanup execution preflight only.
- Does not execute SQL, mutate staging rows, write `learning_samples`, write Dataset2 source files, export files, or start training.
- Keeps `review_only=true`, `simulation_only=true`, and `live_trading_enabled=false`.

## Validation Expectations

- Missing or blocked P20 review returns blocked and must not become ready for preflight.
- Passed P20 review can advance only with `approved_for_controlled_cleanup_execution_preflight`.
- The event must not include record bodies, affected row bodies, executable code, SQL, patches, or full evidence packages.
