# V5.5-P13 Audit Ledger Migration Manual Release Evidence Comparison

## Goal

Add an in-memory comparison layer for two offline manual release evidence payloads. The comparison reports whether verifier outputs and artifact metadata are stable across revisions, while preserving the strict non-execution boundary.

## Implemented Surface

- `POST /api/trade-execution-gateway/audit-ledger-migration-release-evidence/compare`
- `TradeExecutionGatewayService.compare_audit_ledger_migration_manual_release_evidence()`
- Frontend V5.5 gateway panel card for evidence comparison status, comparison id, changed artifact hash count, persistence block, and next required action.
- Release checklist entries for V5.5-P13.

## Safety Boundary

This stage compares evidence in memory only. It must not:

- persist manual release evidence or comparisons
- mutate evidence payloads
- record manual review
- approve release
- execute SQL
- create tables
- run migrations
- write migration files
- write audit ledger rows
- write files
- create downloads
- enable the gateway
- connect brokers
- read accounts or funds
- place, cancel, or modify orders
- click or type into trading software
- change `live_trading_enabled`

Required evidence remains `review_only=true`, `simulation_only=true`, and `live_trading_enabled=false`.

## Validation Expectations

- Empty baseline/candidate evidence returns `manual_release_evidence_comparison_missing`.
- Identical complete fixture evidence returns `manual_release_evidence_comparison_stable`.
- Artifact hash changes return `manual_release_evidence_comparison_changed` and identify the changed artifact.
- Decision and safety summary keep manual review recording, release approval, migration execution, database writes, file writes, evidence persistence, evidence mutation, and gateway execution blocked.
