# Task: V5.6-P4 Dataset2 Staging Quality Review

## Goal
Add a training-freeze quality review over `dataset2_staging_records`. This stage checks whether staged Dataset2 records are ready to be considered for a future training freeze, but it must not promote data into `learning_samples` or start training.

## Scope
- Add APIs:
  - `POST /api/learning/dataset2/staging/quality-review`
  - `GET /api/learning/dataset2/staging/quality-reviews`
- Review staged records for:
  - record count
  - action label distribution
  - risk level distribution
  - split coverage
  - quality flags
  - cleanup operation counts
  - missing historical outcomes
  - low-support labels
- Persist only quality review metadata and gates in the existing `events` table.
- Update dashboard, tests, release checklist, and skill boundaries.

## Safety Rules
- Do not write `learning_samples`.
- Do not start model training.
- Do not modify Dataset2 source files.
- Do not write exports or downloads.
- Do not add broker, order, credential, screen-click, or live-trading capability.
- Keep `live_trading_enabled=false`.

## Acceptance Checks
- Quality review blocks training freeze when quality gates fail.
- Quality review payload does not include staged record bodies.
- API smoke covers quality review create/list.
- Dashboard shows blocked gate count and no-training evidence.
- Full validation and forbidden tracked-file scan pass.
