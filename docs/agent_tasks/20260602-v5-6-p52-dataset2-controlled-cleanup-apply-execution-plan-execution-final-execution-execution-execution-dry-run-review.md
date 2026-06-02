# V5.6-P52 Dataset2 Controlled Cleanup Final Execution Execution Execution Dry-run Review

## Goal

Add a metadata-only manual review gate after the V5.6-P51 aggregate dry-run.

## Scope

- Add P52 dry-run review service and list methods.
- Add POST/GET API routes for P52 review evidence.
- Add dashboard display and review button.
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

- Missing P51 dry-run returns blocked evidence and writes no event.
- Passed P51 dry-run plus `approved_for_controlled_cleanup_apply_execution_plan_execution_final_execution_execution_execution_execution_approval` records one review event.
- Review verifies aggregate dry-run evidence, including simulated mutation count, manual backfill separation, transaction/rollback, table scope, no SQL, no executable payload, and no record bodies.
- Rejected or needs-revision review does not become accepted.
- All cleanup/training/live-trading flags remain false.

## Validation

- `python -m py_compile backend/app/learning/dataset2_readiness.py backend/app/api/routes.py backend/tests/test_dataset2_readiness.py`
- `pytest backend/tests/test_dataset2_readiness.py -q -k "execution_execution_execution_dry_run_review or api_smoke"`
- `npx vue-tsc --noEmit`
- Full Dataset2 and release validation before commit.
