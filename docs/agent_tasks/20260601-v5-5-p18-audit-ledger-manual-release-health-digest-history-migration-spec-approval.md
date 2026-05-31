# V5.5-P18 Handoff: Health Digest History Migration Spec Approval Metadata

## Scope

V5.5-P18 adds operator approval metadata for the V5.5-P17 manual release health digest history migration spec verifier.

This stage may:
- Verify a future `manual_release_health_digest_history` migration spec in memory.
- Record approval metadata into the existing `events` table only after verification passes.
- List recorded approval metadata for dashboard and audit review.
- Show approval status/history in the V5.5 dashboard.

This stage must not:
- Execute SQL.
- Create the history table.
- Write history rows.
- Write migration files or downloads.
- Approve a release or migration for execution.
- Enable the gateway, broker adapter, credentials, screen-click trading, or live trading.

## API

- `POST /api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-spec/approve`
- `GET /api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-spec/approvals?limit=20`

The approval endpoint returns `approval_metadata_recorded` only when the P17 verifier returns `spec_verification_passed`.
Unsafe specs return `approval_blocked` and `event_id=null`.

## Safety Evidence

Expected false flags:
- `migration_allowed_now=false`
- `persists_manual_release_health_digest_history=false`
- `writes_history_row_now=false`
- `creates_table_now=false`
- `runs_migration_now=false`
- `executes_sql=false`
- `writes_migration_file_now=false`
- `writes_file=false`
- `connects_broker=false`
- `places_real_trade=false`
- `live_trading_enabled=false`

## Validation

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_trade_execution_gateway.py backend\tests\test_api_contracts.py backend\tests\test_safety.py -q
npx vue-tsc --noEmit
npx vite build
backend\.venv\Scripts\python.exe -m pytest -q
git diff --check
codegraph status
```
