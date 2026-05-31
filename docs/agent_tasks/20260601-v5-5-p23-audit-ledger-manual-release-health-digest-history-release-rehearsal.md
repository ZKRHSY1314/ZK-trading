# V5.5-P23 Audit Ledger Manual Release Health Digest History Release Rehearsal

## Summary

V5.5-P23 adds an API-only offline operator rehearsal for the manual release health digest history migration path. It consumes the P22 health digest history release package integrity review, turns it into a structured checklist for human release review, and keeps every action review-only and simulation-only.

## Delivered Surface

- Backend service method: `audit_ledger_migration_manual_release_health_digest_history_release_rehearsal`.
- API route: `GET /api/trade-execution-gateway/audit-ledger-migration-release-evidence/health-digest/history-migration-release-review/rehearsal`.
- Review gate: `audit_ledger_migration_manual_release_health_digest_history_release_rehearsal_required`.
- Dashboard card: Health Digest History Release Rehearsal.
- Release checklist entry covering P23 safety and operator handoff.

## Operator Workflow

1. Confirm the P22 package identity and integrity review are stable.
2. Check whether release evidence is ready and all manual artifacts are present.
3. Review pending or failed rehearsal steps before any offline manual release review.
4. Keep the API output as evidence only; do not treat it as approval or migration execution.
5. Complete any future release decision outside this API with separate offline sign-off and live integration review.

## Required False Evidence

- `manual_review_recorded_now=false`
- `marks_rehearsal_complete_now=false`
- `release_approved_now=false`
- `migration_allowed_now=false`
- `execution_allowed_now=false`
- `runs_migration_now=false`
- `executes_sql=false`
- `writes_history_row_now=false`
- `writes_migration_file_now=false`
- `writes_file=false`
- `download_created=false`
- `connects_broker=false`
- `places_real_trade=false`
- `live_trading_enabled=false`

## Forbidden Actions

- Do not record manual release review from this API.
- Do not mark rehearsal complete from this API.
- Do not approve release from rehearsal output.
- Do not execute health digest history migration.
- Do not persist rehearsal snapshots or create downloads.
- Do not connect broker adapters, store credentials, read accounts, place orders, or control trading software.

## Validation Targets

- `python -m pytest backend/tests/test_trade_execution_gateway.py backend/tests/test_api_contracts.py backend/tests/test_safety.py -q`
- `python -m compileall backend/app backend/scripts`
- `python -m pytest -q`
- `npx vue-tsc --noEmit`
- `npx vite build`
- `npm audit --audit-level=moderate`
- `git diff --check`
- forbidden tracked-file scan
- `codegraph status`
