# V5.6-P48 Dataset2 Controlled Cleanup Final Execution Execution Dry-Run Review

## Scope

Add a metadata-only review gate after the V5.6-P47 final execution execution dry-run.

## Acceptance

- Add POST/GET APIs for final execution execution dry-run review history.
- Accept only a passed P47 dry-run and the constrained review decision.
- Persist only aggregate review metadata into the existing events table.
- Keep cleanup execution, staging mutation, learning sample writes, source dataset writes, file export, and training blocked.
- Surface the review result on the dashboard with review-only safety evidence.

## Forbidden

- Do not execute cleanup, SQL, patches, shell commands, exports, or training.
- Do not mutate `dataset2_staging_records` or write `learning_samples`.
- Do not modify Dataset2 source files.
- Do not add broker/order/credential/screen-click/live-trading behavior.
