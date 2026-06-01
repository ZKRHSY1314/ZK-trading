# V5.6-P10 Dataset2 Manual Evidence Acceptance Review

## Goal

Record a metadata-only acceptance review for a passed V5.6-P9 Dataset2 manual evidence verification, so later cleanup application review can cite a stable evidence hash without storing source records or allowing execution.

## Scope

- Add service/API/dashboard support for manual evidence acceptance review.
- Require an existing P9 manual evidence verification with zero blocked checks and an explicit `accepted_for_cleanup_review` decision.
- Store only event ids, evidence package hash, section/check summaries, acceptance metadata, and safety flags.
- Keep cleanup, staging mutation, learning-sample writes, and training blocked.

## Safety Invariants

- `cleanup_application_allowed_now=false`
- `cleanup_executed_now=false`
- `mutates_staging_records_now=false`
- `writes_staging_records_now=false`
- `writes_learning_samples_now=false`
- `can_promote_to_learning_samples_now=false`
- `training_started_now=false`
- `can_start_training_now=false`
- `live_trading_enabled=false`

## Validation

- Backend targeted Dataset2 tests must cover missing P9 evidence, blocked P9 evidence, and accepted P9 evidence.
- API smoke must cover acceptance review create/list endpoints.
- Frontend typecheck/build must keep the new dashboard card and button valid.
- Forbidden tracked-file scan must keep `.codegraph/`, local DBs, datasets, `.venv`, `node_modules`, `dist`, logs, and caches out of Git.
