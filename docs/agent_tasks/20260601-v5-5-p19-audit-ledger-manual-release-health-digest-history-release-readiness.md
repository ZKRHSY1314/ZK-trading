# V5.5-P19 Audit Ledger Manual Release Health Digest History Release Readiness

## Scope

Add a review-only release-readiness summary for the future manual release health digest history migration track. The summary aggregates P15 retention proposal, P16 migration readiness checklist, P17 dry-run spec verifier, and P18 approval metadata.

## API

- `GET /api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-release-readiness`

## Required Behavior

- Return proposal, checklist, verifier, and latest approval evidence.
- Report gate statuses, blocked/review-required gates, go/no-go, target table, current spec hash, approved spec hash, and required manual artifacts.
- If approval metadata is missing or spec hash does not match, return review-required evidence rather than approving release.
- If all review gates pass, return `release_evidence_ready` while still keeping release and migration execution blocked.

## Safety

P19 must remain metadata-only and review-only:

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

Forbidden actions include SQL execution, migration execution, table creation, history-row writes, migration-file writes, file downloads, release approval, broker connection, real order placement, credential storage, and screen-click trading.

## Validation

- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_trade_execution_gateway.py backend\tests\test_api_contracts.py backend\tests\test_safety.py -q`
- `backend\.venv\Scripts\python.exe -m pytest -q`
- `npx vue-tsc --noEmit`
- `npx vite build`
- `git diff --check`
- forbidden tracked-file scan
- `codegraph status`
