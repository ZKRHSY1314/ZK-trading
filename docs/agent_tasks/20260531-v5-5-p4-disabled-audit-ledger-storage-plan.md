# V5.5-P4 Disabled Audit Ledger Storage Plan Handoff

## Summary

V5.5-P4 defines a disabled, review-only storage plan for a future `trade_execution_audit_ledger`. It describes planned columns, proposed indexes, hash-chain rules, retention, redaction, migration preconditions, and rollback requirements, but does not create tables, write migrations, write audit rows, connect brokers, store credentials, read accounts, submit orders, or control screens.

## Added

- Added `TradeExecutionGatewayService.audit_ledger_storage_plan()`.
- Added `GET /api/trade-execution-gateway/audit-ledger-storage-plan`.
- Extended gateway capabilities, future components, and review gates with `disabled_audit_ledger_storage_plan_review`.
- Updated the dashboard with `Audit Ledger Storage Plan` and `Storage Plan Safety` cards.
- Added backend tests and API contract coverage for disabled storage, planned columns/indexes, redaction, hash-chain policy, and migration blockers.

## Storage Plan Evidence

The plan includes:

- Future table: `trade_execution_audit_ledger`
- Planned columns for audit id, timestamps, event type, hashes, runbook references, redacted review notes, and safety flags.
- Proposed indexes for created time, event type, proposal hash, and event hash.
- Hash-chain policy using SHA-256 over canonical JSON with `previous_event_hash`.
- Retention policy requiring manual archive and operator approval before any prune.
- Redaction policy excluding broker credentials, trading PINs, SMS codes, API secrets, session cookies, and raw account numbers.
- Migration preconditions requiring a dry-run verifier, operator approval, backup/restore review, rollback review, forbidden-field scan, and `/health.live_trading_enabled=false`.

## Safety Boundary

V5.5-P4 must preserve:

- `can_create_table_now=false`
- `can_write_audit_row_now=false`
- `can_run_migration_now=false`
- `can_write_migration_file_now=false`
- `writes_database_now=false`
- `runs_migration_now=false`
- `records_audit_rows_now=false`
- `connects_broker=false`
- `places_real_trade=false`
- `live_trading_enabled=false`

## Validation

Targeted backend validation:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_trade_execution_gateway.py backend\tests\test_api_contracts.py backend\tests\test_safety.py -q
```

Result: `30 passed`.

## Next Step

V5.5-P5 can add a dry-run verifier for the disabled audit ledger migration spec. It should validate a proposed spec in memory/API response only and still avoid SQL execution, table creation, migration files, audit-row persistence, broker connectivity, credentials, account reads, orders, and screen control.
