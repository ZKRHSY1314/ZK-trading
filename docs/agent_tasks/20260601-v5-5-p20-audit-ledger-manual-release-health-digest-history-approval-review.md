# V5.5-P20 Audit Ledger Manual Release Health Digest History Approval Review

## Scope

Add a review-only freshness and rotation review for the latest manual release health digest history migration spec approval metadata. This mirrors the earlier V5.5-P8 approval review, but uses the P18 history migration approval event and P19 release-readiness evidence.

## API

- `GET /api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-approval-review`

## Required Behavior

- Report whether approval metadata exists.
- Report approval age, expiry time, max-age policy, and expired state.
- Compare latest approved spec hash with the current P17 verified spec hash.
- Include P19 release-readiness status and go/no-go evidence.
- Return `approval_current` only when approval exists, is fresh, matches the current spec, and P19 release readiness is evidence-ready.
- Return review-required or rotation-required statuses without approving a release or enabling migration.

## Safety

P20 must remain metadata-only and review-only:

- `migration_allowed_now=false`
- `execution_allowed_now=false`
- `release_approved_now=false`
- `persists_manual_release_health_digest_history=false`
- `writes_history_row_now=false`
- `creates_table_now=false`
- `runs_migration_now=false`
- `executes_sql=false`
- `writes_migration_file_now=false`
- `writes_file=false`
- `live_trading_enabled=false`

Forbidden actions include SQL execution, migration execution, table creation, history-row writes, migration-file writes, release approval, broker connection, real order placement, credential storage, and treating expired approvals as current.

## Validation

- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_trade_execution_gateway.py backend\tests\test_api_contracts.py backend\tests\test_safety.py -q`
- `backend\.venv\Scripts\python.exe -m pytest -q`
- `npx vue-tsc --noEmit`
- `npx vite build`
- `git diff --check`
- forbidden tracked-file scan
- `codegraph status`
