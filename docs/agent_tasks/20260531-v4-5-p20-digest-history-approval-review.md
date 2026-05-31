# V4.5-P20 Digest History Approval Freshness Review

## Summary

V4.5-P20 adds a review-only freshness and rotation check for digest history migration approval metadata. It prevents old approval evidence from looking current by summarizing whether the latest approval is missing, expired, mismatched with the current spec hash, or still reusable for manual release review.

## Added Surface

- `GET /api/screen-monitoring/readiness-health/history-migration-approval-review`
- `ScreenMonitoringService.screen_readiness_digest_history_approval_review()`
- Dashboard button: `审批有效期复核`
- Dashboard card: `Approval Review`
- Release checklist V4.5-P20 entries
- Cockpit skill V4.5-P20 boundary notes

## Review Policy

Default approval freshness window:

- `max_age_days=7`
- missing approval -> `approval_review_required`
- expired approval -> `approval_rotation_required`
- current spec hash mismatch -> `approval_rotation_required`
- fresh matching approval plus P19 release evidence -> `approval_current`

## Safety Evidence

The approval review preserves:

- `review_only=true`
- `simulation_only=true`
- `live_trading_enabled=false`
- `migration_allowed_now=false`
- `executes_sql=false`
- `runs_migration_now=false`
- `creates_table_now=false`
- `writes_database_now=false`
- `writes_migration_file_now=false`
- `writes_digest_history_table_now=false`

It reads existing approval metadata only. It does not write new approval records, apply migrations, execute SQL, create tables, write migration files, write digest history records, capture pixels, run OCR, click screens, connect brokers, or change live-trading state.

## Validation Commands

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_screen_monitoring.py -q
backend\.venv\Scripts\python.exe -m compileall backend\app backend\scripts
Set-Location backend; .\.venv\Scripts\python.exe -m pytest -q
Set-Location frontend; npx vue-tsc --noEmit
Set-Location frontend; npx vite build
Set-Location frontend; npm audit --audit-level=moderate
git diff --check
codegraph status
```

## Next Step

The digest-history migration review scaffolding is now fairly complete. Next, either add a final V4.5 migration release package checklist, or move into a V5.0 Trade Execution Gateway planning document. V5.0 must still start as design and review metadata, not live broker integration.
