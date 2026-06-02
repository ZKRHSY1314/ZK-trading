# V5.6-P51 Dataset2 Controlled Cleanup Final Execution Execution Execution Dry-run

## Goal

Add an aggregate-only dry-run after the V5.6-P50 final execution execution execution preflight.

## Scope

- Add metadata-only P51 dry-run service and list methods.
- Add POST/GET API routes for the P51 dry-run evidence.
- Add dashboard display and a dry-run button.
- Add backend unit/API smoke coverage.
- Update release checklist and the `a-share-trading-cockpit` skill stage map.

## Safety Boundary

- Do not execute cleanup.
- Do not execute SQL.
- Do not mutate `dataset2_staging_records`.
- Do not write `learning_samples`.
- Do not modify Dataset2 source files.
- Do not start training.
- Do not connect brokers, place orders, or control trading screens.

## Acceptance Checks

- Missing P50 preflight returns blocked evidence and writes no event.
- Passed P50 preflight plus `simulated_for_controlled_cleanup_apply_execution_plan_execution_final_execution_execution_execution_review` records one dry-run event.
- Dry-run preserves lock key, staging count, learning-sample count, transaction/rollback, table scope, and aggregate counts.
- Dry-run stores no record bodies, SQL, executable payload, or evidence package body.
- All cleanup/training/live-trading flags remain false.

## Validation

- `python -m py_compile backend/app/learning/dataset2_readiness.py backend/app/api/routes.py backend/tests/test_dataset2_readiness.py`
- `pytest backend/tests/test_dataset2_readiness.py -q -k "execution_execution_execution_dry_run or api_smoke"`
- `npx vue-tsc --noEmit`
- Full Dataset2 and release validation before commit.
