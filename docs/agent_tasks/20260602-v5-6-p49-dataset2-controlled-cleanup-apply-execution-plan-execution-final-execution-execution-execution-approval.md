# V5.6-P49 Dataset2 Controlled Cleanup Final Execution Execution Execution Approval

## Scope

Add a metadata-only approval gate after the V5.6-P48 final execution execution dry-run review.

## Acceptance

- Add POST/GET APIs for final execution execution execution approval history.
- Accept only an accepted P48 dry-run review and the constrained approval decision.
- Persist only aggregate approval metadata into the existing events table.
- Carry forward lock key, transaction/rollback, table scope, and aggregate dry-run counts for a future P50 preflight.
- Keep cleanup execution, staging mutation, learning sample writes, source dataset writes, file export, and training blocked.
- Surface the approval result on the dashboard with review-only safety evidence.

## Forbidden

- Do not execute cleanup, SQL, patches, shell commands, exports, or training.
- Do not mutate `dataset2_staging_records` or write `learning_samples`.
- Do not modify Dataset2 source files.
- Do not add broker/order/credential/screen-click/live-trading behavior.
