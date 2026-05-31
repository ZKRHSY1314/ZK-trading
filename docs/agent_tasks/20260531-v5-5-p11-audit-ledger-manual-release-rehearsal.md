# V5.5-P11 Audit Ledger Migration Manual Release Review Rehearsal

## Goal

Add an API-only rehearsal layer for the future offline manual release review of the audit ledger migration package. The rehearsal converts V5.5-P10 package integrity evidence into operator-readable steps, pending evidence, offline artifacts, and safety confirmations.

## Implemented Surface

- `GET /api/trade-execution-gateway/audit-ledger-migration-release-review/rehearsal`
- `TradeExecutionGatewayService.audit_ledger_migration_manual_release_review_rehearsal()`
- Frontend V5.5 gateway panel card for manual release rehearsal status, rehearsal id, pending step count, and review-record prohibition.
- Release checklist entries for V5.5-P11.

## Safety Boundary

This stage is a rehearsal only. It must not:

- record manual release review
- mark rehearsal complete
- approve a release
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

- Missing approval or release evidence keeps rehearsal in waiting state.
- Current approval and passed integrity review make all rehearsal steps ready for offline manual review.
- Every rehearsal step requires operator action but has `api_can_mark_complete=false` and `api_can_record_approval=false`.
- Decision and safety summary keep release approval, migration execution, database writes, file writes, and gateway execution blocked.
