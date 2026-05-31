# V5.5-P12 Audit Ledger Migration Manual Release Evidence Verifier

## Goal

Add an in-memory verifier for offline manual release evidence payloads. The verifier checks whether the operator's evidence list is complete and safe enough for continued offline review, while preserving the strict non-execution boundary.

## Implemented Surface

- `POST /api/trade-execution-gateway/audit-ledger-migration-release-evidence/verify`
- `TradeExecutionGatewayService.verify_audit_ledger_migration_manual_release_evidence()`
- Frontend V5.5 gateway panel card for manual evidence verifier status, verification id, missing artifact count, persistence block, and next required action.
- Release checklist entries for V5.5-P12.

## Safety Boundary

This stage verifies evidence in memory only. It must not:

- persist manual release evidence
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

- Empty evidence returns missing evidence and lists all required artifacts.
- Complete fixture evidence passes only when source package id, rehearsal id, required artifacts, hashes, reviewer metadata, and safety flags match.
- Evidence containing forbidden fields such as SQL text, shell commands, broker credentials, account data, order actions, or screen-control fields is blocked.
- Decision and safety summary keep manual review recording, release approval, migration execution, database writes, file writes, and gateway execution blocked.
