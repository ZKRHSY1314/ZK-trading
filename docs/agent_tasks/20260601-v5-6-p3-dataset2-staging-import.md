# Task: V5.6-P3 Dataset2 Staging Import

## Goal
Move Dataset2 one step closer to training by allowing reviewed normalized records to be persisted into a quarantine staging table. This is not the final training dataset and must not start model training.

## Scope
- Add `dataset2_staging_records` as a quarantine table separate from `learning_samples`.
- Add APIs:
  - `POST /api/learning/dataset2/staging/import`
  - `GET /api/learning/dataset2/staging/records`
  - `GET /api/learning/dataset2/staging/summary`
- Require a matching V5.6-P2 import queue review event before staging records.
- Store normalized records in staging with package hash, review event id, quality flags, cleanup operations, and review-only status.
- Update dashboard, tests, release checklist, and skill boundaries.

## Safety Rules
- Do not write Dataset2 source files.
- Do not write `learning_samples`.
- Do not start model training.
- Do not create exports or downloads.
- Do not add broker, order, credential, screen-click, or live-trading capability.
- Keep `live_trading_enabled=false`.

## Acceptance Checks
- Import without matching review is blocked.
- Import with matching review writes staging rows only.
- Staging summary proves `learning_samples` remains untouched.
- Dashboard distinguishes quarantine staging from training data.
- Backend tests, frontend typecheck/build, full validation, codegraph status, and forbidden tracked-file scan pass.
