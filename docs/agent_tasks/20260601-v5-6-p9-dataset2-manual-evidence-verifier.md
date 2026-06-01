# V5.6-P9 Dataset2 Manual Evidence Verifier

## Goal

Verify a manual evidence package for unresolved Dataset2 cleanup dry-run checks before any later cleanup application stage.

## Scope

- Add manual evidence verification APIs backed by the existing `events` table.
- Verify historical outcome source hash, join keys, and required field coverage.
- Verify quality flag dispositions, deterministic split acknowledgement, label support policy, and reviewer metadata.
- Store only evidence section names, a package hash, checks, reviewer metadata, and safety flags.

## Safety

- Do not store source records, normalized records, rows, or full evidence package bodies.
- Do not execute SQL.
- Do not apply cleanup.
- Do not mutate `dataset2_staging_records`.
- Do not write `learning_samples`.
- Do not modify Dataset2 source files.
- Do not start training.

## Acceptance

- Missing dry-run verification returns a blocked response and writes no event.
- Empty evidence package is blocked and recorded as metadata only.
- Complete evidence package can be verified for review while cleanup and training remain blocked.
- Full validation passes before commit.
