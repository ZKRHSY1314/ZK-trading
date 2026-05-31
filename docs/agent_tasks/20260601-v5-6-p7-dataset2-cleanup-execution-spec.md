# V5.6-P7 Dataset2 Cleanup Execution Spec

## Goal

Convert the V5.6-P6 Dataset2 fix preflight into a review-only cleanup execution specification.

## Scope

- Add execution-spec APIs backed by the existing `events` table.
- Translate preflight checks into future manual or reviewed-script steps.
- Preserve acceptance checks, forbidden actions, and source evidence links.
- Display dashboard evidence that the spec cannot be executed yet.

## Safety

- Do not execute SQL.
- Do not mutate `dataset2_staging_records`.
- Do not write `learning_samples`.
- Do not modify Dataset2 source files.
- Do not include record bodies in event payloads.
- Do not start training.

## Acceptance

- Missing preflight returns a blocked response and writes no event.
- Valid preflight creates one metadata-only execution-spec event.
- Spec reports `can_execute_now=false`, `contains_executable_code=false`, and `sql_included=false`.
- Full validation passes before commit.
