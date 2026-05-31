# V4.5-P19 Digest History Migration Release Readiness

## Summary

V4.5-P19 adds a final review-only release readiness summary for the future screen readiness digest history migration. It combines:

1. V4.5-P16 migration readiness checklist.
2. V4.5-P17 dry-run migration spec verifier.
3. V4.5-P18 operator approval metadata.

The summary is evidence for manual release review only. It does not apply migrations, execute SQL, create tables, write migration files, write digest history records, capture pixels, run OCR, click screens, connect brokers, or change live-trading state.

## Added Surface

- `GET /api/screen-monitoring/readiness-health/history-migration-release-readiness`
- `ScreenMonitoringService.screen_readiness_digest_history_release_readiness()`
- Dashboard button: `发布就绪汇总`
- Dashboard card: `Release Readiness`
- Release checklist V4.5-P19 entries
- Cockpit skill V4.5-P19 boundary notes

## Safety Evidence

The release readiness summary preserves:

- `review_only=true`
- `simulation_only=true`
- `live_trading_enabled=false`
- `migration_allowed_now=false`
- `executes_sql=false`
- `runs_migration_now=false`
- `creates_table_now=false`
- `writes_migration_file_now=false`
- `writes_digest_history_table_now=false`

Actual migration work still requires a separate reviewed migration file, rollback plan, migration tests, API smoke tests, database backup plan, and explicit operator release approval.

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

V4.5-P20 can either add an expiry/rotation review for migration approval metadata, or pause V4.5 migration scaffolding and move to a V5.0 planning document for a future human-reviewed Trade Execution Gateway. V5.0 must remain behind explicit human confirmation, audit logs, rollback, tests, and conservative risk review.
