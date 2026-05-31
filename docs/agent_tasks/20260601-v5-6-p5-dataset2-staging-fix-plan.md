# Task: V5.6-P5 Dataset2 Staging Fix Plan

## Goal
Convert V5.6-P4 Dataset2 staging quality review gates into a review-only fix plan. This stage plans what must be fixed before a future training freeze, but it must not apply fixes, mutate staging rows, write `learning_samples`, or start training.

## Scope
- Add APIs:
  - `POST /api/learning/dataset2/staging/fix-plan`
  - `GET /api/learning/dataset2/staging/fix-plans`
- Read the latest or selected V5.6-P4 quality review.
- Generate action items for blocked/warning gates:
  - quality flags
  - missing historical outcomes
  - split coverage
  - low-support labels
  - other failed gates
- Persist only fix plan metadata and evidence in the existing `events` table.
- Update dashboard, tests, release checklist, and skill boundaries.

## Safety Rules
- Do not apply fixes automatically.
- Do not mutate staging rows.
- Do not write `learning_samples`.
- Do not start model training.
- Do not modify Dataset2 source files.
- Do not write exports or downloads.
- Do not add broker, order, credential, screen-click, or live-trading capability.

## Acceptance Checks
- Missing quality review blocks fix plan generation.
- Fix plan uses quality review gates and creates review-only action items.
- Plan payload excludes record bodies.
- Dashboard shows action count, blocked gates, auto-apply blocked, and no-training evidence.
- Full validation and forbidden tracked-file scan pass.
