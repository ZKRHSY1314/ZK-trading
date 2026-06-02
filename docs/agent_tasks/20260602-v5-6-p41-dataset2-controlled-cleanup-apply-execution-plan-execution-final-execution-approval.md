# V5.6-P41 Dataset2 Controlled Cleanup Apply Execution Plan Execution Final Execution Approval

## Goal

Add a metadata-only approval gate after the V5.6-P40 final dry-run review. This gate records whether an operator approves the aggregate final dry-run review evidence for a future, separate final execution preflight.

## Scope

- Add a service method and list method for final execution approvals.
- Add API endpoints:
  - `POST /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-execution-approval`
  - `GET /api/learning/dataset2/staging/cleanup-execution-controlled-apply-execution-plan-execution-final-execution-approvals`
- Add dashboard evidence for the latest final execution approval metadata.
- Add backend unit and API smoke coverage.
- Update release checklist and `a-share-trading-cockpit` stage map.

## Safety Boundary

P41 may write only one metadata event to the existing `events` table. It must not execute cleanup, execute SQL, apply fixes, mutate `dataset2_staging_records`, write `learning_samples`, start training, modify Dataset2 source files, export files, optimize positions, connect brokers, place orders, control trading screens, or change live-trading state.

Required false flags:

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

## Acceptance

- Missing P40 review returns a blocked response and writes no event.
- Accepted P40 review plus `approved_for_controlled_cleanup_apply_execution_plan_execution_final_execution_preflight` records an accepted approval.
- `needs_revision` or `rejected` approval decisions are recorded but remain blocked.
- Stored payload contains aggregate approval scope only, with no record bodies, SQL, executable code, patch, shell command, or evidence package body.
- Frontend can show empty state, accepted approval, blocked approval, and safety flags.

## Validation

- `backend\.venv\Scripts\python.exe -m py_compile backend\app\learning\dataset2_readiness.py backend\app\api\routes.py`
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_dataset2_readiness.py -q`
- `npx.cmd vue-tsc --noEmit`
- Full validation before release: backend compileall, full pytest, pip check, health false, frontend build/audit, git diff check, forbidden tracked-file scan, and codegraph status.
