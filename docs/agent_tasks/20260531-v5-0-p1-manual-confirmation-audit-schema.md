# V5.0-P1 Manual Confirmation And Audit Evidence Schema

## Summary

V5.0-P1 defines the first review-only contracts that a future Trade Execution Gateway would need before any real-money integration can be reviewed: a manual confirmation contract and an immutable audit evidence schema.

This stage still does not connect brokers, store credentials, read account funds, place/cancel/modify real trades, click trading software, write audit tables, create migrations, or enable live trading.

## Added Surface

- `GET /api/trade-execution-gateway/manual-confirmation-contract`
- `GET /api/trade-execution-gateway/audit-evidence-schema`
- `TradeExecutionGatewayService.manual_confirmation_contract()`
- `TradeExecutionGatewayService.audit_evidence_schema()`
- Dashboard evidence for confirmation contract and audit schema
- Release checklist V5.0-P1 entries
- Cockpit skill V5.0-P1 boundary notes

## Manual Confirmation Contract

The contract defines future evidence requirements only:

- operator id stored as hash or alias only
- explicit confirmation phrase
- proposal hash
- risk snapshot hash
- 120 second confirmation TTL
- reconfirmation on price or risk changes
- second reviewer requirement for high-risk situations

The contract returns `contract_allows_execution_now=false`.

## Audit Evidence Schema

The schema is not persisted and does not create any table. It defines future fields for:

- audit id
- event type
- proposal hash
- previous event hash
- event hash
- operator id hash
- confirmation excerpt
- risk snapshot hash
- market data quality
- safety flags
- created timestamp

The schema uses append-only and hash-chain rules, excludes broker credentials and sensitive account data, and returns `writes_database_now=false` plus `migration_allowed_now=false`.

## Safety Evidence

- `gateway_enabled=false`
- `execution_enabled=false`
- `broker_adapter_enabled=false`
- `credential_storage_enabled=false`
- `screen_click_trading_enabled=false`
- `places_real_trade=false`
- `writes_database_now=false`
- `runs_migration_now=false`
- `live_trading_enabled=false`

## Next Step

V5.0-P2 can design the portfolio and symbol risk-gate contract as review-only metadata. It should still avoid broker adapters, credential handling, real orders, screen-click trading, audit table creation, or live execution.
