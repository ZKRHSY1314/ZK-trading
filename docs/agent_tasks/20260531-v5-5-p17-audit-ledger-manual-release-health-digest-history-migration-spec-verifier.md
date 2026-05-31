# V5.5-P17 Audit Ledger Manual Release Health Digest History Migration Spec Verifier

## Scope

P17 adds an in-memory dry-run verifier for future manual release health digest history migration specs. It derives the safe default spec from the V5.5-P16 migration readiness checklist and verifies that all required metadata fields are covered.

## Implemented

- `TradeExecutionGatewayService.verify_audit_ledger_migration_manual_release_health_digest_history_migration_spec()` verifies future digest history migration spec text.
- `POST /api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-spec/verify` exposes the verifier for API smoke and dashboard use.
- Gateway capabilities, review gates, future components, API contracts, tests, and dashboard state include the P17 verifier.
- Release checklist and `a-share-trading-cockpit` skill document the P17 boundary.

## Safety Boundary

Required false flags:

- `executes_sql=false`
- `creates_table_now=false`
- `writes_database_now=false`
- `runs_migration_now=false`
- `writes_migration_file_now=false`
- `writes_history_row_now=false`
- `history_persistence_enabled_now=false`
- `release_approved_now=false`
- `migration_allowed_now=false`
- `execution_allowed_now=false`
- `persists_manual_release_health_digest_history=false`
- `writes_file=false`
- `live_trading_enabled=false`

Forbidden actions:

- Execute SQL or migration spec text.
- Create the manual release health digest history table.
- Persist manual release health digest history rows.
- Write migration files or downloads.
- Approve release, enable the gateway, connect brokers, store credentials, click screens, or place orders.

## Validation Targets

- Backend targeted tests: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_trade_execution_gateway.py backend\tests\test_api_contracts.py backend\tests\test_safety.py -q`
- Frontend: `npx vue-tsc --noEmit` and `npx vite build`
- Full release checks: compileall, full pytest, pip check, npm audit, `git diff --check`, forbidden tracked-file scan, and `codegraph status`.
