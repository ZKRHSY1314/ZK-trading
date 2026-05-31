# V5.6-P6 Dataset2 Fix Approval And Preflight

## Goal

Record metadata-only approval for a V5.6-P5 Dataset2 staging fix plan, then generate deterministic preflight checks for the future manual cleanup stage.

## Scope

- Add approval APIs for selected or latest fix plans.
- Add preflight APIs backed by the existing `events` table.
- Keep approval limited to preflight permission, not fix application.
- Show dashboard evidence for approval, preflight checks, blocked mutation, and blocked training.

## Safety

- Do not mutate `dataset2_staging_records`.
- Do not write `learning_samples`.
- Do not modify Dataset2 source files.
- Do not create exports or downloads.
- Do not start training.
- Keep `review_only=true`, `simulation_only=true`, and `live_trading_enabled=false`.

## Acceptance

- Missing fix plan approval is blocked without event writes.
- Missing or non-approved preflight is blocked without event writes.
- Approved preflight writes only metadata into `events`.
- Full validation passes before commit.
