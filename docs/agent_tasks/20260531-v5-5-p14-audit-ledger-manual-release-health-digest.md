# V5.5-P14 Audit Ledger Migration Manual Release Health Digest

## Goal

Add an API-only health digest for the audit ledger migration manual release track. The digest summarizes package, integrity, rehearsal, verifier, comparison, and safety evidence so the operator can see whether the offline release evidence needs attention.

## Implemented Surface

- `POST /api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest`
- `TradeExecutionGatewayService.audit_ledger_migration_manual_release_health_digest()`
- Frontend V5.5 gateway panel card for health digest status, digest id, attention count, persistence block, and next required action.
- Release checklist entries for V5.5-P14.

## Safety Boundary

This stage summarizes evidence in memory only. It must not:

- persist health digests, evidence, or comparisons
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

- Empty baseline/candidate evidence returns `manual_release_health_digest_attention_required`.
- Complete stable fixture evidence returns `manual_release_health_digest_healthy`.
- Digest reports module status, attention count, missing artifact count, changed artifact hash count, and pending rehearsal steps.
- Decision and safety summary keep manual review recording, release approval, migration execution, database writes, file writes, digest persistence, evidence mutation, and gateway execution blocked.
