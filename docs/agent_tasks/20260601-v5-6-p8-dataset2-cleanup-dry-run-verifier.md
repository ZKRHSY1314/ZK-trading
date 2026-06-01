# V5.6-P8 Dataset2 Cleanup Dry-Run Verifier

## Goal

Verify a V5.6-P7 Dataset2 cleanup execution spec in dry-run mode before any later cleanup application stage.

## Scope

- Add dry-run verification APIs backed by the existing `events` table.
- Verify that the execution spec is descriptive only: no executable code, no SQL, no record bodies.
- Verify that forbidden actions are complete and source blocked checks are surfaced.
- Show dashboard evidence that cleanup application, training, and learning-sample promotion remain blocked.

## Safety

- Do not execute SQL.
- Do not apply cleanup.
- Do not mutate `dataset2_staging_records`.
- Do not write `learning_samples`.
- Do not modify Dataset2 source files.
- Do not start training.

## Acceptance

- Missing execution spec returns a blocked response and writes no event.
- Valid execution spec creates one metadata-only dry-run verification event.
- Existing Dataset2 smoke keeps staging count unchanged and learning sample count unchanged.
- Full validation passes before commit.
