# V5.5-P8 Audit Ledger Migration Approval Review

## Summary

V5.5-P8 adds a review-only freshness and rotation review for future trade execution audit ledger migration approval metadata. It checks whether the latest approval exists, remains within the validity window, still matches the current verified spec hash, and can be reused for manual release review.

This stage does not execute SQL, create tables, run migrations, write migration files, write audit ledger rows, approve release, enable the gateway, connect brokers, store credentials, read accounts/funds, place/cancel/modify orders, click/type trading software, or change live-trading state.

## Implemented Surface

- `GET /api/trade-execution-gateway/audit-ledger-migration-approval-review?limit=&max_age_days=`
- `TradeExecutionGatewayService.audit_ledger_migration_approval_review(limit=50, max_age_days=7)`
- V5.5-P8 dashboard card showing approval review status, next action, age, max age policy, spec match, and reuse yes/no evidence.
- Release checklist entries for the V5.5-P8 gate.
- `a-share-trading-cockpit` skill stage/playbook update.

## Safety Evidence

- `approval_can_be_reused_for_manual_release_review` is evidence-only
- `migration_allowed_now=false`
- `executes_sql=false`
- `runs_migration_now=false`
- `creates_table_now=false`
- `writes_database_now=false`
- `writes_audit_ledger_row_now=false`
- `writes_migration_file_now=false`
- `approves_release_now=false`
- `enables_gateway_now=false`
- `connects_broker=false`
- `places_real_trade=false`
- `live_trading_enabled=false`

## Validation Targets

- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_trade_execution_gateway.py backend\tests\test_api_contracts.py backend\tests\test_safety.py -q`
- `backend\.venv\Scripts\python.exe -m compileall backend\app backend\scripts`
- `cd backend; .\.venv\Scripts\python.exe -m pytest -q`
- `cd backend; .\.venv\Scripts\python.exe -m pip check`
- `cd frontend; npx vue-tsc --noEmit`
- `cd frontend; npx vite build`
- `cd frontend; npm audit --audit-level=moderate`
- `git diff --check`
- forbidden tracked-file scan
- `codegraph status`

## Next Candidate Step

V5.5-P9 can aggregate the audit ledger migration storage plan, verifier, approval metadata, release readiness, and approval freshness review into a manual release package manifest. It should remain review-only and must not execute SQL, create tables, run migrations, write migration files, write audit ledger rows, approve release, enable the gateway, connect brokers, store credentials, read accounts, add order endpoints, or control screens.
